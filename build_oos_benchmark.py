"""Build the frozen out-of-sample routing benchmark v1."""

import argparse
from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "benchmark_oos_v1.json"

FAMILY_COUNTS = {
    "structured_extraction": 10,
    "sentiment": 5,
    "json_format": 5,
    "priority": 5,
    "markdown_bullets": 5,
    "key_value_labels": 5,
    "transformation": 5,
}

LOCAL_FAMILIES = {
    "structured_extraction",
    "sentiment",
    "json_format",
}

REMOTE_FAMILIES = set(FAMILY_COUNTS) - LOCAL_FAMILIES

SENTIMENT_RUBRIC = (
    "Use this rubric: Positive means a clearly favourable evaluation; "
    "Negative means a clearly unfavourable evaluation; Neutral means a "
    "factual statement without evaluation. "
)

PRIORITY_RUBRIC = (
    "Use this rubric: High means a present safety or security incident, "
    "work blocked now, or an explicit deadline within 24 hours. Medium "
    "means action is required after 24 hours but within seven days, with "
    "no present safety or security incident and no current blocker. Low "
    "means no action is required, or the explicit deadline is more than "
    "seven days away. "
)


def task(
    task_id,
    task_class,
    capability_family,
    normalization,
    prompt,
    expected,
):
    return {
        "task_id": task_id,
        "task_class": task_class,
        "capability_family": capability_family,
        "normalization": normalization,
        "prompt": prompt,
        "expected": expected,
    }


def structured_tasks():
    definitions = [
        (
            "oos_extract_person",
            "name, age",
            "Employee record: Maya Chen is 29 years old.",
            {"name": "Maya Chen", "age": 29},
        ),
        (
            "oos_extract_event",
            "event, date, city",
            (
                "Schedule record: accessibility workshop; "
                "date 2026-11-03; city Bristol."
            ),
            {
                "event": "accessibility workshop",
                "date": "2026-11-03",
                "city": "Bristol",
            },
        ),
        (
            "oos_extract_order",
            "order_id, total, currency",
            "Order record: C-318; total 73.20; currency USD.",
            {
                "order_id": "C-318",
                "total": 73.2,
                "currency": "USD",
            },
        ),
        (
            "oos_extract_weather",
            "city, temperature_c, condition",
            (
                "Weather record: city Glasgow; temperature 11 "
                "degrees Celsius; condition rain."
            ),
            {
                "city": "Glasgow",
                "temperature_c": 11,
                "condition": "rain",
            },
        ),
        (
            "oos_extract_book",
            "title, author, year",
            (
                "Catalogue record: Kindred; author Octavia E. Butler; "
                "year 1979."
            ),
            {
                "title": "Kindred",
                "author": "Octavia E. Butler",
                "year": 1979,
            },
        ),
        (
            "oos_extract_shipment",
            "tracking_id, status, carrier",
            (
                "Shipment record: tracking ID ZX-4401; status "
                "in_transit; carrier DPD."
            ),
            {
                "tracking_id": "ZX-4401",
                "status": "in_transit",
                "carrier": "DPD",
            },
        ),
        (
            "oos_extract_device",
            "asset_id, operating_system, version",
            (
                "Device record: asset ID LT-882; operating system "
                "Fedora; version 42."
            ),
            {
                "asset_id": "LT-882",
                "operating_system": "Fedora",
                "version": 42,
            },
        ),
        (
            "oos_extract_meeting",
            "topic, time, room",
            (
                "Meeting record: topic budget review; time 14:30; "
                "room Cedar."
            ),
            {
                "topic": "budget review",
                "time": "14:30",
                "room": "Cedar",
            },
        ),
        (
            "oos_extract_product",
            "sku, quantity, unit_price",
            (
                "Product record: SKU P-77; quantity 12; "
                "unit price 4.25."
            ),
            {
                "sku": "P-77",
                "quantity": 12,
                "unit_price": 4.25,
            },
        ),
        (
            "oos_extract_train",
            "origin, destination, departure",
            (
                "Train record: origin Norwich; destination Cambridge; "
                "departure 09:17."
            ),
            {
                "origin": "Norwich",
                "destination": "Cambridge",
                "departure": "09:17",
            },
        ),
    ]

    return [
        task(
            task_id,
            "extract_structured",
            "structured_extraction",
            "structured_json",
            (
                "Extract one JSON object from the source record. "
                f"Required keys exactly: {keys}. "
                "Preserve source spelling, capitalization, underscores, and "
                "punctuation in string values. Represent numeric values as JSON "
                f"numbers. Do not infer unstated values. Output only JSON. Source: {source}"
            ),
            expected,
        )
        for task_id, keys, source, expected in definitions
    ]


