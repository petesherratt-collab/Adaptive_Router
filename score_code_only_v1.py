"""Score the code-only reading rules on the V3 texts. Makes no provider call.

Accuracy of ``fast_path_code_only_v1.RULES`` on every distinct text (by shape
and label, with a confusion table) and on the job stream. Run only after the
texts were hand-checked and their hash recorded.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import fast_path_code_only_v1 as code_only
import fast_path_planned_bench_v3 as bench


def score(prose, stream_length=bench.STREAM_LENGTH):
    texts, jobs = {}, {}
    for shape in bench.SHAPES:
        name, rule = shape["name"], code_only.RULES[shape["name"]]
        confusion = collections.Counter()
        misses = []
        for label, items in prose[name].items():
            for text in items:
                got = rule(text)
                confusion[f"{label}->{got}"] += 1
                if got != label:
                    misses.append({"label": label, "got": got, "text": text})
        total = sum(confusion.values())
        texts[name] = {"texts": total, "correct": total - len(misses),
                       "confusion": dict(sorted(confusion.items())), "misses": misses}
        field, label_name, _ = shape["reading"]
        instances = bench.stream(shape, length=stream_length, prose=prose)
        hits = sum(rule(inputs[field]) == labels[label_name] for inputs, labels in instances)
        jobs[name] = {"jobs": len(instances), "correct": hits}
    return {
        "texts": {"correct": sum(v["correct"] for v in texts.values()),
                  "total": sum(v["texts"] for v in texts.values())},
        "stream": {"correct": sum(v["correct"] for v in jobs.values()),
                   "total": sum(v["jobs"] for v in jobs.values())},
        "per_shape_texts": texts, "per_shape_stream": jobs,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = score(bench.load_prose())
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    for name, entry in result["per_shape_texts"].items():
        print(f"{name:16} texts {entry['correct']}/{entry['texts']}  stream "
              f"{result['per_shape_stream'][name]['correct']}/{result['per_shape_stream'][name]['jobs']}")
    print("overall texts", result["texts"], "stream", result["stream"])


if __name__ == "__main__":
    main()
