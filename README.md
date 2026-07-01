# SiliconBench 2-Go

A zero-dependency distribution of SiliconBench. Runs on any Python 3.8+ installation — no `pip install` required.

## Requirements

- Python 3.8 or newer (tkinter is included with macOS/Windows/Linux system Python)

## Run

```
python main.py
```

## Tabs

### Benchmark
Single-Core, Multi-Core, and System Scaling suites from the original SiliconBench.
Results are shown against Apple M2, Core i5-7400T, and Core i3-4130 reference scores.

### Stress Test
Runs continuously until stopped or a preset duration (30 / 60 / 120 s) expires.

- **Prime Search** — Lucas-Lehmer Mersenne primality torture test, one worker per CPU core.  
  Self-checks every 5 iterations to catch calculation mismatches (Prime95-style).  
  Per-core exponent status updates live.

- **Rendering** — Cinebench-style fixed-scene path tracer, all cores.  
  Live render preview updates as each frame completes.

### Stability Test
Runs back-to-back render passes and classifies each as Pass/Fail against a rolling
baseline, so thermal throttling shows up as a trend rather than a single end-of-run number.

- **By Count** — run 16 / 24 / 48 iterations.
- **By Time**  — run for a user-specified number of seconds (5 – 3600).

Verdict thresholds:
- **Stable** — ≥ 95% retained, zero failures
- **Degraded** — ≥ 85% retained
- **Unstable** — < 85% retained

## Files

| File | Source |
|---|---|
| `main.py` | UI (Tkinter/ttk, pure stdlib) |
| `benchmark_engine.py` | Original benchmark engine |
| `workloads_sc.py` | Single-core workloads |
| `workloads_mc.py` | Multi-core / system workloads |
| `workloads_render.py` | Fixed-scene path tracer |
| `stress_engine.py` | StressController + RenderStressController |
| `stability_engine.py` | StabilityController |
