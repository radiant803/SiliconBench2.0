import time
import math
import random
import hashlib
import zlib
import re
import sys

# --- Constants & Helpers ---
# Adjust these ITERATIONS to make each test take roughly 1-3 seconds on a modern CPU
# for a "real" run. We can have a 'calibration' pass or just fixed constants.
# For now, fixed constants that are reasonably high. The Engine can scale them.

class SCWorkloads:
    @staticmethod
    def integer_alu_mix(iterations=1_000_000):
        """
        Stresses Integer ALU: Add, Sub, Mul, Div, Bitwise.
        """
        res = 0
        for i in range(iterations):
            # perform a mix of operations
            # carefully chosen to avoid overflow or trivial optimization
            a = i & 0xFFFF
            b = (i >> 3) & 0xFFFF
            res += (a * b) + (a ^ b) - (a | b)
            res = (res << 1) ^ (i & 0xFF)
        return res

    @staticmethod
    def branchy_code(iterations=500_000):
        """
        Heavy branching logic to stress branch predictor.
        """
        res = 0
        # Pre-compute a random table to make branches unpredictable
        # We use a fixed seed for reproducibility
        rng = random.Random(42)
        table = [rng.randint(0, 100) for _ in range(1024)]
        
        for i in range(iterations):
            val = table[i % 1024]
            # Complex condition chain
            if val < 20:
                res += 1
            elif val < 40:
                res -= 1
            elif val < 50:
                res *= 2
            elif val < 70:
                if (i % 2) == 0:
                    res += 5
                else:
                    res -= 5
            else:
                res ^= val
        return res

    @staticmethod
    def string_processing(iterations=50_000):
        """
        Regex and String manipulation.
        """
        text = "The quick brown fox jumps over the lazy dog. " * 50
        pattern = re.compile(r"\b\w{4}\b") # find 4 letter words
        count = 0
        for _ in range(iterations):
            # Tokenize manually
            words = text.split()
            # Regex search
            matches = pattern.findall(text)
            count += len(matches) + len(words)
            # String slicing/concatenation
            _ = text[10:50] + text[0:5]
        return count

    @staticmethod
    def hashing(iterations=50_000):
        """
        SHA-256 Hashing.
        """
        data = b"Benchmarks are fun!" * 100
        digest = b""
        for _ in range(iterations):
            digest = hashlib.sha256(data + digest).digest()
        return digest

    @staticmethod
    def encryption_aes_sim(iterations=20_000):
        """
        Simulated AES-like encryption (Table lookups + XOR in rounds).
        Native Python AES is too slow for 1:1 comp with C, but good for relative generic stress.
        """
        # Simulated S-Box (just a simple mapping)
        sbox = list(range(256))
        # Swap some values to simulate substitution
        for i in range(0, 256, 2):
            sbox[i], sbox[i+1] = sbox[i+1], sbox[i]
            
        state = [i for i in range(16)] # 128-bit block
        
        for _ in range(iterations):
            # 10 rounds
            for _ in range(10):
                # SubBytes
                state = [sbox[b] for b in state]
                # ShiftRows (simulated)
                state = state[1:] + state[:1]
                # MixColumns (simulated simplified XOR churn)
                new_state = []
                for j in range(0, 16, 4):
                    new_state.append(state[j] ^ state[j+1])
                    new_state.append(state[j+1] ^ state[j+2])
                    new_state.append(state[j+2] ^ state[j+3])
                    new_state.append(state[j+3] ^ state[j])
                state = new_state
        return state[0]

    @staticmethod
    def compression_lz_sim(iterations=200):
        """
        Uses zlib (LZ77+Huffman) to compress data.
        """
        data = (b"RepeatingPattern" * 50 + b"RandomAttributes" * 50) * 10
        total_len = 0
        for _ in range(iterations):
            comp = zlib.compress(data, level=6)
            decomp = zlib.decompress(comp)
            total_len += len(decomp)
        return total_len

    @staticmethod
    def matrix_math(iterations=10_000):
        """
        3x3 and 4x4 Matrix multiplication.
        """
        mat_a = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 1, 2, 3], [4, 5, 6, 7]]
        mat_b = [[2, 0, 1, 2], [1, 2, 0, 1], [0, 1, 2, 0], [2, 1, 0, 2]]
        
        def mat_mul_4x4(a, b):
            c = [[0]*4 for _ in range(4)]
            for i in range(4):
                for j in range(4):
                    for k in range(4):
                        c[i][j] += a[i][k] * b[k][j]
            return c

        final_val = 0
        for _ in range(iterations):
            res = mat_mul_4x4(mat_a, mat_b)
            final_val += res[0][0]
        return final_val

    @staticmethod
    def fft_sim(iterations=5_000):
        """
        Small FFT simulation using recusion.
        """
        def fft(x):
            N = len(x)
            if N <= 1: return x
            even = fft(x[0::2])
            odd =  fft(x[1::2])
            T = [math.e**(-2j * math.pi * k / N) * odd[k] for k in range(N//2)]
            return [even[k] + T[k] for k in range(N//2)] + \
                   [even[k] - T[k] for k in range(N//2)]
        
        input_data = [random.random() for _ in range(64)] # Small N for pure python
        
        for _ in range(iterations):
            _ = fft(input_data)
        return 0

    @staticmethod
    def physics_nbody(iterations=500):
        """
        N-Body gravity simulation. O(N^2).
        """
        # 50 particles
        bodies = [{'x': random.random(), 'y': random.random(), 'vx': 0, 'vy': 0, 'm': 1} for _ in range(50)]
        dt = 0.01
        
        for _ in range(iterations):
            for i, b1 in enumerate(bodies):
                fx, fy = 0.0, 0.0
                for j, b2 in enumerate(bodies):
                    if i == j: continue
                    dx = b2['x'] - b1['x']
                    dy = b2['y'] - b1['y']
                    dist = math.sqrt(dx*dx + dy*dy) + 0.001
                    f = (b1['m'] * b2['m']) / (dist*dist)
                    fx += f * dx / dist
                    fy += f * dy / dist
                b1['vx'] += fx * dt
                b1['vy'] += fy * dt
            
            for b_ in bodies:
                b_['x'] += b_['vx'] * dt
                b_['y'] += b_['vy'] * dt
        return bodies[0]['x']

    @staticmethod
    def ray_trace_kernel(iterations=20_000):
        """
        Ray-sphere intersection check.
        """
        sphere = {'x': 0, 'y': 0, 'z': 5, 'r': 1}
        ray_origin = {'x': 0, 'y': 0, 'z': 0}
        
        hits = 0
        for i in range(iterations):
            # Jitter ray dir
            ray_dir = {'x': (i%100 - 50)/100.0, 'y': (i%100 - 50)/100.0, 'z': 1.0}
            # Normalize
            mag = math.sqrt(ray_dir['x']**2 + ray_dir['y']**2 + ray_dir['z']**2)
            ray_dir['x'] /= mag
            ray_dir['y'] /= mag
            ray_dir['z'] /= mag
            
            # Intersection logic
            oc_x = ray_origin['x'] - sphere['x']
            oc_y = ray_origin['y'] - sphere['y']
            oc_z = ray_origin['z'] - sphere['z']
            
            a = ray_dir['x']**2 + ray_dir['y']**2 + ray_dir['z']**2
            b = 2.0 * (oc_x*ray_dir['x'] + oc_y*ray_dir['y'] + oc_z*ray_dir['z'])
            c = oc_x**2 + oc_y**2 + oc_z**2 - sphere['r']**2
            
            discriminant = b*b - 4*a*c
            if discriminant > 0:
                hits += 1
        return hits

    @staticmethod
    def image_gaussian_blur(iterations=50):
        """
        SImple 3x3 Gaussian blur on a small buffer.
        """
        w, h = 64, 64
        img = [random.randint(0, 255) for _ in range(w*h)]
        
        kernel = [
            1, 2, 1,
            2, 4, 2,
            1, 2, 1
        ]
        
        for _ in range(iterations):
            new_img = [0] * (w*h)
            for y in range(1, h-1):
                for x in range(1, w-1):
                    val = 0
                    for ky in range(-1, 2):
                        for kx in range(-1, 2):
                            p = img[(y+ky)*w + (x+kx)]
                            k = kernel[(ky+1)*3 + (kx+1)]
                            val += p * k
                    new_img[y*w + x] = val // 16
            img = new_img # swap
        return img[0]

    @staticmethod
    def compiler_sim(iterations=20_000):
        """
        Simulate tokenizing and simple parsing.
        """
        code = "int main() { int a = 5; if (a > 2) { return a; } return 0; } " * 10
        
        for _ in range(iterations):
            tokens = []
            i = 0
            while i < len(code):
                char = code[i]
                if char.isspace():
                    i += 1
                elif char.isalpha():
                    start = i
                    while i < len(code) and code[i].isalnum():
                        i += 1
                    tokens.append(('ID', code[start:i]))
                elif char.isdigit():
                    start = i
                    while i < len(code) and code[i].isdigit():
                        i += 1
                    tokens.append(('NUM', code[start:i]))
                else:
                    tokens.append(('SYM', char))
                    i += 1
            # Simple AST walk simulation
            depth = 0
            nodes = 0
            for t in tokens:
                if t[1] == '{': depth += 1
                elif t[1] == '}': depth -= 1
                nodes += 1
        return nodes
