using System;
using System.Linq;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Reflection;
using HIDMaestro;

namespace HIDMaestroHost;

class Program
{
    static Program()
    {
        System.Runtime.Loader.AssemblyLoadContext.Default.Resolving += (context, assemblyName) =>
        {
            if (string.Equals(assemblyName.Name, "HIDMaestro.Core", StringComparison.OrdinalIgnoreCase))
            {
                string? path = FindCoreDll();
                if (path != null)
                {
                    return context.LoadFromAssemblyPath(path);
                }
            }
            return null;
        };

        AppDomain.CurrentDomain.AssemblyResolve += (sender, args) =>
        {
            var asmName = new AssemblyName(args.Name).Name;
            if (string.Equals(asmName, "HIDMaestro.Core", StringComparison.OrdinalIgnoreCase))
            {
                string? path = FindCoreDll();
                if (path != null)
                {
                    return Assembly.LoadFrom(path);
                }
            }
            return null;
        };
    }

    private static string? FindCoreDll()
    {
        string baseDir = AppContext.BaseDirectory;
        var arch = RuntimeInformation.ProcessArchitecture;
        var dllNames = new List<string>();

        if (arch == Architecture.Arm64)
        {
            dllNames.Add("HIDMaestro.Core.arm64.dll");
        }
        else
        {
            dllNames.Add("HIDMaestro.Core.amd64.dll");
            dllNames.Add("HIDMaestro.Core.x64.dll");
        }
        dllNames.Add("HIDMaestro.Core.dll");

        string[] searchDirs = new[]
        {
            baseDir,
            Path.Combine(baseDir, ".."),
            Path.Combine(baseDir, "..", ".."),
            Path.Combine(baseDir, "bin"),
            Path.Combine(baseDir, "bin", "hidmaestro"),
            Path.Combine(baseDir, "..", "bin"),
            Path.Combine(baseDir, "..", "bin", "hidmaestro"),
            Path.Combine(baseDir, "..", "hidmaestro"),
            Path.Combine(baseDir, "lib"),
        };

        foreach (var dir in searchDirs)
        {
            foreach (var dllName in dllNames)
            {
                string fullPath = Path.GetFullPath(Path.Combine(dir, dllName));
                if (File.Exists(fullPath))
                {
                    return fullPath;
                }
            }
        }
        return null;
    }

    static int Main(string[] args)
    {
        return HostServer.Run(args);
    }
}

class HostServer
{
    private static HMContext? s_ctx;
    private static readonly ConcurrentDictionary<int, HMController> s_controllers = new();
    private static readonly object s_sendLock = new();
    private static readonly List<Stream> s_activeStreams = new();
    private static bool s_running = true;

