"""Real tasks for the planned-jobs runner, read from ``real_tasks/*.json``.

See ``real_tasks/README.md`` for the file format. Every file whose name does
not start with ``example_`` becomes one job shape; set the environment
variable ``REAL_TASKS_DIR`` to read another folder, or
``REAL_TASKS_INCLUDE_EXAMPLES=1`` to include the example files.

Run ``python fast_path_real_bench.py`` to check the files without calling any
model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

OUTPUT = "result"
STREAM_SEED = 0
FOLDER = Path(os.environ.get("REAL_TASKS_DIR", Path(__file__).resolve().parent / "real_tasks"))
INCLUDE_EXAMPLES = os.environ.get("REAL_TASKS_INCLUDE_EXAMPLES") == "1"


class RealTaskError(ValueError):
    """A real-task file does not follow the format."""


def load_task(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealTaskError(f"{Path(path).name}: not readable JSON ({exc})") from exc
    where = Path(path).name
    if not isinstance(data, dict) or set(data) != {"name", "description", "jobs"}:
        raise RealTaskError(f"{where}: needs exactly the keys name, description, jobs")
    if not isinstance(data["name"], str) or not re.fullmatch(r"\w+", data["name"]):
        raise RealTaskError(f"{where}: name must be letters, digits and underscores")
    if not isinstance(data["description"], str) or len(data["description"].strip()) < 20:
        raise RealTaskError(f"{where}: description is missing or too short")
    jobs = data["jobs"]
    if not isinstance(jobs, list) or len(jobs) < 5:
        raise RealTaskError(f"{where}: needs at least 5 jobs")
    keys = None
    for number, job in enumerate(jobs, start=1):
        if not isinstance(job, dict) or set(job) != {"inputs", "answer"}:
            raise RealTaskError(f"{where}: job {number} needs exactly the keys inputs, answer")
        if not isinstance(job["inputs"], dict) or not job["inputs"]:
            raise RealTaskError(f"{where}: job {number} has no inputs")
        if keys is None:
            keys = set(job["inputs"])
        elif set(job["inputs"]) != keys:
            raise RealTaskError(f"{where}: job {number} has different input keys from job 1")
    for key in sorted(keys):
        if not re.search(rf"(?<![\w]){re.escape(key)}(?![\w])", data["description"]):
            raise RealTaskError(f"{where}: the description never names the input '{key}'")
    return {"name": data["name"], "description": data["description"], "output": OUTPUT,
            "jobs": jobs}


def load_all(folder=FOLDER, include_examples=INCLUDE_EXAMPLES):
    paths = sorted(Path(folder).glob("*.json"))
    shapes = [load_task(p) for p in paths if include_examples or not p.name.startswith("example_")]
    names = [s["name"] for s in shapes]
    if len(names) != len(set(names)):
        raise RealTaskError("two files use the same name")
    return shapes


SHAPES = load_all() if FOLDER.exists() else []
STREAM_LENGTH = max((len(s["jobs"]) for s in SHAPES), default=0)


def stream(shape, seed=STREAM_SEED, length=None):
    jobs = shape["jobs"][: length or len(shape["jobs"])]
    return [(job["inputs"], {}) for job in jobs]


def gold(shape, instances):
    by_inputs = {json.dumps(j["inputs"], sort_keys=True): j["answer"] for j in shape["jobs"]}
    return [{OUTPUT: by_inputs[json.dumps(inputs, sort_keys=True)]} for inputs, _ in instances]


def self_verify():
    shapes = load_all()
    scored = sum(j["answer"] is not None for s in shapes for j in s["jobs"])
    total = sum(len(s["jobs"]) for s in shapes)
    print(f"self_verify OK: {len(shapes)} task kinds, {total} jobs, {scored} with a known answer")
    for shape in shapes:
        print(f"  {shape['name']}: {len(shape['jobs'])} jobs")


if __name__ == "__main__":
    self_verify()
