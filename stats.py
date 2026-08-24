from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics


def wilson_interval(successes, total, z=1.959963984540054):
    if total == 0: return (0.0, 0.0)
    p, z2 = successes / total, z * z
    centre = (p + z2/(2*total)) / (1 + z2/total)
    margin = z * math.sqrt((p*(1-p) + z2/(4*total))/total) / (1 + z2/total)
    return centre-margin, centre+margin


def read_runs(path):
    if not Path(path).exists(): return []
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: continue
    return rows


def task_statistics(rows, minimum=30):
    groups = defaultdict(lambda: {"N": 0, "successes": 0})
    for row in rows:
        task = row.get("task_class", "unknown")
        if row.get("local", {}).get("attempted"):
            groups[task]["N"] += 1
            groups[task]["successes"] += row.get("decision", {}).get("reason") == "LOCAL_ACCEPTED"
    for value in groups.values():
        n, successes = value["N"], value["successes"]
        value.update(rate=successes/n if n else 0, wilson_95=wilson_interval(successes, n),
                     evidence="SUFFICIENT" if n >= minimum else "INSUFFICIENT_EVIDENCE")
    return dict(groups)


def rolling_median(rows, metric, days=7, minimum=30, now=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days); values = []
    for row in rows:
        try: timestamp = datetime.fromisoformat(row["timestamp"])
        except (KeyError, ValueError): continue
        local, system = row.get("local", {}), row.get("system", {})
        healthy = row.get("decision", {}).get("trigger") not in {"LOW_RAM", "ACTIVE_SWAP_PRESSURE", "LOCAL_TIMEOUT", "LOCAL_ERROR"}
        if timestamp < cutoff or not healthy or (local.get("attempted") and not local.get("success")): continue
        value = row.get("probe_ms") if metric == "probe_ms" else local.get(metric)
        if isinstance(value, (int, float)): values.append(value)
    return {"N": len(values), "median": statistics.median(values) if len(values) >= minimum else None,
            "status": "OK" if len(values) >= minimum else "INSUFFICIENT_BASELINE_DATA"}


def render_report(rows, config):
    minimum = config["statistics"]["minimum_evidence_count"]
    accepted = sum(r.get("decision", {}).get("reason") == "LOCAL_ACCEPTED" for r in rows)
    escalated = sum(r.get("local", {}).get("attempted") and r.get("decision", {}).get("route") == "remote" for r in rows)
    defaults = sum(r.get("decision", {}).get("trigger") == "REMOTE_DEFAULT_TASK" for r in rows)
    lines = ["=== Adaptive Router Statistics ===", "", f"Total requests: {len(rows)}", "", "LOCAL",
             f"Accepted:         {accepted}", f"Failed/escalated: {escalated}", "", "REMOTE", f"Default routed:   {defaults}", "", "By task:"]
    for task, data in sorted(task_statistics(rows, minimum).items()):
        lo, hi = data["wilson_95"]
        lines += ["", task, f"  local accepted: {data['successes']}/{data['N']}",
                  f"  rate: {data['rate']:.1%}", f"  Wilson 95%: {lo:.1%} to {hi:.1%}", f"  {data['evidence']}"]
    lines += ["", "Rolling healthy baselines:"]
    for metric in ("probe_ms", "ttft_ms", "tokens_per_second"):
        baseline = rolling_median(rows, metric, config["statistics"]["baseline_days"], minimum)
        shown = f"{baseline['median']:.3f}" if baseline["median"] is not None else "n/a"
        lines.append(f"  {metric}: median={shown}, N={baseline['N']} ({baseline['status']})")
    return "\n".join(lines)
