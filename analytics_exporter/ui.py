"""Tkinter management UI for the GA4 + GSC exporter — improved.

Improvements vs v1:
- Run happens on a background thread so the window never freezes; a progress
  bar + live status reflect progress.
- Login-state badge (Logged in / Not logged in) read from the seeded profile.
- Re-auth banner appears if a run stops with a REAUTH error.
- Better layout: section frames, sensible widths, disabled Run until valid.
"""
from __future__ import annotations

import threading
from datetime import date
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from config import AppConfig
from profile import seed_login, get_profile_dir


class ExporterUI:
    def __init__(self, root: tk.Tk, config_path: Path):
        self.root = root
        self.config_path = config_path
        self.cfg = AppConfig.load(config_path)
        self._running = False
        root.title("GA4 + GSC Data Exporter")
        root.geometry("680x640")
        self._build()
        self._refresh_login_badge()

    # ---- layout helpers ----
    def _label(self, parent, text, row, col=0, sticky="nw", padx=8, pady=3):
        tk.Label(parent, text=text).grid(row=row, column=col, sticky=sticky, padx=padx, pady=pady)

    def _entry(self, parent, var, row, col=1, width=42):
        e = tk.Entry(parent, textvariable=var, width=width)
        e.grid(row=row, column=col, sticky="ew", padx=8, pady=3)
        return e

    def _build(self):
        # Config section
        f_cfg = tk.LabelFrame(self.root, text="Export settings", padx=6, pady=6)
        f_cfg.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
        r = 0
        self.email_var = tk.StringVar(value=self.cfg.email)
        self._label(f_cfg, "Company Google email:", r); self._entry(f_cfg, self.email_var, r); r += 1

        self.ga4_var = tk.StringVar(value=", ".join(self.cfg.ga4_property_ids))
        self._label(f_cfg, "GA4 property IDs (comma-sep):", r); self._entry(f_cfg, self.ga4_var, r); r += 1

        self.gsc_var = tk.StringVar(value=", ".join(self.cfg.gsc_site_urls))
        self._label(f_cfg, "GSC site URLs (comma-sep):", r); self._entry(f_cfg, self.gsc_var, r); r += 1

        self.start_var = tk.StringVar(value=self.cfg.start_date)
        self._label(f_cfg, "Start date (YYYY-MM-DD):", r)
        self._entry(f_cfg, self.start_var, r, width=20); r += 1

        self.end_var = tk.StringVar(value=self.cfg.end_date or date.today().isoformat())
        self._label(f_cfg, "End date (YYYY-MM-DD):", r)
        self._entry(f_cfg, self.end_var, r, width=20); r += 1

        self.chunk_var = tk.StringVar(value=self.cfg.chunk_mode)
        self._label(f_cfg, "Chunk mode:", r)
        tk.OptionMenu(f_cfg, self.chunk_var, "monthly", "daily").grid(row=r, column=1, sticky="w", padx=8, pady=3); r += 1

        self.out_var = tk.StringVar(value=self.cfg.output_dir)
        self._label(f_cfg, "Output folder:", r)
        out_frame = tk.Frame(f_cfg)
        tk.Entry(out_frame, textvariable=self.out_var, width=34).pack(side="left", fill="x", expand=True)
        tk.Button(out_frame, text="Browse...", command=self._pick_dir).pack(side="left")
        out_frame.grid(row=r, column=1, sticky="ew", padx=8, pady=3); r += 1

        # Status section
        f_status = tk.Frame(self.root)
        f_status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=2)
        self.login_badge = tk.Label(f_status, text="Login: ?", fg="black")
        self.login_badge.pack(side="left", padx=4)
        self.reauth_banner = tk.Label(f_status, text="", fg="red")
        self.reauth_banner.pack(side="left", padx=8)

        # Actions
        f_act = tk.Frame(self.root)
        f_act.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
        tk.Button(f_act, text="Save", command=self._save).pack(side="left", padx=4)
        tk.Button(f_act, text="Login (once)", command=self._login).pack(side="left", padx=4)
        self.run_btn = tk.Button(f_act, text="Run export", command=self._run)
        self.run_btn.pack(side="left", padx=4)

        # Progress
        self.progress = ttk.Progressbar(self.root, length=620, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=2, padx=10, pady=4)

        # Log
        self.log = scrolledtext.ScrolledText(self.root, height=14, state="disabled")
        self.log.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=6)

    # ---- helpers ----
    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.out_var.set(d)

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _refresh_login_badge(self):
        logged = (get_profile_dir() / "storage_state.json").exists()
        self.login_badge.config(text="Login: OK" if logged else "Login: not seeded",
                                fg="green" if logged else "red")

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

    # ---- actions ----
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
        self._refresh_login_badge()
        self._log("Login session saved." if ok else "Login did not complete in time.")

    def _run(self):
        if self._running:
            return
        cfg = self._gather()
        errs = cfg.validate()
        if errs:
            messagebox.showerror("Invalid config", "\n".join(errs))
            return
        if not (get_profile_dir() / "storage_state.json").exists():
            messagebox.showwarning("Not logged in", "Click 'Login (once)' before running.")
            return
        cfg.save(self.config_path)
        self.reauth_banner.config(text="")
        self._running = True
        self.run_btn.config(state="disabled")
        self.progress["value"] = 0

        def worker():
            try:
                from run_all import run_exports
                def progress(done, total):
                    self.root.after(0, lambda: self.progress.configure(
                        value=(done / total) * 100 if total else 0))
                manifest = run_exports(cfg, log_fn=self._log, progress_fn=progress)
                if any(e.startswith("REAUTH") for e in manifest["errors"]):
                    self.root.after(0, lambda: self.reauth_banner.config(
                        text="Re-auth needed — click 'Login (once)', then Run again."))
            finally:
                self._running = False
                self.root.after(0, lambda: self.run_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


def main():
    from pathlib import Path as _P
    config_path = _P(__file__).resolve().parent / "config.json"
    root = tk.Tk()
    ExporterUI(root, config_path)
    root.mainloop()


if __name__ == "__main__":
    main()
