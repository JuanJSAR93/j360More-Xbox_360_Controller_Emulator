"""
plugins/plugin_ui_renderer.py
Declarative UI renderer for j360More plugins using Tkinter.
Constructs global configuration dialogs and per-pad calibration tabs
directly from plugin.json JSON schemas.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional


class PluginUIRenderer:
    """Renders declarative widgets from JSON schema definitions."""

    @staticmethod
    def render_fields(
        parent: tk.Widget,
        fields: List[Dict[str, Any]],
        current_values: Dict[str, Any],
        on_field_change: Optional[Callable[[str, Any], None]] = None,
        on_action: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Renders a list of fields into parent container.
        Returns a dict of widget references: {field_id: {'widget': ..., 'var': ...}}
        """
        rendered_refs = {}

        for row_idx, field in enumerate(fields):
            f_id = field.get("id")
            f_type = field.get("type", "slider")
            label_text = field.get("label", f_id)
            default_val = field.get("default")
            curr_val = current_values.get(f_id, default_val)

            row_frame = ttk.Frame(parent)
            row_frame.pack(fill=tk.X, padx=8, pady=4)

            if f_type == "slider":
                f_min = float(field.get("min", 0))
                f_max = float(field.get("max", 100))
                init_val = float(curr_val if curr_val is not None else f_min)

                lbl = ttk.Label(row_frame, text=label_text, width=28, anchor="w")
                lbl.pack(side=tk.LEFT)

                val_var = tk.DoubleVar(value=init_val)
                val_lbl = ttk.Label(row_frame, text=f"{int(init_val)}", width=6, anchor="e")

                def make_slider_cb(fid=f_id, vvar=val_var, vlbl=val_lbl):
                    def _cb(val):
                        ival = int(float(val))
                        vlbl.config(text=f"{ival}")
                        if on_field_change:
                            on_field_change(fid, ival)
                    return _cb

                scale = ttk.Scale(
                    row_frame,
                    from_=f_min,
                    to=f_max,
                    variable=val_var,
                    command=make_slider_cb()
                )
                scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
                val_lbl.pack(side=tk.RIGHT)

                rendered_refs[f_id] = {"widget": scale, "var": val_var, "val_lbl": val_lbl}

            elif f_type == "checkbox":
                init_val = bool(curr_val if curr_val is not None else False)
                chk_var = tk.BooleanVar(value=init_val)

                def make_chk_cb(fid=f_id, cvar=chk_var):
                    return lambda: on_field_change(fid, cvar.get()) if on_field_change else None

                chk = ttk.Checkbutton(
                    row_frame,
                    text=label_text,
                    variable=chk_var,
                    command=make_chk_cb()
                )
                chk.pack(side=tk.LEFT, padx=2)
                rendered_refs[f_id] = {"widget": chk, "var": chk_var}

            elif f_type in ("dropdown", "dynamic_dropdown"):
                lbl = ttk.Label(row_frame, text=label_text, width=28, anchor="w")
                lbl.pack(side=tk.LEFT)

                options = list(field.get("options", []))
                combo_var = tk.StringVar(value=str(curr_val if curr_val is not None else (options[0] if options else "")))

                combo = ttk.Combobox(
                    row_frame,
                    textvariable=combo_var,
                    values=options,
                    state="readonly"
                )
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

                def make_combo_cb(fid=f_id, cvar=combo_var):
                    def _cb(ev):
                        if on_field_change:
                            on_field_change(fid, cvar.get())
                    return _cb

                combo.bind("<<ComboboxSelected>>", make_combo_cb())

                # Discovery refresh button if action is declared
                disc_action = field.get("discovery_action")
                if disc_action:
                    btn_refresh = ttk.Button(
                        row_frame,
                        text="🔄",
                        width=3,
                        command=lambda act=disc_action: on_action(act) if on_action else None
                    )
                    btn_refresh.pack(side=tk.RIGHT, padx=2)

                rendered_refs[f_id] = {"widget": combo, "var": combo_var}

            elif f_type == "button":
                act_name = field.get("action", f_id)
                btn = ttk.Button(
                    row_frame,
                    text=label_text,
                    command=lambda act=act_name: on_action(act) if on_action else None
                )
                btn.pack(side=tk.LEFT, padx=4, pady=2)
                rendered_refs[f_id] = {"widget": btn}

            elif f_type in ("progress_bar_multi", "progress_bar_pair"):
                lbl = ttk.Label(row_frame, text=label_text, font=("Segoe UI", 9, "bold"))
                lbl.pack(side=tk.TOP, anchor="w", pady=(2, 4))

                canvas_h = 32
                canvas = tk.Canvas(row_frame, height=canvas_h, bg="#1e1e1e", highlightthickness=1, highlightbackground="#333333")
                canvas.pack(fill=tk.X, expand=True, pady=2)

                rendered_refs[f_id] = {
                    "widget": canvas,
                    "type": f_type,
                    "labels": field.get("labels", [])
                }

        return rendered_refs

    @staticmethod
    def update_telemetry_widget(ref_data: Dict[str, Any], values: List[float]):
        """Updates canvas bars in real-time with telemetry array (e.g. [gas, brake, clutch])."""
        widget = ref_data.get("widget")
        if not isinstance(widget, tk.Canvas):
            return

        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return

        w = widget.winfo_width()
        if w <= 1:
            w = widget.winfo_reqwidth()
        if w <= 1:
            try:
                w = widget.master.winfo_width()
            except Exception:
                w = 1
        if w <= 1:
            w = 380

        h = widget.winfo_height()
        if h <= 1:
            h = widget.winfo_reqheight()
        if h <= 1:
            h = 32

        widget.delete("all")
        if not values:
            return

        num_bars = len(values)
        bar_w = (w - (num_bars + 1) * 8) / max(1, num_bars)
        colors = ["#107C41", "#0078D7", "#FFB900", "#E81123", "#B4009E"]

        custom_labels = ref_data.get("labels") or []

        for i, val in enumerate(values):
            clamped = max(0.0, min(1.0, float(val)))
            x0 = 8 + i * (bar_w + 8)
            x1 = x0 + bar_w
            fill_h = (h - 8) * clamped
            y0 = h - 4 - fill_h
            y1 = h - 4

            color = colors[i % len(colors)]
            # Background track
            widget.create_rectangle(x0, 4, x1, h - 4, fill="#2d2d2d", outline="")
            # Active fill
            if clamped > 0.005:
                widget.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

            # Label text
            if i < len(custom_labels):
                lbl_txt = custom_labels[i]
            else:
                default_labels = ["GAS", "BRK", "CLT", "AUX1", "AUX2"]
                lbl_txt = default_labels[i] if i < len(default_labels) else f"CH{i+1}"
            widget.create_text((x0 + x1) / 2, h / 2, text=f"{lbl_txt} {int(clamped * 100)}%", fill="#ffffff", font=("Segoe UI", 8, "bold"))
