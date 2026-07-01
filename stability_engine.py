import multiprocessing
import threading
import time

import workloads_render
from workloads_sc import SCWorkloads

# Fixed representative subset used only when the "sc_subset" workload mode is
# selected as an alternative to the default fixed-scene render workload. Each
# function already runs a fixed iteration count (see workloads_sc.py), so this
# is constant-difficulty too, just a different (non-rendering) instruction mix.
SC_SUBSET_FUNCS = [SCWorkloads.integer_alu_mix, SCWorkloads.hashing, SCWorkloads.physics_nbody]

# Stability's default render pass is deliberately heavier than the base
# workloads_render.py scene (128x128/2spp/3 bounces, ~0.25s/frame on an
# 8-core machine): ~4x the resolution*samples work (~1.1s/frame) makes
# sustained-load degradation (thermal throttling) show up more clearly than a
# workload that finishes almost instantly. Still a *fixed* configuration --
# every pass does identical work, so wall-clock time stays a pure CPU-speed
# signal. Stress Test's separate Rendering mode is untouched by this.
INTENSIVE_RENDER_KWARGS = {"width": 256, "height": 256, "samples_per_pixel": 4, "max_bounces": 4}


class StabilityController:
    """Runs back-to-back passes of a constant-difficulty workload (default:
    one fixed-scene render per pass) and classifies each pass as pass/fail
    against a running baseline, so sustained-load degradation (thermal
    throttling) shows up as a live pass/fail trend rather than only a single
    end-of-run percentage. Bounded by `max_iterations`, by `max_duration_seconds`
    (if set), or by stop() -- whichever comes first."""

    def __init__(self, max_iterations=24, num_cores=None, workload="render", render_kwargs=None,
                 baseline_n=3, pass_threshold_pct=90.0, min_sample_gap=0.0, max_duration_seconds=None):
        self.max_iterations = max_iterations
        self.max_duration_seconds = max_duration_seconds  # None = unbounded by time
        self.num_cores = num_cores or multiprocessing.cpu_count()
        self.workload = workload  # "render" (default) or "sc_subset"
        self.render_kwargs = render_kwargs if render_kwargs is not None else dict(INTENSIVE_RENDER_KWARGS)
        self.baseline_n = baseline_n
        self.pass_threshold_pct = pass_threshold_pct
        self.min_sample_gap = min_sample_gap  # optional back-to-back pacing; 0 = no gap

        self.samples = []  # list of (elapsed_seconds, score)
        self.results = []  # list of {"index", "score", "passed"}
        self.running = False
        self.stop_flag = False
        self.thread = None
        self._lock = threading.Lock()

    def start(self):
        self.samples = []
        self.results = []
        self.stop_flag = False
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        # Cooperative: the loop finishes its current in-flight pass (so no
        # garbage partial-duration reading) before exiting.
        self.stop_flag = True

    def _run_one_sample(self):
        if self.workload == "sc_subset":
            return self._run_sc_subset_sample()

        duration = workloads_render.render_frame(num_workers=self.num_cores, **self.render_kwargs)
        return (1.0 / duration) if duration > 0 else 0.0

    def _run_sc_subset_sample(self):
        start = time.perf_counter()
        with multiprocessing.Pool(self.num_cores) as pool:
            for func in SC_SUBSET_FUNCS:
                work_items = [()] * self.num_cores
                pool.starmap(func, work_items)
        duration = time.perf_counter() - start
        units = self.num_cores * len(SC_SUBSET_FUNCS)
        return (units / duration) if duration > 0 else 0.0

    def _classify(self, score):
        # Baseline = average of the first `baseline_n` scores collected so
        # far (partial if fewer than baseline_n samples exist yet).
        scores_so_far = [s for _, s in self.samples]
        baseline_pool = scores_so_far[:self.baseline_n]
        baseline = sum(baseline_pool) / len(baseline_pool)
        if baseline <= 0:
            return True
        return (score / baseline) * 100 >= self.pass_threshold_pct

    def _run_loop(self):
        t0 = time.perf_counter()
        for i in range(self.max_iterations):
            if self.stop_flag:
                break
            if self.max_duration_seconds and (time.perf_counter() - t0) >= self.max_duration_seconds:
                break
            sample_start = time.perf_counter()
            score = self._run_one_sample()
            elapsed = time.perf_counter() - t0
            with self._lock:
                self.samples.append((elapsed, score))
                passed = self._classify(score)
                self.results.append({"index": i, "score": score, "passed": passed})

            if self.min_sample_gap:
                elapsed_this = time.perf_counter() - sample_start
                sleep_left = max(0.0, self.min_sample_gap - elapsed_this)
                slept = 0.0
                while slept < sleep_left and not self.stop_flag:
                    chunk = min(0.5, sleep_left - slept)
                    time.sleep(chunk)
                    slept += chunk
        self.running = False

    def get_snapshot(self):
        with self._lock:
            return list(self.samples), list(self.results)

    def compute_retention(self, baseline_n=None, final_n=3):
        baseline_n = baseline_n or self.baseline_n
        with self._lock:
            scores = [s for _, s in self.samples]
        if len(scores) < 2:
            return None
        baseline = sum(scores[:baseline_n]) / min(baseline_n, len(scores))
        final = sum(scores[-final_n:]) / min(final_n, len(scores))
        retained_pct = (final / baseline) * 100 if baseline > 0 else 0.0
        return {"baseline": baseline, "final": final, "retained_pct": retained_pct}

    def get_verdict(self):
        retention = self.compute_retention()
        if retention is None:
            return None
        with self._lock:
            fail_count = sum(1 for r in self.results if not r["passed"])
        pct = retention["retained_pct"]
        if pct >= 95 and fail_count == 0:
            level, label = "good", "Stable"
        elif pct >= 85:
            level, label = "warn", "Degraded"
        else:
            level, label = "bad", "Unstable"
        return {"label": label, "level": level, "consistency": pct, "fail_count": fail_count}
