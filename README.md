# SiliconBench 2.0

**SiliconBench 2.0** is a zero-dependency, pure-Python CPU benchmarking suite with a native Tkinter GUI. Runs on any Python 3.8+ installation with automatic OS dark/light mode detection.

## Features

### Benchmark Suite
- **Single-Core Performance**: 12 CPU-intensive workloads (integer, branching, encryption, compression, FFT, physics, ray tracing)
- **Multi-Core Throughput**: Scales benchmarks across all available CPU cores
- **System Scaling**: Memory streaming, synchronization, and producer-consumer patterns
- **Results**: Immediate display with performance ratings (Low/Medium/Good)

### Stress Testing
Two workload modes designed to push the CPU to its limits:

**Prime Number Search** (Lucas-Lehmer Mersenne)
- One worker per CPU core
- Self-checking every 5 iterations (Prime95-style)
- Purely integer-based workload
- Per-core exponent tracking
- Detects calculation mismatches in real-time

**Rendering** (Cinebench-style Ray Tracer)
- Fixed-scene path tracer
- All cores working in parallel
- Live frame rendering preview
- Real-time frame/ray throughput metrics
- Floating-point intensive workload

**Duration Options**: Manual (run until stopped), 30s, 60s, or 120s presets

### Stability Testing
Iterative render passes with thermal throttling detection:

**Test Modes**:
- **By Count**: 16, 24, or 48 iterations
- **By Time**: 5 to 3600 seconds user-configurable

**Metrics**:
- Pass/fail results displayed as colored grid
- Baseline vs. final score tracking
- Retained performance percentage
- Consistency verdict (Stable/Degraded/Unstable)
- Thermal throttling trends

**Verdict Thresholds**:
- **Stable** ≥95% retained, zero failures
- **Degraded** ≥85% retained or minor failures
- **Unstable** <85% retained or multiple failures

### Cross-Platform UI
- **Tkinter/ttk**: Pure stdlib, no external GUI dependencies
- **Auto Dark Mode Detection**: Respects OS theme preference
  - macOS: `AppleInterfaceStyle` defaults
  - Windows: Registry-based theme detection
  - Linux: GNOME gsettings integration
- **Automatic Theme Sync**: Light/dark palettes with accent colors
- **Responsive Design**: Modern card-based layout

### Results & History
- Benchmarks saved as JSON with timestamps
- Performance history tracking
- Portable results (JSON format)
- Export for analysis

## System Requirements

### Minimum
- **Python**: 3.8 or newer
- **Tkinter**: Included with most Python distributions
- **CPU**: Any multi-core processor
- **RAM**: 2 GB

### Platform-Specific

**macOS**:
- Python 3.8+ (system or Homebrew)
- Tkinter included with Python 3.8+

**Windows**:
- Python 3.8+ (python.org or Microsoft Store)
- Tkinter included with standard Python installer

**Linux**:
- Python 3.8+
- Tkinter package (usually bundled)
- For Fedora/RHEL: `sudo dnf install python3-tkinter`
- For Ubuntu/Debian: `sudo apt install python3-tk`

## Installation & Usage

### Quick Start
```bash
git clone https://github.com/radiant803/SiliconBench2.0.git
cd SiliconBench2.0
python3 main.py
```

### No Installation Required
No pip, no virtual env, no setup.py — just run:
```bash
python3 main.py
```

All dependencies are in Python's standard library.

## GUI Walkthrough

### Main Window
- **Tabbed interface**: Benchmark | Stress Test | Stability Test
- **Status bar**: Current operation and progress
- **Activity log**: Real-time status and result display
- **Auto-saving**: Results stored in `~/siliconbench/results/`

### Benchmark Tab
1. Select test suites: Single-Core, Multi-Core, System Scaling
2. Click "RUN BENCHMARK"
3. Watch progress bars fill as workloads complete
4. Final scores displayed with ratings

**Output Example**:
```
Single-Core:      1232  (Good)
Multi-Core:       9193  (Good)
System Scaling:   1987  (Good)
```

### Stress Test Tab
1. Select workload: Prime Search or Rendering
2. Choose duration: Manual or preset (30/60/120s)
3. Click "START STRESS TEST"
4. Monitor real-time metrics:
   - Elapsed time
   - Throughput (iters/sec or fps)
   - Errors (if any)
   - Per-core activity
5. Click "STOP" or wait for auto-stop

### Stability Test Tab
1. Choose test mode: By Count (16/24/48) or By Time (5-3600s)
2. Click "START STABILITY TEST"
3. View live pass/fail grid
4. Final verdict with consistency metrics
5. Analyze performance degradation trend

## Architecture

### Core Components
```
main.py
├── UI (Tkinter/ttk)
├── Theme detection & switching
└── Tab controllers

benchmark_engine.py
├── BenchmarkEngine class
├── Workload definitions
└── Score calculation

stress_engine.py
├── StressController (Prime)
├── RenderStressController (Rendering)
└── Worker polling

stability_engine.py
├── StabilityController
├── Pass/fail tracking
└── Retention metrics

workloads_*.py
├── workloads_sc.py (Single-core kernels)
├── workloads_mc.py (Multi-core kernels)
└── workloads_render.py (Path tracer)
```

