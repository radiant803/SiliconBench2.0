import tkinter as tk
from tkinter import ttk, messagebox
import threading
import platform
import multiprocessing
import base64
import time

from benchmark_engine import BenchmarkEngine
from stress_engine import StressController, RenderStressController
from stability_engine import StabilityController

REFERENCE_SCORES = [
    ("Apple M2",       72,  445, 1245),
    ("Core i5-7400T",  43,  155,  527),
    ("Core i3-4130",   37,   73,  381),
]

POLL_MS = 400


def _make_ppm_photo(gray_bytes, width, height, scale=2):
    """Convert raw grayscale bytes to a tkinter PhotoImage via in-memory PPM."""
    w, h = width * scale, height * scale
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            v = gray_bytes[y * width + x]
            for _ in range(scale):
                row += bytes([v, v, v])
        for _ in range(scale):
            rows.append(bytes(row))
    ppm = header + b"".join(rows)
    return tk.PhotoImage(data=base64.b64encode(ppm).decode("ascii"))


class SiliconBenchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SiliconBench 2-Go — Pure-Python Benchmark")
        self.root.geometry("860x640")
        self.root.configure(bg="#202020")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame",        background="#202020")
        style.configure("TLabel",        background="#202020", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#00aaff")
        style.configure("Sub.TLabel",    font=("Segoe UI", 9),  foreground="#888888")
        style.configure("ScoreBox.TLabel", font=("Segoe UI", 24, "bold"), foreground="#ffffff")
        style.configure("ScoreTitle.TLabel", font=("Segoe UI", 10, "bold"), foreground="#aaaaaa")
        style.configure("TCheckbutton",  background="#202020", foreground="#e0e0e0")
        style.configure("TButton",       font=("Segoe UI", 10, "bold"), background="#333333", foreground="#ffffff")
        style.configure("TRadiobutton",  background="#202020", foreground="#e0e0e0")
        style.configure("TNotebook",     background="#202020", tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background="#2c2c2c", foreground="#aaaaaa",
                        font=("Segoe UI", 10, "bold"), padding=[16, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", "#0055cc")],
                  foreground=[("selected", "#ffffff")])
        style.configure("TProgressbar",  troughcolor="#333333", background="#00aaff")
        style.configure("TLabelframe",   background="#202020", foreground="#aaaaaa")
        style.configure("TLabelframe.Label", background="#202020", foreground="#aaaaaa")
        style.configure("TSpinbox",      background="#2c2c2c", foreground="#e0e0e0",
                        fieldbackground="#2c2c2c", insertcolor="#e0e0e0")

        # Header
        hdr = ttk.Frame(root)
        hdr.pack(fill=tk.X, padx=20, pady=12)
        ttk.Label(hdr, text="SILICONBENCH 2-GO", style="Header.TLabel").pack(side=tk.LEFT)
        sys_info = f"{platform.system()} · {platform.machine()} · {multiprocessing.cpu_count()} Cores"
        ttk.Label(hdr, text=sys_info, style="Sub.TLabel").pack(side=tk.RIGHT, pady=10)

        # Tab notebook
        nb = ttk.Notebook(root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.bench_frame = ttk.Frame(nb)
        self.stress_frame = ttk.Frame(nb)
        self.stab_frame = ttk.Frame(nb)
        nb.add(self.bench_frame, text="  Benchmark  ")
        nb.add(self.stress_frame, text="  Stress Test  ")
        nb.add(self.stab_frame, text="  Stability Test  ")

        self._build_benchmark_tab()
        self._build_stress_tab()
        self._build_stability_tab()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────
    #  BENCHMARK TAB
    # ─────────────────────────────────────────────────────────
    def _build_benchmark_tab(self):
        f = self.bench_frame

        # Options row
        opts = ttk.Frame(f)
        opts.pack(fill=tk.X, padx=20, pady=8)
        self.var_sc = tk.BooleanVar(value=True)
        self.var_mc = tk.BooleanVar(value=True)
        self.var_ex = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Single-Core",           variable=self.var_sc).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(opts, text="Multi-Core (Throughput)", variable=self.var_mc).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(opts, text="System Scaling",        variable=self.var_ex).pack(side=tk.LEFT, padx=8)
        self.bench_run_btn = ttk.Button(opts, text="RUN BENCHMARK", command=self._start_benchmark)
        self.bench_run_btn.pack(side=tk.RIGHT, padx=8)

        # Score boxes
        score_row = ttk.Frame(f)
        score_row.pack(fill=tk.X, padx=30, pady=12)
        for col in range(3):
            score_row.columnconfigure(col, weight=1)

        def _score_box(parent, col, title, attr):
            box = tk.Frame(parent, bg="#2a2a2a", bd=2, relief="groove")
            box.grid(row=0, column=col, padx=8, sticky="ew")
            ttk.Label(box, text=title, style="ScoreTitle.TLabel").pack(pady=(8, 0))
            lbl = tk.Label(box, text="---", font=("Segoe UI", 24, "bold"),
                           fg="#ffffff", bg="#2a2a2a")
            lbl.pack(pady=(0, 8))
            setattr(self, attr, lbl)

        _score_box(score_row, 0, "SINGLE-CORE", "lbl_sc")
        _score_box(score_row, 1, "MULTI-CORE",  "lbl_mc")
        _score_box(score_row, 2, "SYSTEM",       "lbl_ex")

        # Progress
        prog_row = ttk.Frame(f)
        prog_row.pack(fill=tk.X, padx=20, pady=4)
        self.bench_status = ttk.Label(prog_row, text="Ready to benchmark.")
        self.bench_status.pack(anchor=tk.W)
        self.bench_progress = ttk.Progressbar(prog_row, orient=tk.HORIZONTAL, length=100, mode="determinate")
        self.bench_progress.pack(fill=tk.X, pady=4)

        # Bottom: log + reference panel side by side
        bottom = ttk.Frame(f)
        bottom.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(bottom, text="Activity Log")
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.bench_log = tk.Text(log_frame, bg="#101010", fg="#00ff00",
                                  font=("Consolas", 9), relief="flat", state=tk.DISABLED)
        self.bench_log.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        ref_frame = ttk.LabelFrame(bottom, text="Reference Scores")
        ref_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_reference_panel(ref_frame)

        self.bench_engine = BenchmarkEngine(log_callback=self._bench_log, progress_callback=self._bench_prog)
        self.bench_thread = None

    def _build_reference_panel(self, parent):
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 2))
        for col, (text, w) in enumerate([("System", 14), ("SC", 6), ("MC", 6), ("SYS", 6)]):
            tk.Label(hdr, text=text, fg="#888888", bg="#202020",
                     font=("Segoe UI", 9, "bold"), width=w, anchor="w").grid(row=0, column=col, padx=2)

        for name, sc, mc, sys_s in REFERENCE_SCORES:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, padx=6, pady=1)
            for col, (val, w) in enumerate([(name, 14), (str(sc), 6), (str(mc), 6), (str(sys_s), 6)]):
                tk.Label(row, text=val, fg="#cccccc", bg="#202020",
                         font=("Consolas", 9), width=w, anchor="w").grid(row=0, column=col, padx=2)

        sep = tk.Frame(parent, bg="#444444", height=1)
        sep.pack(fill=tk.X, padx=6, pady=4)

        your_row = ttk.Frame(parent)
        your_row.pack(fill=tk.X, padx=6, pady=1)
        tk.Label(your_row, text="Your System", fg="#00aaff", bg="#202020",
                 font=("Segoe UI", 9, "bold"), width=14, anchor="w").grid(row=0, column=0, padx=2)
        self.ref_your_sc  = tk.Label(your_row, text="---", fg="#00aaff", bg="#202020",
                                      font=("Consolas", 9), width=6, anchor="w")
        self.ref_your_mc  = tk.Label(your_row, text="---", fg="#00aaff", bg="#202020",
                                      font=("Consolas", 9), width=6, anchor="w")
        self.ref_your_sys = tk.Label(your_row, text="---", fg="#00aaff", bg="#202020",
                                      font=("Consolas", 9), width=6, anchor="w")
        self.ref_your_sc.grid(row=0, column=1, padx=2)
        self.ref_your_mc.grid(row=0, column=2, padx=2)
        self.ref_your_sys.grid(row=0, column=3, padx=2)

    def _bench_log(self, msg):
        self.root.after(0, lambda m=msg: self._bench_log_append(m))

    def _bench_log_append(self, msg):
        self.bench_log.config(state=tk.NORMAL)
        self.bench_log.insert(tk.END, msg + "\n")
        self.bench_log.see(tk.END)
        self.bench_log.config(state=tk.DISABLED)
        if "Running" in msg:
            self.bench_status.config(text=msg)

    def _bench_prog(self, current, total):
        self.root.after(0, lambda: self.bench_progress.config(value=(current / total) * 100))

    def _start_benchmark(self):
        if not (self.var_sc.get() or self.var_mc.get() or self.var_ex.get()):
            messagebox.showwarning("Warning", "Select at least one suite!")
            return
        self.bench_run_btn.config(state=tk.DISABLED)
        self.lbl_sc.config(text="---", fg="#ffffff")
        self.lbl_mc.config(text="---", fg="#ffffff")
        self.lbl_ex.config(text="---", fg="#ffffff")
        self.bench_log.config(state=tk.NORMAL)
        self.bench_log.delete(1.0, tk.END)
        self.bench_log.config(state=tk.DISABLED)
        self.bench_thread = threading.Thread(target=self._bench_worker, daemon=True)
        self.bench_thread.start()

    def _bench_worker(self):
        results = self.bench_engine.run_suite(
            run_sc=self.var_sc.get(),
            run_mc=self.var_mc.get(),
            run_extra=self.var_ex.get(),
        )
        self.root.after(0, lambda: self._bench_finish(results))

    def _bench_finish(self, results):
        self.bench_run_btn.config(state=tk.NORMAL)
        self.bench_status.config(text="Benchmark Complete.")
        if results:
            self.lbl_sc.config(text=str(results["sc_score"]),  fg="#00aaff")
            self.lbl_mc.config(text=str(results["mc_score"]),  fg="#00aaff")
            self.lbl_ex.config(text=str(results["extra_score"]), fg="#00aaff")
            self.ref_your_sc.config(text=str(results["sc_score"]))
            self.ref_your_mc.config(text=str(results["mc_score"]))
            self.ref_your_sys.config(text=str(results["extra_score"]))

    # ─────────────────────────────────────────────────────────
    #  STRESS TEST TAB
    # ─────────────────────────────────────────────────────────
    def _build_stress_tab(self):
        f = self.stress_frame

        # Top controls
        ctrl = ttk.Frame(f)
        ctrl.pack(fill=tk.X, padx=20, pady=10)

        # Mode
        mode_lf = ttk.LabelFrame(ctrl, text="Mode")
        mode_lf.pack(side=tk.LEFT, padx=(0, 16))
        self.stress_mode = tk.StringVar(value="prime")
        ttk.Radiobutton(mode_lf, text="Prime Search (Mersenne)",    variable=self.stress_mode, value="prime",
                        command=self._stress_mode_changed).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Radiobutton(mode_lf, text="Rendering (Cinebench-style)", variable=self.stress_mode, value="render",
                        command=self._stress_mode_changed).pack(anchor=tk.W, padx=8, pady=2)

        # Duration
        dur_lf = ttk.LabelFrame(ctrl, text="Duration")
        dur_lf.pack(side=tk.LEFT, padx=(0, 16))
        self.stress_dur = tk.StringVar(value="manual")
        for label, val in [("Manual", "manual"), ("30s", "30"), ("60s", "60"), ("120s", "120")]:
            ttk.Radiobutton(dur_lf, text=label, variable=self.stress_dur, value=val).pack(
                side=tk.LEFT, padx=6, pady=4)

        # Start / Stop
        btn_frame = ttk.Frame(ctrl)
        btn_frame.pack(side=tk.LEFT, padx=8)
        self.stress_start_btn = ttk.Button(btn_frame, text="START", command=self._stress_start)
        self.stress_start_btn.pack(pady=2)
        self.stress_stop_btn = ttk.Button(btn_frame, text="STOP", command=self._stress_stop, state=tk.DISABLED)
        self.stress_stop_btn.pack(pady=2)

        # Stats row
        stats = ttk.Frame(f)
        stats.pack(fill=tk.X, padx=20, pady=4)
        self.stress_stat_labels = {}
        for col, key in enumerate(["Elapsed", "Throughput", "Tests/Frames", "Errors"]):
            box = tk.Frame(stats, bg="#2a2a2a", bd=1, relief="groove")
            box.grid(row=0, column=col, padx=6, sticky="ew")
            stats.columnconfigure(col, weight=1)
            tk.Label(box, text=key.upper(), fg="#888888", bg="#2a2a2a",
                     font=("Segoe UI", 8, "bold")).pack(pady=(6, 0))
            lbl = tk.Label(box, text="---", fg="#00aaff", bg="#2a2a2a",
                           font=("Segoe UI", 14, "bold"))
            lbl.pack(pady=(0, 6))
            self.stress_stat_labels[key] = lbl

        # Core status (prime mode only)
        self.stress_core_frame = ttk.LabelFrame(f, text="Per-Core Status")
        self.stress_core_frame.pack(fill=tk.X, padx=20, pady=4)
        self.stress_core_labels = []
        n_cores = multiprocessing.cpu_count()
        cols_per_row = min(8, n_cores)
        for i in range(n_cores):
            lbl = tk.Label(self.stress_core_frame, text=f"Core {i}: idle",
                           fg="#666666", bg="#202020", font=("Consolas", 8), width=18)
            lbl.grid(row=i // cols_per_row, column=i % cols_per_row, padx=4, pady=2, sticky="w")
            self.stress_core_labels.append(lbl)

        # Output area: activity log (prime) or render canvas (render)
        out_frame = ttk.Frame(f)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)

        self.stress_log = tk.Text(out_frame, bg="#101010", fg="#00ff00",
                                   font=("Consolas", 9), relief="flat", state=tk.DISABLED)
        self.stress_log.pack(fill=tk.BOTH, expand=True)

        # Render preview inside a separate container (shown/hidden via pack)
        self.stress_render_outer = ttk.Frame(out_frame)
        self.stress_render_canvas = tk.Label(self.stress_render_outer, bg="#101010",
                                              text="Waiting for first frame...",
                                              fg="#444444", font=("Consolas", 10))
        self.stress_render_canvas.pack(expand=True)
        self.stress_render_info = tk.Label(self.stress_render_outer, text="",
                                            fg="#00aaff", bg="#101010", font=("Consolas", 9))
        self.stress_render_info.pack()
        self._stress_photo = None  # prevent GC

        self.stress_controller = None
        self.stress_render_controller = None
        self._stress_poll_id = None
        self._stress_auto_stop_at = None

        self._stress_mode_changed()  # set initial visibility

    def _stress_mode_changed(self):
        mode = self.stress_mode.get()
        if mode == "prime":
            self.stress_render_outer.pack_forget()
            self.stress_log.pack(fill=tk.BOTH, expand=True)
            self.stress_core_frame.pack(fill=tk.X, padx=20, pady=4,
                                         before=self.stress_log.master)
        else:
            self.stress_log.pack_forget()
            self.stress_core_frame.pack_forget()
            self.stress_render_outer.pack(fill=tk.BOTH, expand=True)

    def _stress_log_append(self, msg):
        self.stress_log.config(state=tk.NORMAL)
        self.stress_log.insert(tk.END, msg + "\n")
        self.stress_log.see(tk.END)
        self.stress_log.config(state=tk.DISABLED)

    def _stress_start(self):
        mode = self.stress_mode.get()
        self.stress_start_btn.config(state=tk.DISABLED)
        self.stress_stop_btn.config(state=tk.NORMAL)

        # Clear display
        self.stress_log.config(state=tk.NORMAL)
        self.stress_log.delete(1.0, tk.END)
        self.stress_log.config(state=tk.DISABLED)
        for lbl in self.stress_stat_labels.values():
            lbl.config(text="---", fg="#00aaff")
        for lbl in self.stress_core_labels:
            lbl.config(text=f"Core {self.stress_core_labels.index(lbl)}: starting…", fg="#888888")

        # Auto-stop timer
        dur = self.stress_dur.get()
        self._stress_auto_stop_at = (time.perf_counter() + int(dur)) if dur != "manual" else None

        if mode == "prime":
            self.stress_controller = StressController()
            self.stress_controller.start()
        else:
            self.stress_render_controller = RenderStressController()
            self.stress_render_controller.start()
            self.stress_render_canvas.config(text="Waiting for first frame…", image="")

        self._stress_poll()

    def _stress_stop(self):
        self._stress_cancel_poll()
        if self.stress_controller and self.stress_controller.running:
            threading.Thread(target=self.stress_controller.stop, daemon=True).start()
        if self.stress_render_controller and self.stress_render_controller.running:
            threading.Thread(target=self.stress_render_controller.stop, daemon=True).start()
        self.stress_start_btn.config(state=tk.NORMAL)
        self.stress_stop_btn.config(state=tk.DISABLED)
        self._stress_log_append("— Stopped —")

    def _stress_cancel_poll(self):
        if self._stress_poll_id:
            self.root.after_cancel(self._stress_poll_id)
            self._stress_poll_id = None

    def _stress_poll(self):
        mode = self.stress_mode.get()

        # Auto-stop check
        if self._stress_auto_stop_at and time.perf_counter() >= self._stress_auto_stop_at:
            self._stress_stop()
            return

        if mode == "prime" and self.stress_controller:
            snap = self.stress_controller.poll()
            elapsed = snap["elapsed"]
            self.stress_stat_labels["Elapsed"].config(text=f"{elapsed:.0f}s")
            self.stress_stat_labels["Throughput"].config(text=f"{snap['iters_per_sec']:.0f}/s")
            self.stress_stat_labels["Tests/Frames"].config(text=str(snap["total_tests"]))
            err_col = "#ff4444" if snap["any_error"] else "#00aaff"
            self.stress_stat_labels["Errors"].config(
                text=str(sum(1 for e in snap.get("new_error_messages", []))), fg=err_col)

            for msg in snap.get("new_log_messages", []):
                self._stress_log_append(msg)
            for msg in snap.get("new_error_messages", []):
                self._stress_log_append(f"ERROR: {msg}")

            exps = snap["per_worker_exponents"]
            for i, lbl in enumerate(self.stress_core_labels):
                exp = exps[i] if i < len(exps) else 0
                color = "#ff4444" if (i < len(snap.get("new_error_messages", []))) else "#00dd66"
                lbl.config(text=f"Core {i}: M{exp}", fg=color)

        elif mode == "render" and self.stress_render_controller:
            snap = self.stress_render_controller.poll()
            elapsed = snap["elapsed"]
            self.stress_stat_labels["Elapsed"].config(text=f"{elapsed:.0f}s")
            fps = snap["frames_per_sec"]
            self.stress_stat_labels["Throughput"].config(text=f"{fps:.2f} fps")
            self.stress_stat_labels["Tests/Frames"].config(text=str(snap["frames_rendered"]))
            self.stress_stat_labels["Errors"].config(text="0", fg="#00aaff")

            for msg in snap.get("new_log_messages", []):
                self._stress_log_append(msg)

            img_bytes = snap.get("image_bytes")
            w = snap.get("image_width", 128)
            h = snap.get("image_height", 128)
            if img_bytes and len(img_bytes) == w * h:
                scale = max(1, min(4, 256 // max(w, h)))
                photo = _make_ppm_photo(img_bytes, w, h, scale=scale)
                self._stress_photo = photo
                self.stress_render_canvas.config(image=photo, text="")
                self.stress_render_info.config(
                    text=f"Frame {snap['frames_rendered']}  |  {snap['last_frame_duration']:.3f}s/frame  |  {snap['rays_per_sec']/1e6:.1f}M rays/s"
                )

        self._stress_poll_id = self.root.after(POLL_MS, self._stress_poll)

    # ─────────────────────────────────────────────────────────
    #  STABILITY TEST TAB
    # ─────────────────────────────────────────────────────────
    def _build_stability_tab(self):
        f = self.stab_frame

        # Controls row
        ctrl = ttk.Frame(f)
        ctrl.pack(fill=tk.X, padx=20, pady=10)

        # Mode
        mode_lf = ttk.LabelFrame(ctrl, text="Mode")
        mode_lf.pack(side=tk.LEFT, padx=(0, 16))
        self.stab_mode = tk.StringVar(value="count")
        ttk.Radiobutton(mode_lf, text="By Count", variable=self.stab_mode, value="count",
                        command=self._stab_mode_changed).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Radiobutton(mode_lf, text="By Time",  variable=self.stab_mode, value="time",
                        command=self._stab_mode_changed).pack(side=tk.LEFT, padx=6, pady=4)

        # Iterations (by-count mode)
        self.stab_iter_lf = ttk.LabelFrame(ctrl, text="Iterations")
        self.stab_iter_lf.pack(side=tk.LEFT, padx=(0, 16))
        self.stab_iters = tk.IntVar(value=24)
        for n in (16, 24, 48):
            ttk.Radiobutton(self.stab_iter_lf, text=str(n), variable=self.stab_iters, value=n).pack(
                side=tk.LEFT, padx=6, pady=4)

        # Duration (by-time mode)
        self.stab_time_lf = ttk.LabelFrame(ctrl, text="Duration (seconds)")
        self.stab_time_lf.pack(side=tk.LEFT, padx=(0, 16))
        self.stab_seconds = tk.IntVar(value=120)
        spin = ttk.Spinbox(self.stab_time_lf, from_=5, to=3600, textvariable=self.stab_seconds,
                           width=7, font=("Consolas", 10))
        spin.pack(padx=8, pady=4)

        # Start / Stop
        btn_frame = ttk.Frame(ctrl)
        btn_frame.pack(side=tk.LEFT, padx=8)
        self.stab_start_btn = ttk.Button(btn_frame, text="START", command=self._stab_start)
        self.stab_start_btn.pack(pady=2)
        self.stab_stop_btn = ttk.Button(btn_frame, text="STOP", command=self._stab_stop, state=tk.DISABLED)
        self.stab_stop_btn.pack(pady=2)

        # Stats row
        stats = ttk.Frame(f)
        stats.pack(fill=tk.X, padx=20, pady=4)
        self.stab_stat_labels = {}
        for col, key in enumerate(["Verdict", "Iterations", "Errors", "Consistency"]):
            box = tk.Frame(stats, bg="#2a2a2a", bd=1, relief="groove")
            box.grid(row=0, column=col, padx=6, sticky="ew")
            stats.columnconfigure(col, weight=1)
            tk.Label(box, text=key.upper(), fg="#888888", bg="#2a2a2a",
                     font=("Segoe UI", 8, "bold")).pack(pady=(6, 0))
            lbl = tk.Label(box, text="---", fg="#00aaff", bg="#2a2a2a",
                           font=("Segoe UI", 14, "bold"))
            lbl.pack(pady=(0, 6))
            self.stab_stat_labels[key] = lbl

        # Pass/fail grid
        grid_lf = ttk.LabelFrame(f, text="Pass / Fail Grid")
        grid_lf.pack(fill=tk.X, padx=20, pady=4)
        self.stab_grid_frame = ttk.Frame(grid_lf)
        self.stab_grid_frame.pack(fill=tk.X, padx=4, pady=4)
        self.stab_cells = []

        # Summary
        self.stab_summary = tk.Label(f, text="", fg="#aaaaaa", bg="#202020",
                                      font=("Segoe UI", 10))
        self.stab_summary.pack(anchor=tk.W, padx=24, pady=2)

        # Log
        log_lf = ttk.LabelFrame(f, text="Activity Log")
        log_lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        self.stab_log = tk.Text(log_lf, bg="#101010", fg="#00ff00",
                                 font=("Consolas", 9), relief="flat", state=tk.DISABLED)
        self.stab_log.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.stab_controller = None
        self._stab_poll_id = None
        self._stab_seen_results = 0

        self._stab_mode_changed()

    def _stab_mode_changed(self):
        if self.stab_mode.get() == "count":
            self.stab_iter_lf.pack(side=tk.LEFT, padx=(0, 16),
                                    before=self.stab_time_lf)
            self.stab_time_lf.pack_forget()
        else:
            self.stab_time_lf.pack(side=tk.LEFT, padx=(0, 16),
                                    before=self.stab_stop_btn.master)
            self.stab_iter_lf.pack_forget()

    def _stab_log_append(self, msg):
        self.stab_log.config(state=tk.NORMAL)
        self.stab_log.insert(tk.END, msg + "\n")
        self.stab_log.see(tk.END)
        self.stab_log.config(state=tk.DISABLED)

    def _stab_start(self):
        self.stab_start_btn.config(state=tk.DISABLED)
        self.stab_stop_btn.config(state=tk.NORMAL)

        # Clear
        self.stab_log.config(state=tk.NORMAL)
        self.stab_log.delete(1.0, tk.END)
        self.stab_log.config(state=tk.DISABLED)
        for lbl in self.stab_stat_labels.values():
            lbl.config(text="---", fg="#00aaff")
        for cell in self.stab_cells:
            cell.destroy()
        self.stab_cells.clear()
        self.stab_summary.config(text="")
        self._stab_seen_results = 0

        if self.stab_mode.get() == "count":
            self.stab_controller = StabilityController(max_iterations=self.stab_iters.get())
        else:
            self.stab_controller = StabilityController(
                max_iterations=9999,
                max_duration_seconds=self.stab_seconds.get(),
            )
        self.stab_controller.start()
        self._stab_log_append(f"Stability test started — workload: render 256×256/4spp/4-bounce")
        self._stab_poll()

    def _stab_stop(self):
        if self._stab_poll_id:
            self.root.after_cancel(self._stab_poll_id)
            self._stab_poll_id = None
        if self.stab_controller:
            self.stab_controller.stop()
        self.stab_start_btn.config(state=tk.NORMAL)
        self.stab_stop_btn.config(state=tk.DISABLED)
        self._stab_log_append("— Stopped —")

    def _stab_add_cell(self, index, passed):
        col = index % 12
        row = index // 12
        color = "#00bb44" if passed else "#cc2222"
        cell = tk.Label(self.stab_grid_frame, text=str(index + 1),
                        fg="#ffffff", bg=color, font=("Segoe UI", 8, "bold"),
                        width=3, relief="flat", pady=2)
        cell.grid(row=row, column=col, padx=2, pady=2)
        self.stab_cells.append(cell)

    def _stab_poll(self):
        if not self.stab_controller:
            return

        samples, results = self.stab_controller.get_snapshot()

        # Add new result cells
        for r in results[self._stab_seen_results:]:
            self._stab_add_cell(r["index"], r["passed"])
            status = "PASS" if r["passed"] else "FAIL"
            self._stab_log_append(
                f"Iteration {r['index']+1:2d}: score={r['score']:.4f}  [{status}]"
            )
        self._stab_seen_results = len(results)

        # Stats
        total = self.stab_controller.max_iterations
        done = len(results)
        self.stab_stat_labels["Iterations"].config(text=f"{done}/{total}")
        fail_count = sum(1 for r in results if not r["passed"])
        self.stab_stat_labels["Errors"].config(
            text=str(fail_count),
            fg="#ff4444" if fail_count else "#00aaff"
        )

        verdict = self.stab_controller.get_verdict()
        if verdict:
            v_color = {"good": "#00bb44", "warn": "#ffaa00", "bad": "#cc2222"}.get(
                verdict["level"], "#00aaff")
            self.stab_stat_labels["Verdict"].config(text=verdict["label"], fg=v_color)
            self.stab_stat_labels["Consistency"].config(
                text=f"{verdict['consistency']:.1f}%", fg=v_color)

        # Summary when finished
        if not self.stab_controller.running and self._stab_poll_id:
            self.stab_start_btn.config(state=tk.NORMAL)
            self.stab_stop_btn.config(state=tk.DISABLED)
            retention = self.stab_controller.compute_retention()
            if retention:
                pct = retention["retained_pct"]
                verdict_label = verdict["label"] if verdict else "N/A"
                self.stab_summary.config(
                    text=f"Result: {verdict_label}  |  {pct:.1f}% performance retained  "
                         f"|  {fail_count} iteration(s) failed",
                    fg="#00aaff"
                )
            self._stab_poll_id = None
            return

        self._stab_poll_id = self.root.after(POLL_MS, self._stab_poll)

    # ─────────────────────────────────────────────────────────
    #  WINDOW CLOSE
    # ─────────────────────────────────────────────────────────
    def _on_close(self):
        if self.stress_controller and self.stress_controller.running:
            self.stress_controller.stop()
        if self.stress_render_controller and self.stress_render_controller.running:
            self.stress_render_controller.stop()
        if self.stab_controller and self.stab_controller.running:
            self.stab_controller.stop()
        self.root.destroy()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = SiliconBenchApp(root)
    root.mainloop()
