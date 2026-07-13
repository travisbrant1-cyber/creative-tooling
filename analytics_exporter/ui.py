"""Tkinter management UI for the GA4 + GSC exporter.

Collects: company email, GA4 property IDs, GSC site URLs, date range,
chunk mode (monthly/daily), and an output directory the user picks.
The "Login" button triggers the one-time seed login; "Run" starts exports.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from datetime import date

from config import AppConfig
from profile import seed_login, get_profile_dir

CONFIG_PATH = None  # set by main()


class ExporterUI:
    def __init__(self, root: tk.Tk, config_path):
        self.root = root
        self.config_path = config_path
        self.cfg = AppConfig.load(config_path)
        root.title("GA4 + GSC Data Exporter")
        root.geometry("620x560")
        self._build()

    def _row(self, label, row, widget):
        tk.Label(self.root, text=label).grid(row=row, column=0, sticky="nw", padx=8, pady=4)
        widget.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

    def _build(self):
        r = 0
        self.email_var = tk.StringVar(value=self.cfg.email)
        self._row("Company Google email:", r, tk.Entry(self.root, textvariable=self.email_var, width=40)); r += 1

        self.ga4_var = tk.StringVar(value=", ".join(self.cfg.ga4_property_ids))
        self._row("GA4 property IDs (comma-sep):", r, tk.Entry(self.root, textvariable=self.ga4_var, width=40)); r += 1

        self.gsc_var = tk.StringVar(value=", ".join(self.cfg.gsc_site_urls))
        self._row("GSC site URLs (comma-sep):", r, tk.Entry(self.root, textvariable=self.gsc_var, width=40)); r += 1

        self.start_var = tk.StringVar(value=self.cfg.start_date)
        self._row("Start date (YYYY-MM-DD):", r, tk.Entry(self.root, textvariable=self.start_var, width=20)); r += 1

        self.end_var = tk.StringVar(value=self.cfg.end_date or date.today().isoformat())
        self._row("End date (YYYY-MM-DD):", r, tk.Entry(self.root, textvariable=self.end_var, width=20)); r += 1

        self.chunk_var = tk.StringVar(value=self.cfg.chunk_mode)
        self._row("Chunk mode:", r, tk.OptionMenu(self.root, self.chunk_var, "monthly", "daily")); r += 1

        self.out_var = tk.StringVar(value=self.cfg.output_dir)
        out_frame = tk.Frame(self.root)
        tk.Entry(out_frame, textvariable=self.out_var, width=32).pack(side="left", fill="x", expand=True)
        tk.Button(out_frame, text="Browse...", command=self._pick_dir).pack(side="left")
        self._row("Output folder:", r, out_frame); r += 1

        btn_frame = tk.Frame(self.root)
        tk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Login (once)", command=self._login).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Run export", command=self._run).pack(side="left", padx=4)
        self._row("Actions:", r, btn_frame); r += 1

        self.log = scrolledtext.ScrolledText(self.root, height=12, state="disabled")
        self.log.grid(row=r, column=0, columnspan=2, sticky="ew", padx=8, pady=8)

    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.out_var.set(d)

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _gather(self) -> AppConfig:
        return AppConfig(
            email=self.email_var.get().strip(),
            ga4_property_ids=[s.strip() for s in self.ga4_var.get().split(",") if s.strip()],
            gsc_site_urls=[s.strip() for s in self.gsc_var.get().split(",") if s.strip()],
            start_date=self.start_var.get().strip(),
            end_date=self.end_var.get().strip(),
            chunk_mode=self.chunk_var.get(),  # type: ignore[arg-type]
            output_dir=self.out_var.get().strip(),
            profile_dir=get_profile_dir().as_posix(),
        )

    def _save(self):
        cfg = self._gather()
        errs = cfg.validate()
        if errs:
            messagebox.showerror("Invalid config", "\n".join(errs))
            return
        cfg.save(self.config_path)
        self._log("Config saved.")

    def _login(self):
        cfg = self._gather()
        if not cfg.email:
            messagebox.showerror("Missing email", "Enter your company Google email first.")
            return
        self._log("Opening browser for one-time login (enter password in Google's page)...")
        ok = seed_login(cfg.email, get_profile_dir())
        self._log("Login session saved." if ok else "Login did not complete in time.")

    def _run(self):
        cfg = self._gather()
        errs = cfg.validate()
        if errs:
            messagebox.showerror("Invalid config", "\n".join(errs))
            return
        cfg.save(self.config_path)
        self._log("Starting export (verify on Mac)...")
        # Imported here so UI loads even if run_all has Mac-only deps missing.
        from run_all import run_exports
        run_exports(cfg, log_fn=self._log)


def main():
    global CONFIG_PATH
    from pathlib import Path
    CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
    root = tk.Tk()
    ExporterUI(root, CONFIG_PATH)
    root.mainloop()


if __name__ == "__main__":
    main()
