import multiprocessing
import threading
import time

import workloads_render

# Known Lucas-Lehmer-provable Mersenne prime exponents. Kept to a small/fast
# set (each full test finishes in well under a few seconds on a modern core)
# so the live per-core status and iteration counters update frequently and
# Stop feels immediate rather than waiting on a multi-second exponent.
KNOWN_MERSENNE_EXPONENTS = [521, 607, 1279, 2203, 3217]


def _mersenne_worker(worker_id, stop_event, exponents, iters_counter, tests_counter,
                      last_exponent, error_flags, error_queue, log_queue, self_check_every):
    """Top-level (picklable) worker: cycles through `exponents` running the
    Lucas-Lehmer primality test on each M = 2^p - 1, indefinitely, until
    stop_event is set. Mirrors the real GIMPS/Prime95 torture-test algorithm.
    stop_event is checked every inner iteration so Stop lands within a single
    modmul rather than after a whole (possibly multi-second) exponent."""
    idx = 0
    n = len(exponents)
    while not stop_event.is_set():
        p = exponents[idx % n]
        idx += 1
        last_exponent.value = p

        M = (1 << p) - 1
        s = 4
        for i in range(p - 2):
            if stop_event.is_set():
                return
            prev_s = s
            s = (s * s - 2) % M
            with iters_counter.get_lock():
                iters_counter.value += 1

            # Lightweight self-check: redundantly recompute the step just
            # performed and compare. Cheap (one extra modmul every
            # self_check_every-th iteration), catches a class of transient
            # bit-flip-style errors -- not full GIMPS Gerbicz-checking, but
            # in the same spirit as Prime95 flagging calculation mismatches.
            if self_check_every and i % self_check_every == 0:
                verify = (prev_s * prev_s - 2) % M
                if verify != s:
                    error_flags[worker_id] = True
                    error_queue.put(f"Worker {worker_id}: self-check mismatch at M{p}, iter {i}")

        is_prime = (s == 0)
        with tests_counter.get_lock():
            tests_counter.value += 1
        log_queue.put(f"Core {worker_id}: M{p} -> {'PRIME' if is_prime else 'composite'}")


class StressController:
    """Prime Search (Mersenne/Lucas-Lehmer) stress mode."""

    def __init__(self):
        self.manager = None
        self.stop_event = None
        self.processes = []
        self.iters_counters = []
        self.tests_counters = []
        self.last_exponents = []
        self.error_flags = None
        self.error_queue = None
        self.log_queue = None
        self.num_workers = 0
        self.start_time = None
        self.running = False

    def start(self, num_workers=None, exponents=None, self_check_every=5):
        self.num_workers = num_workers or multiprocessing.cpu_count()
        exponents = list(exponents) if exponents else list(KNOWN_MERSENNE_EXPONENTS)

        self.manager = multiprocessing.Manager()
        self.stop_event = multiprocessing.Event()
        self.error_flags = self.manager.list([False] * self.num_workers)
        self.error_queue = self.manager.Queue()
        self.log_queue = self.manager.Queue()
        self.iters_counters = [multiprocessing.Value('L', 0) for _ in range(self.num_workers)]
        self.tests_counters = [multiprocessing.Value('L', 0) for _ in range(self.num_workers)]
        self.last_exponents = [multiprocessing.Value('L', 0) for _ in range(self.num_workers)]

        self.processes = []
        for i in range(self.num_workers):
            proc = multiprocessing.Process(
                target=_mersenne_worker,
                args=(i, self.stop_event, exponents, self.iters_counters[i],
                      self.tests_counters[i], self.last_exponents[i],
                      self.error_flags, self.error_queue, self.log_queue, self_check_every),
                daemon=True,
            )
            self.processes.append(proc)
            proc.start()

        self.start_time = time.perf_counter()
        self.running = True

    def stop(self, join_timeout=5.0):
        if self.stop_event is not None:
            self.stop_event.set()
        for proc in self.processes:
            proc.join(join_timeout)
            if proc.is_alive():
                proc.terminate()
        self.running = False

    def poll(self):
        """Non-blocking snapshot for the GUI thread."""
        elapsed = (time.perf_counter() - self.start_time) if self.start_time else 0.0
        total_iters = sum(c.value for c in self.iters_counters)
        total_tests = sum(c.value for c in self.tests_counters)
        per_worker_exponents = [v.value for v in self.last_exponents]
        errors = list(self.error_flags) if self.error_flags is not None else []

        new_errors = _drain_queue(self.error_queue)
        new_logs = _drain_queue(self.log_queue)

        return {
            "mode": "prime",
            "elapsed": elapsed,
            "total_iters": total_iters,
            "iters_per_sec": (total_iters / elapsed) if elapsed > 0 else 0.0,
            "total_tests": total_tests,
            "per_worker_exponents": per_worker_exponents,
            "any_error": any(errors),
            "new_error_messages": new_errors,
            "new_log_messages": new_logs,
        }