def sentiment_tasks():
    definitions = [
        (
            "oos_sentiment_positive_service",
            "The support team resolved everything brilliantly.",
            "positive",
        ),
        (
            "oos_sentiment_negative_device",
            "The replacement device is unreliable and frustrating.",
            "negative",
        ),
        (
            "oos_sentiment_neutral_delivery",
            "The parcel arrived at 14:10 on Tuesday.",
            "neutral",
        ),
        (
            "oos_sentiment_positive_report",
            "This report is exceptionally clear and useful.",
            "positive",
        ),
        (
            "oos_sentiment_negative_room",
            "The meeting room was dirty and unpleasant.",
            "negative",
        ),
    ]

    return [
        task(
            task_id,
            "classification",
            "sentiment",
            "text",
            (
                SENTIMENT_RUBRIC
                + "Classify the following text. Output exactly one "
                f"label: Positive, Negative, or Neutral. Text: {text}"
            ),
            expected,
        )
        for task_id, text, expected in definitions
    ]


def json_format_tasks():
    definitions = [
        (
            "oos_json_server",
            "Host is edge-7 and port is 8443.",
            {"host": "edge-7", "port": 8443},
        ),
        (
            "oos_json_contact",
            "First name is Leila and postcode is SE18 6HQ.",
            {
                "first_name": "Leila",
                "postcode": "SE18 6HQ",
            },
        ),
        (
            "oos_json_coordinates",
            "The x value is 17 and the y value is -4.",
            {"x": 17, "y": -4},
        ),
        (
            "oos_json_inventory",
            "SKU is R-204 and in_stock is true.",
            {"sku": "R-204", "in_stock": True},
        ),
        (
            "oos_json_ticket",
            "Ticket id is Q-91 and open is false.",
            {"id": "Q-91", "open": False},
        ),
    ]

    results = []

    for task_id, source, expected in definitions:
        keys = ", ".join(expected)

        results.append(task(
            task_id,
            "format",
            "json_format",
            "structured_json",
            (
                "Format the supplied fields as one JSON object. "
                f"Use exactly these lowercase keys: {keys}. "
                "Use the supplied values without modification. Include "
                f"no additional keys or prose. Source: {source}"
            ),
            expected,
        ))

    return results


def priority_tasks():
    definitions = [
        (
            "oos_priority_high_deadline",
            (
                "The signed response must be submitted in six hours. "
                "Work is not currently blocked and there is no safety "
                "or security incident."
            ),
            "high",
        ),
        (
            "oos_priority_high_blocked",
            (
                "Deployment work is blocked now because the required "
                "certificate is missing. There is no safety or security "
                "incident."
            ),
            "high",
        ),
        (
            "oos_priority_medium_three_days",
            (
                "Approve the routine supplier form within three days. "
                "Nothing is blocked and there is no safety or security "
                "incident."
            ),
            "medium",
        ),
        (
            "oos_priority_medium_five_days",
            (
                "Update the ordinary rota within five days. Nothing is "
                "blocked and there is no safety or security incident."
            ),
            "medium",
        ),
        (
            "oos_priority_low_fourteen_days",
            (
                "Review the optional colour choices in fourteen days. "
                "Nothing is blocked and there is no safety or security "
                "incident."
            ),
            "low",
        ),
    ]

    return [
        task(
            task_id,
            "classification",
            "priority",
            "text",
            (
                PRIORITY_RUBRIC
                + "Classify the following item. Output exactly one "
                f"label: High, Medium, or Low. Item: {text}"
            ),
            expected,
        )
        for task_id, text, expected in definitions
    ]


def bullet_tasks():
    definitions = [
        (
            "oos_bullets_fruit",
            ["pear", "plum", "kiwi"],
        ),
        (
            "oos_bullets_stages",
            ["collect", "verify"],
        ),
        (
            "oos_bullets_directions",
            ["north", "east", "south", "west"],
        ),
        (
            "oos_bullets_codes",
            ["AX-1", "BY-2", "CZ-3"],
        ),
        (
            "oos_bullets_dates",
            ["2026-10-02", "2026-10-09"],
        ),
    ]

    results = []

    for task_id, items in definitions:
        joined = "; ".join(items)
        expected = "\n".join(f"- {item}" for item in items)

        results.append(task(
            task_id,
            "format",
            "markdown_bullets",
            "text",
            (
                f"Output exactly {len(items)} Markdown bullet lines in "
                "the supplied order. Every line must contain the literal "
                "hyphen marker followed by exactly one space and then "
                "the exact item text. Include no heading, blank line, "
                f"or surrounding prose. Items: {joined}."
            ),
            expected,
        ))

    return results


