import math
import random
import time
import multiprocessing

# --- Fixed scene (module constants; never change size/complexity across calls
# so every render_frame() call does identical work -- wall-clock time is a pure
# CPU-speed signal, not a function of problem size). ---

WIDTH = 128
HEIGHT = 128
SAMPLES_PER_PIXEL = 2
MAX_BOUNCES = 3
DEFAULT_SEED = 1234

SPHERES = [
    {"center": (0.0, -1000.0, 0.0), "radius": 1000.0, "albedo": 0.5, "reflective": False},  # ground
    {"center": (0.0, 1.0, 0.0), "radius": 1.0, "albedo": 0.85, "reflective": False},
    {"center": (2.2, 1.0, -1.0), "radius": 1.0, "albedo": 0.9, "reflective": True},
    {"center": (-2.0, 0.8, 1.0), "radius": 0.8, "albedo": 0.75, "reflective": False},
]

LIGHT_POS = (5.0, 8.0, 3.0)
LIGHT_INTENSITY = 60.0

CAMERA_ORIGIN = (0.0, 1.5, 6.0)
CAMERA_TARGET = (0.0, 1.0, 0.0)
CAMERA_UP = (0.0, 1.0, 0.0)
FOV_DEGREES = 60.0
EPS = 1e-4


# --- Vector helpers (plain tuples, no numpy) ---

def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return math.sqrt(_dot(a, a))


def _normalize(a):
    l = _length(a)
    if l == 0:
        return a
    return (a[0] / l, a[1] / l, a[2] / l)


def _reflect(d, n):
    return _sub(d, _scale(n, 2 * _dot(d, n)))


# --- Fixed camera basis (computed once at import time) ---

_forward = _normalize(_sub(CAMERA_TARGET, CAMERA_ORIGIN))
_right = _normalize(_cross(_forward, CAMERA_UP))
_true_up = _cross(_right, _forward)
_half_height = math.tan(math.radians(FOV_DEGREES) / 2.0)
_half_width = _half_height * (WIDTH / HEIGHT)


def _camera_ray(u, v):
    px = (2 * u - 1) * _half_width
    py = (1 - 2 * v) * _half_height
    d = _add(_scale(_right, px), _add(_scale(_true_up, py), _forward))
    return _normalize(d)


def _sphere_intersect(orig, direction, sphere):
    oc = _sub(orig, sphere["center"])
    b = _dot(oc, direction)
    c = _dot(oc, oc) - sphere["radius"] * sphere["radius"]
    disc = b * b - c
    if disc < 0:
        return None
    sqrt_disc = math.sqrt(disc)
    t1 = -b - sqrt_disc
    t2 = -b + sqrt_disc
    if t1 > EPS:
        return t1
    if t2 > EPS:
        return t2
    return None


def _intersect_scene(orig, direction):
    hit_t, hit_sphere = None, None
    for sphere in SPHERES:
        t = _sphere_intersect(orig, direction, sphere)
        if t is not None and (hit_t is None or t < hit_t):
            hit_t, hit_sphere = t, sphere
    return hit_t, hit_sphere


def _random_hemisphere(n, rng):
    u1 = rng.random()
    u2 = rng.random()
    r = math.sqrt(u1)
    theta = 2 * math.pi * u2
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    z = math.sqrt(max(0.0, 1 - u1))

    a = (0.0, 1.0, 0.0) if abs(n[0]) > 0.9 else (1.0, 0.0, 0.0)
    t = _normalize(_cross(a, n))
    b = _cross(n, t)
    d = _add(_scale(t, x), _add(_scale(b, y), _scale(n, z)))
    return _normalize(d)