class RenderStressController:
    """Rendering (Cinebench-style, fixed-scene path tracer) stress mode."""

    def __init__(self):
        self.thread = None
        self.stop_flag = None
        self.num_workers = 0
        self.frames_rendered = 0
        self.total_render_time = 0.0
        self.last_frame_duration = 0.0
        self.last_image_bytes = None
        self.start_time = None
        self.running = False
        self._last_reported_frames = 0
        self._lock = threading.Lock()

    def start(self, num_workers=None):
        self.num_workers = num_workers or multiprocessing.cpu_count()
        self.stop_flag = threading.Event()
        self.frames_rendered = 0
        self.total_render_time = 0.0
        self.last_frame_duration = 0.0
        self.last_image_bytes = None
        self._last_reported_frames = 0
        self.start_time = time.perf_counter()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        # Loop lives in this controller thread, not in the worker processes
        # themselves -- render_frame()'s Pool is short-lived and finishes on
        # its own between checks of the stop flag, so a plain threading.Event
        # is enough (no need to thread a multiprocessing.Event through every
        # tile worker). A single 128x128/2spp/3-bounce frame is sub-second,
        # so Stop latency is bounded to about one frame time.
        while not self.stop_flag.is_set():
            duration, image_bytes = workloads_render.render_frame(num_workers=self.num_workers, return_pixels=True)
            with self._lock:
                self.frames_rendered += 1
                self.total_render_time += duration
                self.last_frame_duration = duration
                self.last_image_bytes = image_bytes
        self.running = False

    def stop(self, join_timeout=10.0):
        if self.stop_flag is not None:
            self.stop_flag.set()
        if self.thread is not None:
            self.thread.join(join_timeout)
        self.running = False

    def poll(self):
        elapsed = (time.perf_counter() - self.start_time) if self.start_time else 0.0
        with self._lock:
            frames = self.frames_rendered
            last_duration = self.last_frame_duration
            image_bytes = self.last_image_bytes

        fps = (frames / elapsed) if elapsed > 0 else 0.0
        rays_per_frame = workloads_render.WIDTH * workloads_render.HEIGHT * workloads_render.SAMPLES_PER_PIXEL
        rays_per_sec = fps * rays_per_frame

        new_logs = []
        if frames > self._last_reported_frames:
            new_logs.append(f"Frame {frames} rendered in {last_duration:.3f}s ({fps:.2f} fps)")
            self._last_reported_frames = frames

        return {
            "mode": "render",
            "elapsed": elapsed,
            "frames_rendered": frames,
            "frames_per_sec": fps,
            "last_frame_duration": last_duration,
            "rays_per_sec": rays_per_sec,
            "image_bytes": image_bytes,
            "image_width": workloads_render.WIDTH,
            "image_height": workloads_render.HEIGHT,
            "any_error": False,
            "new_error_messages": [],
            "new_log_messages": new_logs,
        }


def _drain_queue(queue):
    items = []
    while queue is not None and not queue.empty():
        try:
            items.append(queue.get_nowait())
        except Exception:
            break
    return items
