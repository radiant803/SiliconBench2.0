import multiprocessing
import time
import hashlib
import zlib
import random
import math
import os

# --- Worker Functions (Must be top-level) ---

def _worker_hash_farm(iterations):
    # Independent hashing
    data = b"Benchmarks are parallel!" * 50
    digest = b""
    for _ in range(iterations):
        digest = hashlib.sha256(data + digest).digest()
    return digest

def _worker_compress(iterations):
    # Independent compression
    data = (b"RepeatingPattern" * 50 + b"RandomAttributes" * 50) * 10
    total = 0
    for _ in range(iterations):
        comp = zlib.compress(data)
        total += len(comp)
    return total

def _worker_monte_carlo(iterations):
    # Estimate Pi
    inside = 0
    for _ in range(iterations):
        x = random.random()
        y = random.random()
        if x*x + y*y <= 1.0:
            inside += 1
    return inside

def _worker_image_tile(iterations):
    # Simulate processing a tile
    w, h = 64, 64
    img = [random.randint(0, 255) for _ in range(w*h)]
    # Blur
    for _ in range(iterations):
        # simplified blur logic (1 pass)
        new_img = [x//2 for x in img] # dummy op to consume cycles
        img = new_img
    return img[0]

def _worker_ray_batch(iterations):
    # Same as SC ray trace but simpler for pure throughput test
    hit = 0
    for i in range(iterations):
        x = (i % 100) / 50.0
        if x*x < 0.5: hit += 1
    return hit

def _worker_stream_triad(size):
    # READ + READ + WRITE
    # Generate large arrays
    a = [1.0] * size
    b = [2.0] * size
    c = [0.0] * size
    scalar = 3.0
    for i in range(size):
        c[i] = a[i] + scalar * b[i]
    return c[0]

def _worker_pointer_chase(size):
    # Linked list traversal simulation via array indices
    # Create random permutation
    nodes = list(range(size))
    random.shuffle(nodes)
    next_ptr = list(range(size))
    for i in range(size):
        next_ptr[i] = nodes[i]
    
    current = 0
    # traverse
    for _ in range(size * 10): # walk widely
        current = next_ptr[current]
    return current

def _worker_contention(lock, shared_val, iterations):
    for _ in range(iterations):
        with lock:
            shared_val.value += 1

def _worker_producer(queue, count):
    for i in range(count):
        queue.put(i)

def _worker_consumer(queue, count):
    processed = 0
    for _ in range(count):
        _ = queue.get()
        processed += 1
    return processed

# --- MC Workload Class (Now Extra/Systems) ---

class MCWorkloads:
    def __init__(self, num_processes=None):
        self.num_processes = num_processes if num_processes else os.cpu_count()

    def run_parallel_hashing(self, iterations=20_000):
        with multiprocessing.Pool(self.num_processes) as pool:
            # Distribute iterations across cores
            chunk_iters = max(1, iterations // self.num_processes)
            results = pool.map(_worker_hash_farm, [chunk_iters] * self.num_processes)
        return len(results)

    def run_parallel_compression(self, iterations=1000):
        with multiprocessing.Pool(self.num_processes) as pool:
            chunk_iters = max(1, iterations // self.num_processes)
            results = pool.map(_worker_compress, [chunk_iters] * self.num_processes)
        return sum(results)

    def run_monte_carlo(self, iterations=200_000):
        with multiprocessing.Pool(self.num_processes) as pool:
            chunk_iters = max(1, iterations // self.num_processes)
            results = pool.map(_worker_monte_carlo, [chunk_iters] * self.num_processes)
        return sum(results)

    def run_tile_image(self, iterations=100):
        with multiprocessing.Pool(self.num_processes) as pool:
            chunk_iters = max(1, iterations // self.num_processes)
            results = pool.map(_worker_image_tile, [chunk_iters] * self.num_processes)
        return sum(results)

    def run_batch_ray(self, iterations=100_000):
        with multiprocessing.Pool(self.num_processes) as pool:
            chunk_iters = max(1, iterations // self.num_processes)
            results = pool.map(_worker_ray_batch, [chunk_iters] * self.num_processes)
        return sum(results)

    def run_stream_memory(self, size=100_000):
        # size is array size per core
        with multiprocessing.Pool(self.num_processes) as pool:
            results = pool.map(_worker_stream_triad, [size] * self.num_processes)
        return sum(results)

    def run_pointer_chase(self, size=10_000):
        with multiprocessing.Pool(self.num_processes) as pool:
            results = pool.map(_worker_pointer_chase, [size] * self.num_processes)
        return sum(results)

    def run_contention(self, iterations=1000):
        # Use Manager for shared state
        manager = multiprocessing.Manager()
        lock = manager.Lock()
        shared_val = manager.Value('i', 0)
        
        chunk_iters = max(1, iterations // self.num_processes)
        processes = []
        for _ in range(self.num_processes):
            p = multiprocessing.Process(target=_worker_contention, args=(lock, shared_val, chunk_iters))
            processes.append(p)
            p.start()
        
        for p in processes:
            p.join()
            
        return shared_val.value

    def run_producer_consumer(self, items=200):
        # Split processes into half producers, half consumers (roughly)
        manager = multiprocessing.Manager()
        queue = manager.Queue()
        
        # Ensure at least 1 producer and 1 consumer
        n_prod = max(1, self.num_processes // 2)
        n_cons = max(1, self.num_processes - n_prod)
        
        items_per_prod = items // n_prod
        total_items = items_per_prod * n_prod
        items_per_cons = total_items // n_cons # simplified
        
        procs = []
        for _ in range(n_prod):
            p = multiprocessing.Process(target=_worker_producer, args=(queue, items_per_prod))
            procs.append(p)
            p.start()
            
        for _ in range(n_cons):
            p = multiprocessing.Process(target=_worker_consumer, args=(queue, items_per_cons))
            procs.append(p)
            p.start()
            
        for p in procs:
            p.join()
        
        return total_items

    # Mixed Workloads (Simplified mappings for suite structure)
    def run_work_stealing_sim(self, iterations=1000):
        # We simulate this by just running a generic map with many small tasks
        # The Pool itself implements work distribution
        tasks = [10] * iterations # Many small tasks
        with multiprocessing.Pool(self.num_processes) as pool:
            results = pool.map(_worker_monte_carlo, tasks) # reusing monte carlo as "work"
        return len(results)
