"""Small, explicit-Apply interface. Tk is used only on the main thread."""
import queue
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, ttk
import json

from .protocol import LightingError, parse_color
from .service import Settings, run_bounded
from . import __version__


class App:
    def __init__(self, root):
        self.root = root
        self.settings = Settings.default()
        self.results = queue.Queue()
        self.busy = False
        self.ready = False
        self.diagnostics = None
        self.root.title(f"K621 Static Color {__version__}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        panel = ttk.Frame(root, padding=24)
        panel.grid()
        ttk.Label(panel, text="One color. All keys.", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(panel, text="Redragon K621-RGB HORUS · USB", foreground="#626262").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(5, 22))
        self.color = tk.StringVar(value=self.settings.load())
        self.preview = tk.Canvas(panel, width=76, height=64, highlightthickness=1,
                                 highlightbackground="#CCCCCC", background=self.color.get())
        self.preview.grid(row=2, column=0, rowspan=2, padx=(0, 16))
        ttk.Label(panel, text="Color hex").grid(row=2, column=1, sticky="w")
        self.entry = ttk.Entry(panel, textvariable=self.color, width=15, font=("Consolas", 13))
        self.entry.grid(row=3, column=1, sticky="w")
        self.pick_button = ttk.Button(panel, text="Choose color…", command=self.pick)
        self.pick_button.grid(row=3, column=2, padx=(14, 0))
        self.validation = tk.StringVar()
        ttk.Label(panel, textvariable=self.validation, foreground="#A32323").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.apply_button = ttk.Button(panel, text="Apply to keyboard", command=self.apply, state="disabled")
        self.apply_button.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(14, 16))
        self.status = tk.StringVar(value="Checking USB connection…")
        ttk.Label(panel, textvariable=self.status, wraplength=390, justify="left").grid(
            row=6, column=0, columnspan=3, sticky="w")
        actions = ttk.Frame(panel)
        actions.grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 16))
        self.refresh_button = ttk.Button(actions, text="Refresh connection", command=self.refresh)
        self.refresh_button.pack(side="left")
        self.save_button = ttk.Button(actions, text="Save diagnostics…", command=self.save_diagnostics, state="disabled")
        self.save_button.pack(side="left", padx=(8, 0))
        ttk.Label(panel, text=f"v{__version__} · Apply once, then close.", foreground="#626262").grid(
            row=8, column=0, columnspan=3, sticky="w")
        self.color.trace_add("write", lambda *_: self.validate())
        self.root.after(60, self.poll)
        self.refresh()

    def validate(self):
        try:
            parse_color(self.color.get())
            self.preview.configure(background=self.color.get())
            self.validation.set("")
            valid = True
        except LightingError:
            self.validation.set("Use six hex digits, for example #4A90E2.")
            valid = False
        self.apply_button.configure(state="normal" if valid and self.ready and not self.busy else "disabled")
        return valid

    def pick(self):
        result = colorchooser.askcolor(color=self.preview.cget("background"), title="Choose keyboard color", parent=self.root)
        if result[1]:
            self.color.set(result[1].upper())

    def start(self, operation, args, color=None):
        if self.busy:
            return
        self.busy = True
        for widget in (self.entry, self.pick_button, self.apply_button, self.refresh_button, self.save_button):
            widget.configure(state="disabled")

        def worker():
            try:
                result = run_bounded(*args)
                self.results.put((operation, result, None, color))
            except Exception as exc:
                self.results.put((operation, None, str(exc), color))

        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        if not self.busy:
            self.status.set("Checking USB connection…")
            self.start("diagnose", ("--diagnose",))

    def apply(self):
        if self.busy or not self.ready or not self.validate():
            return
        color = self.color.get().upper()
        self.status.set("Applying color…")
        self.start("apply", ("--worker-apply", color), color)

    def poll(self):
        try:
            operation, result, error, color = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.entry.configure(state="normal")
            self.pick_button.configure(state="normal")
            self.refresh_button.configure(state="normal")
            if error:
                self.ready = False
                self.status.set(error)
            elif operation == "diagnose":
                self.diagnostics = result
                self.ready = result["ready"]
                self.status.set(result["status"])
            else:
                self.status.set(result["status"] + " You can close the app.")
                try:
                    self.settings.save(color)
                except OSError:
                    self.status.set(result["status"] + " Could not remember this color locally.")
            self.save_button.configure(state="normal" if self.diagnostics else "disabled")
            self.validate()
        self.root.after(60, self.poll)

    def save_diagnostics(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Save read-only device diagnostics",
                                          initialfile="k621-diagnostics.json", defaultextension=".json",
                                          filetypes=[("JSON", "*.json")])
        if path:
            try:
                from pathlib import Path
                Path(path).write_text(json.dumps(self.diagnostics, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                self.status.set(f"Could not save diagnostics: {exc}")

    def close(self):
        if self.busy:
            self.status.set("Wait for the current operation to finish (up to 15 seconds), then close.")
        else:
            self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
