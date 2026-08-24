import hashlib


def should_shadow(request_id, sample_rate, salt):
    if not 0 <= sample_rate <= 1:
        raise ValueError("sample_rate must be between 0 and 1")
    number = int.from_bytes(hashlib.sha256(f"{request_id}{salt}".encode()).digest()[:8], "big")
    return number / 2**64 < sample_rate