    static bool IsElevated()
    {
        try
        {
            using var identity = WindowsIdentity.GetCurrent();
            var principal = new WindowsPrincipal(identity);
            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch
        {
            return false;
        }
    }

    static int RelaunchElevated(string[] args, bool hidden = false)
    {
        string exe = Environment.ProcessPath ?? Process.GetCurrentProcess().MainModule!.FileName;
        var psi = new ProcessStartInfo
        {
            FileName = exe,
            Arguments = string.Join(" ", args),
            UseShellExecute = true,
            Verb = "runas",
            WindowStyle = hidden ? ProcessWindowStyle.Hidden : ProcessWindowStyle.Normal,
        };
        try
        {
            using var proc = Process.Start(psi);
            proc?.WaitForExit();
            return proc?.ExitCode ?? 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[!] Error al solicitar elevacion: {ex.Message}");
            return 1;
        }
    }

    public static int Run(string[] args)
    {
        int port = 3255;
        bool quiet = false;
        bool noElevate = false;

        foreach (var arg in args)
        {
            if (arg.StartsWith("--port=", StringComparison.OrdinalIgnoreCase))
            {
                int.TryParse(arg.Substring(7), out port);
            }
            else if (arg.Equals("--quiet", StringComparison.OrdinalIgnoreCase))
            {
                quiet = true;
            }
            else if (arg.Equals("--no-elevate", StringComparison.OrdinalIgnoreCase))
            {
                noElevate = true;
            }
            else if (arg.Equals("--install-driver", StringComparison.OrdinalIgnoreCase))
            {
                if (!IsElevated())
                {
                    return RelaunchElevated(args, hidden: false);
                }
                try
                {
                    Console.WriteLine("[*] Instalando controlador HIDMaestro en el DriverStore...");
                    using var ctx = new HMContext();
                    ctx.InstallDriver();
                    Console.WriteLine("[+] Driver HIDMaestro instalado con exito en el sistema.");
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[!] Error instalando driver HIDMaestro: {ex.Message}");
                    return 1;
                }
            }
            else if (arg.Equals("--elevate", StringComparison.OrdinalIgnoreCase))
            {
                if (!IsElevated())
                {
                    return RelaunchElevated(args, hidden: true);
                }
            }
        }

        // Do not block running un-elevated if driver is already installed
        if (!noElevate && args.Any(a => a.Equals("--elevate", StringComparison.OrdinalIgnoreCase)) && !IsElevated())
        {
            return RelaunchElevated(args, hidden: quiet);
        }

        if (!quiet)
        {
            Console.WriteLine("=================================================");
            Console.WriteLine($"  HIDMaestro Host Server - Puerto {port}");
            Console.WriteLine($"  Elevado (Admin): {IsElevated()}");
            Console.WriteLine("=================================================");
        }

        try
        {
            s_ctx = new HMContext();
            int count = s_ctx.LoadDefaultProfiles();
            if (!quiet) Console.WriteLine($"[+] Catalogo de perfiles cargado: {count} perfiles disponibles.");

            if (!s_ctx.IsDriverInstalled && IsElevated())
            {
                if (!quiet) Console.WriteLine("[*] Instalando controlador de HIDMaestro en el sistema...");
                try
                {
                    s_ctx.InstallDriver();
                    if (!quiet) Console.WriteLine("[+] Controlador HIDMaestro instalado con exito.");
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[!] Error al instalar driver en inicio: {ex.Message}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[!] Error inicializando HMContext: {ex.Message}");
            return 1;
        }

        // Safety cleanup on process exit
        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            Cleanup();
        };

        Console.CancelKeyPress += (_, e) =>
        {
            e.Cancel = true;
            s_running = false;
            Cleanup();
            Environment.Exit(0);
        };

        RunServer(port, quiet);
        return 0;
    }

    static void Cleanup()
    {
        try
        {
            foreach (var kvp in s_controllers)
            {
                try { kvp.Value.Dispose(); } catch { }
            }
            s_controllers.Clear();
            s_ctx?.Dispose();
            s_ctx = null;
            HMContext.RemoveAllVirtualControllers(preserveInstall: true);
        }
        catch { }
    }

    static void RunServer(int port, bool quiet)
    {
        TcpListener listener = new TcpListener(IPAddress.Loopback, port);
        try
        {
            listener.Start();
            if (!quiet) Console.WriteLine($"[+] Escuchando en 127.0.0.1:{port}...");

            while (s_running)
            {
                TcpClient client = listener.AcceptTcpClient();
                client.NoDelay = true;
                if (!quiet) Console.WriteLine("[+] Cliente conectado.");

                Thread clientThread = new Thread(() => HandleClient(client, quiet))
                {
                    IsBackground = true
                };
                clientThread.Start();
            }
        }
        catch (Exception ex)
        {
            if (s_running) Console.Error.WriteLine($"[!] Error en el servidor: {ex.Message}");
        }
        finally
        {
            listener.Stop();
        }
    }

    static void SendResponse(Stream stream, string msg)
    {
        lock (s_sendLock)
        {
            try
            {
                byte[] bytes = Encoding.UTF8.GetBytes(msg + "\n");
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush();
            }
            catch { }
        }
    }

    static void HandleClient(TcpClient client, bool quiet)
    {
        using (client)
        {
            NetworkStream stream = client.GetStream();
            lock (s_sendLock)
            {
                s_activeStreams.Add(stream);
            }

            byte[] inBuffer = new byte[8192];
            int inLen = 0;

            try
            {
                while (s_running && client.Connected)
                {
                    int r = stream.Read(inBuffer, inLen, inBuffer.Length - inLen);
                    if (r <= 0) break;
                    inLen += r;

                    int offset = 0;
                    while (offset < inLen)
                    {
                        // Check if binary packet
                        if (offset + 1 < inLen && inBuffer[offset] == 0x48 && inBuffer[offset + 1] == 0x4D)
                        {
                            // Binary packet is 18 bytes
                            if (offset + 18 <= inLen)
                            {
                                int slot = inBuffer[offset + 2];
                                int cmd = inBuffer[offset + 3];
                                if (cmd == 0x01 && s_controllers.TryGetValue(slot, out var ctrl))
                                {
                                    ushort buttons = BitConverter.ToUInt16(inBuffer, offset + 4);
                                    byte dpad = inBuffer[offset + 6];
                                    byte lt = inBuffer[offset + 7];
                                    byte rt = inBuffer[offset + 8];
                                    short lx = BitConverter.ToInt16(inBuffer, offset + 9);
                                    short ly = BitConverter.ToInt16(inBuffer, offset + 11);
                                    short rx = BitConverter.ToInt16(inBuffer, offset + 13);
                                    short ry = BitConverter.ToInt16(inBuffer, offset + 15);

                                    ApplyState(ctrl, buttons, dpad, lt, rt, lx, ly, rx, ry);
                                }
                                offset += 18;
                                continue;
                            }
                            else
                            {
                                break; // wait for more bytes
                            }
                        }

                        // Otherwise text command: find '\n'
                        int nlIdx = -1;
                        for (int i = offset; i < inLen; i++)
                        {
                            if (inBuffer[i] == (byte)'\n')
                            {
                                nlIdx = i;
                                break;
                            }
                        }

                        if (nlIdx != -1)
                        {
                            string line = Encoding.UTF8.GetString(inBuffer, offset, nlIdx - offset).Trim();
                            offset = nlIdx + 1;
                            if (!string.IsNullOrEmpty(line))
                            {
                                ProcessTextCommand(line, stream, quiet);
                            }
                        }
                        else
                        {
                            break; // wait for newline
                        }
                    }

                    // Shift remaining unparsed bytes to beginning
                    if (offset > 0)
                    {
                        int remaining = inLen - offset;
                        if (remaining > 0)
                        {
                            Buffer.BlockCopy(inBuffer, offset, inBuffer, 0, remaining);
                        }
                        inLen = remaining;
                    }
                }
            }
            catch (Exception ex)
            {
                if (!quiet) Console.WriteLine($"[-] Cliente desconectado: {ex.Message}");
            }
            finally
            {
                lock (s_sendLock)
                {
                    s_activeStreams.Remove(stream);
                }
            }
        }
    }

    static void ProcessTextCommand(string line, Stream stream, bool quiet)
    {
        string[] parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0) return;

        string cmd = parts[0].ToUpperInvariant();

        switch (cmd)
        {
            case "PING":
                SendResponse(stream, IsElevated() ? "PONG ELEVATED" : "PONG NOT_ELEVATED");
                break;

            case "IS_ELEVATED":
                SendResponse(stream, IsElevated() ? "YES" : "NO");
                break;

            case "IS_DRIVER_INSTALLED":
                bool installed = s_ctx?.IsDriverInstalled ?? false;
                SendResponse(stream, installed ? "YES" : "NO");
                break;

            case "INSTALL_DRIVER":
                try
                {
                    if (!IsElevated())
                    {
                        SendResponse(stream, "ERROR Requiere privilegios de Administrador para instalar el driver.");
                        return;
                    }
                    s_ctx?.InstallDriver();
                    SendResponse(stream, "OK");
                }
                catch (Exception ex)
                {
                    SendResponse(stream, $"ERROR {ex.Message}");
                }
                break;

            case "ADD":
                if (parts.Length < 3)
                {
                    SendResponse(stream, "ERROR Uso: ADD <slot> <profile_id>");
                    return;
                }
                if (!int.TryParse(parts[1], out int addSlot))
                {
                    SendResponse(stream, "ERROR Slot invalido");
                    return;
                }
                string profileId = parts[2];
                try
                {
                    if (s_ctx == null)
                    {
                        SendResponse(stream, "ERROR Contexto no inicializado");
                        return;
                    }

                    // Ensure driver installed
                    if (!s_ctx.IsDriverInstalled)
                    {
                        if (IsElevated())
                        {
                            try
                            {
                                s_ctx.InstallDriver();
                            }
                            catch (Exception ex)
                            {
                                SendResponse(stream, $"ERROR Instalando driver: {ex.Message}");
                                return;
                            }
                        }
                        else
                        {
                            SendResponse(stream, "ERROR_DRIVER_NOT_INSTALLED");
                            return;
                        }
                    }

                    var profile = s_ctx.GetProfile(profileId);
                    if (profile == null)
                    {
                        SendResponse(stream, $"ERROR Perfil '{profileId}' no encontrado");
                        return;
                    }

                    // Dispose previous if any
                    if (s_controllers.TryRemove(addSlot, out var oldCtrl))
                    {
                        try { oldCtrl.Dispose(); } catch { }
                    }

                    var ctrl = s_ctx.CreateController(profile, $"slot{addSlot}");
                    
                    void BroadcastRumble(byte left, byte right)
                    {
                        lock (s_sendLock)
                        {
                            byte[] bytes = Encoding.UTF8.GetBytes($"RUMBLE {addSlot} {left} {right}\n");
                            for (int sIdx = s_activeStreams.Count - 1; sIdx >= 0; sIdx--)
                            {
                                try
                                {
                                    s_activeStreams[sIdx].Write(bytes, 0, bytes.Length);
                                    s_activeStreams[sIdx].Flush();
                                }
                                catch
                                {
                                    s_activeStreams.RemoveAt(sIdx);
                                }
                            }
                        }
                    }

                    // 1. Decoded HID rumble (Sony DualShock 4 / DualSense / Switch)
                    ctrl.OutputDecoded += (c, e) =>
                    {
                        byte left = 0, right = 0;
                        if (e.Fields.TryGetValue("leftMotor", out var lm) && lm is byte b1) left = b1;
                        if (e.Fields.TryGetValue("rightMotor", out var rm) && rm is byte b2) right = b2;
                        BroadcastRumble(left, right);
                    };

                    // 2. Direct XInput rumble (Xbox 360 / Xbox One / Xbox Series)
                    ctrl.OutputReceived += (c, pkt) =>
                    {
                        if (pkt.Source == HMOutputSource.XInput && pkt.Data.Length >= 4)
                        {
                            var span = pkt.Data.Span;
                            byte left = span[2];
                            byte right = span[3];
                            BroadcastRumble(left, right);
                        }
                    };

                    s_controllers[addSlot] = ctrl;
                    if (!quiet) Console.WriteLine($"[+] Mando creado en slot {addSlot}: {profile.Name} ({profile.Id})");
                    SendResponse(stream, $"OK {addSlot}");
                }
                catch (Exception ex)
                {
                    SendResponse(stream, $"ERROR {ex.Message}");
                }
                break;

            case "REMOVE":
                if (parts.Length < 2 || !int.TryParse(parts[1], out int remSlot))
                {
                    SendResponse(stream, "ERROR Uso: REMOVE <slot>");
                    return;
                }
                if (s_controllers.TryRemove(remSlot, out var remCtrl))
                {
                    try { remCtrl.Dispose(); } catch { }
                    if (!quiet) Console.WriteLine($"[-] Mando removido de slot {remSlot}.");
                    SendResponse(stream, $"OK {remSlot}");
                }
                else
                {
                    SendResponse(stream, $"OK {remSlot}");
                }
                break;

            case "REMOVE_ALL":
                foreach (var kvp in s_controllers)
                {
                    try { kvp.Value.Dispose(); } catch { }
                }
                s_controllers.Clear();
                SendResponse(stream, "OK");
                break;

            case "SET":
                if (parts.Length >= 10 && int.TryParse(parts[1], out int sSlot))
                {
                    if (s_controllers.TryGetValue(sSlot, out var setCtrl))
                    {
                        ushort btns = Convert.ToUInt16(parts[2], 16);
                        byte dpad = byte.Parse(parts[3]);
                        byte lt = byte.Parse(parts[4]);
                        byte rt = byte.Parse(parts[5]);
                        short lx = short.Parse(parts[6]);
                        short ly = short.Parse(parts[7]);
                        short rx = short.Parse(parts[8]);
                        short ry = short.Parse(parts[9]);

                        ApplyState(setCtrl, btns, dpad, lt, rt, lx, ly, rx, ry);
                    }
                }
                break;

            case "QUIT":
                SendResponse(stream, "OK");
                s_running = false;
                Cleanup();
                Environment.Exit(0);
                break;

            default:
                SendResponse(stream, $"ERROR Comando desconocido '{cmd}'");
                break;
        }
    }

    static void ApplyState(HMController ctrl, ushort buttons, byte dpad, byte lt, byte rt, short lx, short ly, short rx, short ry)
    {
        HMButton btnMask = HMButton.None;
        if ((buttons & (1 << 0)) != 0) btnMask |= HMButton.A;
        if ((buttons & (1 << 1)) != 0) btnMask |= HMButton.B;
        if ((buttons & (1 << 2)) != 0) btnMask |= HMButton.X;
        if ((buttons & (1 << 3)) != 0) btnMask |= HMButton.Y;
        if ((buttons & (1 << 4)) != 0) btnMask |= HMButton.LeftBumper;
        if ((buttons & (1 << 5)) != 0) btnMask |= HMButton.RightBumper;
        if ((buttons & (1 << 6)) != 0) btnMask |= HMButton.Back;
        if ((buttons & (1 << 7)) != 0) btnMask |= HMButton.Start;
        if ((buttons & (1 << 8)) != 0) btnMask |= HMButton.LeftStick;
        if ((buttons & (1 << 9)) != 0) btnMask |= HMButton.RightStick;
        if ((buttons & (1 << 10)) != 0) btnMask |= HMButton.Guide;
        if ((buttons & (1 << 11)) != 0) btnMask |= HMButton.Touchpad;
        if ((buttons & (1 << 12)) != 0) btnMask |= HMButton.Share;

        HMHat hat = dpad switch
        {
            1 => HMHat.North,
            2 => HMHat.South,
            3 => HMHat.West,
            4 => HMHat.East,
            5 => HMHat.NorthEast,
            6 => HMHat.SouthEast,
            7 => HMHat.SouthWest,
            8 => HMHat.NorthWest,
            _ => HMHat.None
        };

        float flx = ((float)lx + 32768f) / 65535f;
        // Invert Y for standard DirectX / HID (up = 1, down = 0)
        float fly = ((- (float)ly) + 32768f) / 65535f;
        float frx = ((float)rx + 32768f) / 65535f;
        float fry = ((- (float)ry) + 32768f) / 65535f;
        float flt = (float)lt / 255f;
        float frt = (float)rt / 255f;

        var axes = HMGamepadStateHelpers.StandardAxes(ctrl.Profile,
            leftStickX: flx,
            leftStickY: fly,
            rightStickX: frx,
            rightStickY: fry,
            leftTrigger: flt,
            rightTrigger: frt);

        var state = new HMGamepadState
        {
            Axes = axes,
            Buttons = btnMask,
            Hat = hat
        };

        ctrl.SubmitState(in state);
    }
}
