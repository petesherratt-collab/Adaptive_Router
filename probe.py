import hashlib
import time


def run_probe(iterations=50000):
    value = b"adaptive-router-probe"
    started = time.perf_counter()
    for _ in range(iterations):
        value = hashlib.sha256(value).digest()
    return round((time.perf_counter() - started) * 1000, 3)
