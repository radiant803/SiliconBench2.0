import time
import math
import multiprocessing
from workloads_sc import SCWorkloads
from workloads_mc import MCWorkloads

# Helper wrapper for pool.map to pick up
def _run_sc_wrapper(func_name, args):
    # Re-import or rely on module availability? 
    # Static methods are picklable, but we need the function object.
    # We can pass the function object if it's top level or static.
    # Let's pass the function itself in the tuple if possible, or lookup.
    # Actually simplest is to just run the function.
    # But multiprocessing pickles arguments.
    # Let's assume 'func' is passed and is picklable (static methods are).
    start = time.perf_counter()
    func_name(*args) # func_name is the actual function object here
    return time.perf_counter() - start

class BenchmarkEngine:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.sc = SCWorkloads()
        self.mc = MCWorkloads() # These are now "Extra" or "System" workloads
        self.running = False
        self.num_cores = multiprocessing.cpu_count()

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def update_progress(self, value, total):
        if self.progress_callback:
            self.progress_callback(value, total)

    def calculate_score(self, baseline_time, actual_time, scale_factor=1.0):
        if actual_time <= 0: return 0
        # Score = (Baseline / Actual) * 1000 * ScaleFactor
        return int((baseline_time / actual_time) * 1000 * scale_factor)

    def _run_single_core_pass(self, tasks):
        results = {}
        for name, func, args, baseline in tasks:
            if not self.running: break
            self.log(f"Running SC {name}...")
            
            start = time.perf_counter()
            try:
                func(*args)
            except Exception as e:
                self.log(f"Error in {name}: {e}")
                continue
            duration = time.perf_counter() - start
            
            score = self.calculate_score(baseline, duration)
            results[name] = score
            self.log(f"  > Time: {duration:.4f}s | Score: {score}")
            time.sleep(0.5) # Short gap
        return results

    def _run_multi_core_pass(self, tasks):
        # Run SC workloads on ALL cores
        results = {}
        with multiprocessing.Pool(self.num_cores) as pool:
            for name, func, args, baseline in tasks:
                if not self.running: break
                self.log(f"Running MC {name} (x{self.num_cores})...")
                
                # We need to wrap the function call to measure time inside the worker?
                # Or just measure total time of the batch?
                # Measuring total time of batch (wall clock) is 'throughput' time.
                
                # Prepare arguments for map
                # map expects function and iterable.
                # We want to run 'func' N times.
                
                start = time.perf_counter()
                try:
                    # We pass the function object.
                    # func is a static method, so it pickles fine.
                    pool_args = [args] * self.num_cores
                    # simple wrapper to unpack? No, func(*args) needs star unpack.
                    # simple lambda? can't pickle lambda.
                    # Workaround: use helper function defined at top level?
                    # Or just starmap if func accepts multiple args?
                    # our funcs usually accept iterations=... which is 1 arg?
                    # Let's check workloads_sc. They take 'iterations'.
                    # So simple map works.
                    
                    # For safety, let's just use starmap with a list of tuples
                    # But if args is empty list [], then starmap calls func().
                    
                    if not args:
                        # Inspect default args? sc workloads have defaults.
                        # We can pass empty tuple.
                        work_items = [()] * self.num_cores
                    else:
                        work_items = [tuple(args)] * self.num_cores
                        
                    pool.starmap(func, work_items)
                    
                except Exception as e:
                    self.log(f"Error in {name}: {e}")
                    continue
                    
                duration = time.perf_counter() - start
                
                # Score calculation:
                # If 1 core takes T seconds to do 1 unit of work.
                # N cores take T seconds to do N units of work (perfect scaling).
                # Measured duration is T.
                # Score should reflect N units.
                # So we apply scale_factor = self.num_cores
                score = self.calculate_score(baseline, duration, scale_factor=self.num_cores)
                results[name] = score
                self.log(f"  > Time: {duration:.4f}s | Score: {score}")
                time.sleep(1.0) # Thermal gap
        return results

    def _run_extra_pass(self, tasks):
        # These are the specific MC workloads (contention, etc)
        # They manage their own multiprocessing.
        # We just run them once and time them.
        results = {}
        for name, func, args, baseline in tasks:
            if not self.running: break
            self.log(f"Running Extra {name}...")
            
            start = time.perf_counter()
            try:
                # These funcs return a 'result' (count/hash/etc) not time.
                # But we measure time.
                func(*args)
            except Exception as e:
                self.log(f"Error in {name}: {e}")
                continue
            duration = time.perf_counter() - start
            
            # These were designed with baselines for specific iteration counts which implicitly assume N cores.
            # We don't apply N scaling here because the workload ITSELF is the N-core workload.
            score = self.calculate_score(baseline, duration)
            results[name] = score
            self.log(f"  > Time: {duration:.4f}s | Score: {score}")
            time.sleep(1.0)
        return results

    def run_suite(self, run_sc=True, run_mc=True, run_extra=True):
        self.running = True
        
        # --- DEFINITIONS ---
        # Baselines are roughly estimated for ~Mid-Range Modern Core (e.g. Zen3/Skylake) doing 1 unit of work.
        
        sc_workloads = [
            ("Integer ALU", self.sc.integer_alu_mix, [], 0.05),
            ("Branching", self.sc.branchy_code, [], 0.08),
            ("String Proc", self.sc.string_processing, [], 0.15),
            ("Hashing", self.sc.hashing, [], 0.12),
            ("Encryption", self.sc.encryption_aes_sim, [], 0.20),
            ("Compression", self.sc.compression_lz_sim, [], 0.18),
            ("Matrix Math", self.sc.matrix_math, [], 0.10),
            ("FFT", self.sc.fft_sim, [], 0.25),
            ("Physics", self.sc.physics_nbody, [], 0.30),
            ("Ray Tracing", self.sc.ray_trace_kernel, [], 0.15),
            ("Image Blur", self.sc.image_gaussian_blur, [], 0.40),
            ("Compiler", self.sc.compiler_sim, [], 0.15),
        ]
        
        extra_workloads = [
             ("Hash Farm", self.mc.run_parallel_hashing, [], 0.2), # Throughput-like
             ("Compression", self.mc.run_parallel_compression, [], 0.2), # Throughput-like
             ("Monte Carlo", self.mc.run_monte_carlo, [], 0.15), 
             ("Image Tile", self.mc.run_tile_image, [], 0.3),
             ("Ray Batch", self.mc.run_batch_ray, [], 0.15),
             ("Mem Stream", self.mc.run_stream_memory, [], 0.5), 
             ("Pointer Chase", self.mc.run_pointer_chase, [], 0.4),
             ("Contention", self.mc.run_contention, [], 0.5), # Sync heavy
             ("Prod/Cons", self.mc.run_producer_consumer, [], 0.6), # Sync heavy
             ("Work Steal", self.mc.run_work_stealing_sim, [], 0.2),
        ]

        # --- EXECUTION ---
        
        sc_scores = {}
        mc_scores = {} # Throughput
        ex_scores = {} # System/Extra

        # 1. Single Core Pass
        if run_sc and self.running:
            self.log("\n[Phase 1] Single-Core Performance")
            sc_scores = self._run_single_core_pass(sc_workloads)

        # 2. Multi Core Pass (Run SC workloads on all cores)
        if run_mc and self.running:
            self.log("\n[Phase 2] Multi-Core Throughput")
            mc_scores = self._run_multi_core_pass(sc_workloads)

        # 3. Extra/System Pass
        if run_extra and self.running:
            self.log("\n[Phase 3] System & Scaling Extras")
            ex_scores = self._run_extra_pass(extra_workloads)

        if not self.running:
            return None

        # --- AGGREGATION ---
        
        def avg(lst): return int(sum(lst)/len(lst)) if lst else 0
        
        final_sc = avg(list(sc_scores.values()))
        final_mc = avg(list(mc_scores.values()))
        final_ex = avg(list(ex_scores.values()))
        
        self.log("=" * 40)
        self.log(f"Single-Core Score:   {final_sc}")
        self.log(f"Multi-Core Score:    {final_mc}")
        self.log(f"System/Extra Score:  {final_ex}")
        self.log("=" * 40)
        
        return {
            "sc_score": final_sc,
            "mc_score": final_mc,
            "extra_score": final_ex,
            "details_sc": sc_scores,
            "details_mc": mc_scores,
            "details_ex": ex_scores
        }

    def stop(self):
        self.running = False
