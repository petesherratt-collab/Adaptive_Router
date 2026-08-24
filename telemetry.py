from datetime import datetime, timezone
import os
import psutil

SAMPLE_INTERVAL_SECONDS = 0.1


def collect_system_metrics():
    swap_before = psutil.swap_memory()
    cpu_percent = psutil.cpu_percent(interval=SAMPLE_INTERVAL_SECONDS)
    memory, swap = psutil.virtual_memory(), psutil.swap_memory()
    page_size = os.sysconf("SC_PAGE_SIZE")
    swap_in_bytes = max(0, swap.sin - swap_before.sin)
    swap_out_bytes = max(0, swap.sout - swap_before.sout)
    return {"cpu_percent": cpu_percent, "load_average": list(os.getloadavg()),
            "available_ram_mb": memory.available / 1048576, "ram_percent": memory.percent,
            "swap_used_mb": swap.used / 1048576, "swap_percent": swap.percent,
            "swap_activity_sample_seconds": SAMPLE_INTERVAL_SECONDS,
            "swap_in_bytes": swap_in_bytes, "swap_in_pages": swap_in_bytes // page_size,
            "swap_out_bytes": swap_out_bytes, "swap_out_pages": swap_out_bytes // page_size,
            "timestamp": datetime.now(timezone.utc).isoformat()}


def system_is_healthy(metrics, config, local_model_resident=False):
    routing = config["routing"]
    if metrics["swap_out_pages"] > routing["active_swap_out_pages_threshold"]:
        return False, "ACTIVE_SWAP_PRESSURE"
    if not local_model_resident and metrics["available_ram_mb"] < routing["minimum_available_ram_mb"]:
        return False, "LOW_RAM"
    return True, None