def _trace(orig, direction, depth, rng):
    if depth <= 0:
        return 0.0

    hit_t, sphere = _intersect_scene(orig, direction)
    if sphere is None:
        return 0.1 + 0.05 * direction[1]  # sky gradient

    point = _add(orig, _scale(direction, hit_t))
    normal = _normalize(_sub(point, sphere["center"]))
    bias_point = _add(point, _scale(normal, EPS))

    if sphere["reflective"]:
        reflected = _reflect(direction, normal)
        return 0.8 * _trace(bias_point, reflected, depth - 1, rng)

    to_light = _normalize(_sub(LIGHT_POS, point))
    in_shadow = False
    for sphere2 in SPHERES:
        if sphere2 is sphere:
            continue
        if _sphere_intersect(bias_point, to_light, sphere2) is not None:
            in_shadow = True
            break

    ndotl = max(0.0, _dot(normal, to_light))
    dist2 = max(1.0, _dot(_sub(LIGHT_POS, point), _sub(LIGHT_POS, point)))
    direct = 0.0 if in_shadow else (ndotl * LIGHT_INTENSITY / dist2)

    indirect = 0.0
    if depth > 1:
        bounce_dir = _random_hemisphere(normal, rng)
        indirect = 0.5 * _trace(bias_point, bounce_dir, depth - 1, rng)

    return sphere["albedo"] * (0.15 + 0.85 * min(1.0, direct) + indirect)


def _render_tile(y_start, y_end, width, height, samples_per_pixel, max_bounces, seed, return_pixels=False):
    """Top-level, picklable render worker: path-traces rows [y_start, y_end)
    of the fixed scene. By default only a checksum is returned (not pixel
    data) -- only the timing/CPU cost matters for stress/stability scoring,
    so we keep the IPC payload tiny. Pass return_pixels=True (used only by
    the Stress Test's live render preview) to additionally get back a
    grayscale byte per pixel for this tile's rows."""
    rng = random.Random(seed + y_start)
    checksum = 0.0
    pixel_bytes = bytearray() if return_pixels else None
    for y in range(y_start, y_end):
        for x in range(width):
            pixel_val = 0.0
            for _ in range(samples_per_pixel):
                u = (x + rng.random()) / width
                v = (y + rng.random()) / height
                direction = _camera_ray(u, v)
                pixel_val += _trace(CAMERA_ORIGIN, direction, max_bounces, rng)
            avg = pixel_val / samples_per_pixel
            checksum += avg
            if return_pixels:
                pixel_bytes.append(max(0, min(255, int(avg * 255))))
    return checksum, (bytes(pixel_bytes) if return_pixels else None)


def render_frame(num_workers=None, width=None, height=None,
                  samples_per_pixel=None, max_bounces=None, seed=DEFAULT_SEED, return_pixels=False):
    """Renders one frame of the fixed scene, tile-parallel across num_workers
    cores. Returns wall-clock duration in seconds -- the score for both the
    Stress Test's Render mode and the Stability Test's default workload.
    Pass return_pixels=True to additionally get back (duration, image_bytes)
    -- a width*height grayscale buffer -- for live preview purposes; this is
    purely additive and never changes the duration/scoring path, so existing
    callers that don't pass it see identical behavior to before.

    width/height/samples_per_pixel/max_bounces default to the fixed module
    constants; overrides exist only so smoke tests (verify_stress.py,
    verify_stability.py) can use a tiny resolution for speed -- production
    call sites should leave these at their defaults so every sample/frame is
    genuinely identical work."""
    num_workers = num_workers or multiprocessing.cpu_count()
    width = width or WIDTH
    height = height or HEIGHT
    samples_per_pixel = samples_per_pixel or SAMPLES_PER_PIXEL
    max_bounces = max_bounces if max_bounces is not None else MAX_BOUNCES

    rows_per_tile = max(1, -(-height // num_workers))  # ceil division
    tiles = []
    y = 0
    while y < height:
        y_end = min(height, y + rows_per_tile)
        tiles.append((y, y_end, width, height, samples_per_pixel, max_bounces, seed, return_pixels))
        y = y_end

    start = time.perf_counter()
    with multiprocessing.Pool(num_workers) as pool:
        tile_results = pool.starmap(_render_tile, tiles)
    duration = time.perf_counter() - start

    if not return_pixels:
        return duration
    image_bytes = b"".join(pixels for _, pixels in tile_results)
    return duration, image_bytes