def label_tasks():
    definitions = [
        (
            "oos_labels_account",
            [
                ("account_id", "AC-55"),
                ("state", "active"),
            ],
        ),
        (
            "oos_labels_sensor",
            [
                ("sensor", "S-9"),
                ("reading", "18.4"),
                ("unit", "C"),
            ],
        ),
        (
            "oos_labels_route",
            [
                ("origin", "Woolwich"),
                ("destination", "Lewisham"),
            ],
        ),
        (
            "oos_labels_build",
            [
                ("build_id", "B-602"),
                ("result", "passed"),
                ("duration_s", "47"),
            ],
        ),
        (
            "oos_labels_owner",
            [
                ("owner", "Nadia"),
                ("team", "Orchid"),
            ],
        ),
    ]

    results = []

    for task_id, fields in definitions:
        specification = "; ".join(
            f"{key}={value}" for key, value in fields
        )
        expected = "\n".join(
            f"{key}: {value}" for key, value in fields
        )
        keys = ", ".join(key for key, value in fields)

        results.append(task(
            task_id,
            "format",
            "key_value_labels",
            "text",
            (
                f"Output exactly {len(fields)} lines in this order using "
                f"these exact lowercase keys: {keys}. Every line must use "
                "the exact format key, then a colon, then exactly one "
                "space, then the supplied value. Preserve every value "
                "exactly. Include no additional lines or prose. "
                f"Fields: {specification}."
            ),
            expected,
        ))

    return results


def transformation_tasks():
    definitions = [
        (
            "oos_transform_reverse",
            (
                "Reverse the characters in the string `signal`. "
                "Output only the transformed string."
            ),
            "langis",
        ),
        (
            "oos_transform_uppercase",
            (
                "Convert every lowercase letter in the string "
                "`edge node` to uppercase. Preserve the space and output "
                "only the transformed string."
            ),
            "EDGE NODE",
        ),
        (
            "oos_transform_remove_spaces",
            (
                "Remove every space from the string `paired sample` and "
                "make no other change. Output only the transformed string."
            ),
            "pairedsample",
        ),
        (
            "oos_transform_underscores",
            (
                "Replace every space in the string `frozen policy check` "
                "with an underscore. Preserve all letters and output only "
                "the transformed string."
            ),
            "frozen_policy_check",
        ),
        (
            "oos_transform_replace_o",
            (
                "Replace every lowercase letter o in the string "
                "`local model` with the digit 0 and make no other change. "
                "Output only the transformed string."
            ),
            "l0cal m0del",
        ),
    ]

    return [
        task(
            task_id,
            "transform",
            "transformation",
            "text",
            prompt,
            expected,
        )
        for task_id, prompt, expected in definitions
    ]


def build_tasks():
    families = {
        "structured_extraction": structured_tasks(),
        "sentiment": sentiment_tasks(),
        "json_format": json_format_tasks(),
        "priority": priority_tasks(),
        "markdown_bullets": bullet_tasks(),
        "key_value_labels": label_tasks(),
        "transformation": transformation_tasks(),
    }

    tasks = []

    for index in range(5):
        tasks.extend([
            families["structured_extraction"][index],
            families["sentiment"][index],
            families["json_format"][index],
            families["priority"][index],
            families["markdown_bullets"][index],
            families["key_value_labels"][index],
            families["transformation"][index],
            families["structured_extraction"][index + 5],
        ])

    return tasks


def validate(tasks):
    if len(tasks) != 40:
        raise ValueError(
            f"expected 40 tasks, found {len(tasks)}"
        )

    task_ids = [item["task_id"] for item in tasks]

    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be unique")

    required = {
        "task_id",
        "task_class",
        "capability_family",
        "normalization",
        "prompt",
        "expected",
    }

    for item in tasks:
        missing = required - set(item)

        if missing:
            raise ValueError(
                f"{item.get('task_id')} missing {sorted(missing)}"
            )

        if item["normalization"] not in {
            "structured_json",
            "text",
        }:
            raise ValueError(
                f"unsupported normalization: {item['task_id']}"
            )

    counts = Counter(
        item["capability_family"] for item in tasks
    )

    if dict(counts) != FAMILY_COUNTS:
        raise ValueError(
            f"family counts differ: {dict(counts)}"
        )

    local_count = sum(
        item["capability_family"] in LOCAL_FAMILIES
        for item in tasks
    )
    remote_count = sum(
        item["capability_family"] in REMOTE_FAMILIES
        for item in tasks
    )

    if (local_count, remote_count) != (20, 20):
        raise ValueError(
            "fine policy must split tasks 20 local / 20 remote"
        )

    return counts


def build_document():
    tasks = build_tasks()
    counts = validate(tasks)

    document = {
        "version": 3,
        "suite_id": "oos_validation_v1",
        "task_count": len(tasks),
        "capability_family_counts": dict(counts),
        "tasks": tasks,
    }

    return document


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--write",
        action="store_true",
    )
    args = parser.parse_args(argv)

    document = build_document()

    print(f"Suite: {document['suite_id']}")
    print(f"Tasks: {document['task_count']}")
    print(
        "Families:",
        document["capability_family_counts"],
    )
    print("Fine-policy split: local=20 remote=20")

    if not args.write:
        print(
            "Dry run only; pass --write to create the benchmark."
        )
        return

    if args.output.exists():
        raise FileExistsError(
            f"refusing to overwrite {args.output}"
        )

    args.output.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