### Design Patterns
- **Pure stdlib**: No pip install required
- **Callback-based**: Engines report progress without blocking UI
- **Multiprocessing**: Safe worker spawning for parallel tests
- **Theme abstraction**: Single PALETTE dict for light/dark switching
- **Non-blocking UI**: All operations run in background threads

## Performance Tips

1. **Close background apps** — Reduces system noise during benchmarking
2. **Disable turbo boost** (if consistent results needed) — Prevents frequency scaling
3. **Monitor thermals** — Results degrade if CPU overheats
4. **Run multiple times** — Average 3+ runs for reliable baseline
5. **Check system load** — High load affects stress/stability results

## Scoring System

### Formula
```
Score = (Baseline Time / Actual Time) × 1000 × Scale Factor
```

**Baseline**: Reference time for each workload (tuned for ~1000 pts on modern CPUs)
**Scale Factor**: CPU core count for multi-core tests (1.0 for single-core)
**Higher scores = faster CPU**

### Expected Ranges
| Workload | Range | Notes |
|----------|-------|-------|
| Integer ALU | 600-2000 | Varies by IPC |
| Branching | 500-1500 | Branch prediction impact |
| Matrix Math | 400-1200 | Cache sensitivity |
| Encryption | 700-2000 | AES-NI availability |
| Ray Tracing | 300-1000 | Memory bandwidth |

## Troubleshooting

### App won't start
```bash
# Verify Tkinter is installed
python3 -m tkinter
# Should open a small test window
```

**On Linux**:
```bash
sudo apt install python3-tk  # Ubuntu/Debian
sudo dnf install python3-tkinter  # Fedora/RHEL
```

### Theme not detected (stays light mode on macOS)
- May require logout/login for OS theme changes to apply
- Or manually toggle System Preferences > Appearance

### Stress test crashes / "SIGILL" errors
- Usually indicates Numba/CPU compatibility issue
- Upgrade Python: `python3 --version` should be 3.10+
- Or switch to SiliconBench CLI (uses Numba more robustly)

### Results not saving
- Check directory permissions: `ls -la ~/siliconbench/results/`
- Or manually verify write access: `touch ~/siliconbench/test.txt`

### Low/inconsistent scores
- **Close all background processes**
- **Check CPU temperature** — Throttling reduces scores
- **Disable power-saving features**
- **Run on AC power** (laptops may throttle on battery)
- **Average 3+ runs** — One-off scores unreliable

### "ImportError: No module named 'workloads_*'"
- Ensure all `.py` files are in the same directory
- Run from the same directory as `main.py`

## File Structure

| File | Purpose |
|------|---------|
| `main.py` | Tkinter GUI, tab controllers, theme sync |
| `benchmark_engine.py` | Benchmark harness, score calculation |
| `workloads_sc.py` | Single-core workload functions |
| `workloads_mc.py` | Multi-core and system workloads |
| `workloads_render.py` | Fixed-scene path tracer (ray tracing) |
| `stress_engine.py` | Prime & Render stress test controllers |
| `stability_engine.py` | Iterative stability test logic |
| `README.md` | This file |

## Version History

### 2.0.1 (Current)
- **Auto OS theme detection** (dark/light mode)
- **Theme sync on OS changes** (macOS notifications)
- **Tkinter/ttk modern styling**
- **Removed reference score panel** (baseline scores deprecated due to Python version variance)

### 2.0
- Initial multi-suite release
- Benchmark, Stress, Stability tabs
- Results history

## Related Projects

- **SiliconBench X**: GUI with PySide6/Qt (modern features, cross-platform)
- **SiliconBench CLI**: Command-line version (headless/CI-CD)
- **SiliconBench Lite**: Python REPL version (interactive shell)
- **SiliconBench APK**: Android mobile app

## Known Limitations

1. **Tkinter limitations**: Some UI elements may not render identically on all platforms
2. **Accuracy**: Scores vary based on system load and thermal state
3. **Compatibility**: Requires local Python (not web-based)
4. **Resolution**: UI best at 1920x1080 or higher (responsive design still in progress)

## Contributing

Issues and feature requests welcome on GitHub [Issues](../../issues).

**Testing contributions appreciated**:
- Report platform-specific issues
- Suggest workload improvements
- Help tune baseline scores

## License

Proprietary. See LICENSE file for details.

## Support

- **Questions**: Check GitHub Issues for similar problems
- **Bugs**: Report with full system info (`siliconbench info`)
- **Features**: Open a feature request on GitHub

---

**Version**: 2.0.1 (Python-native, theme-aware)  
**Last Updated**: 2026-07-14  
**Maintainer**: SiliconBench Team
