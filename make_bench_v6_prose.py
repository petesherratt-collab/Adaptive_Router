"""Write the prose for ``fast_path_planned_bench_v6.py``. Makes provider calls.

One call per job shape to a model outside the race roster asks for short
English messages for every label of that shape's reading step. The replies are
kept verbatim in ``fast_path_planned_bench_v6_prose.json``, which this script
never overwrites. The hand check against the planted labels is recorded in the
same file's ``excluded`` list afterwards, before any rule or model reads them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fast_path
from fast_path_planned_bench_v6 import PROSE_PATH, READINGS
import remote

WRITER_MODEL = "mistralai/mistral-large-4-0"
PER_LABEL = 12

CONTEXT = {
    "review_digest": ("short customer reviews of a product, each mainly about one thing", {
        "price": "mainly about the price or value for money", "quality": "mainly about the product's quality",
        "delivery": "mainly about the delivery", "service": "mainly about customer service"}),
    "incident_log": ("one-line notes in an office building's incident log", {
        "low": "a minor issue that can wait", "medium": "a real problem that needs attention today",
        "high": "a serious or dangerous problem needing immediate action"}),
    "expense_lines": ("short descriptions on employees' expense lines", {
        "travel": "a travel cost (fares, fuel, taxis, hotels)", "meals": "a meal or food and drink",
        "equipment": "equipment or hardware bought for work", "other": "anything else"}),
    "survey_comments": ("free-text comments left on a customer survey", {
        "positive": "the comment is positive", "negative": "the comment is negative",
        "neutral": "the comment is neutral or factual"}),
    "menu_check": ("short descriptions of restaurant dishes", {
        "nuts": "the dish contains nuts", "dairy": "the dish contains dairy but no nuts",
        "gluten": "the dish contains gluten but no nuts or dairy",
        "none": "the dish contains none of nuts, dairy or gluten"}),
    "applicant_screen": ("short cover letters from job applicants, from which the role applied for can be told", {
        "engineering": "applying for an engineering role", "design": "applying for a design role",
        "sales": "applying for a sales role"}),
    "delivery_feedback": ("one-line notes couriers record after a delivery attempt", {
        "delivered": "the parcel was delivered in good condition", "missed": "the parcel could not be delivered",
        "damaged": "the parcel was delivered damaged"}),
    "listing_filter": ("short blurbs from flat-to-rent listings", {
        "garden": "the flat has a garden", "balcony": "the flat has a balcony but no garden",
        "none": "the flat has no outdoor space"}),
}


def build_prompt(shape):
    what, meanings = CONTEXT[shape]
    labels = "\n".join(f"- {label}: {meaning}" for label, meaning in meanings.items())
    keys = ", ".join(json.dumps(label) for label in meanings)
    return (
        f"Write short messages for a test set. The messages are {what}.\n\n"
        f"Write {PER_LABEL} different messages for each of these labels:\n{labels}\n\n"
        "Each message is one to three sentences of natural English, as a real person would write it. "
        "Vary the wording, length and style. A careful reader must be able to tell which label a "
        "message belongs to, and it must not fit any other label.\n\n"
        f"Reply with JSON only, no code fence: an object with the keys {keys}, each mapping to an array "
        f"of {PER_LABEL} strings."
    )


def main():
    if PROSE_PATH.exists():
        raise SystemExit(f"{PROSE_PATH.name} exists; it is never overwritten")
    remote_config = json.loads(Path("config.json").read_text(encoding="utf-8"))["remote"]
    config = {**remote_config, "model": WRITER_MODEL, "max_tokens": 8192}
    api_key = os.environ["OPENROUTER_API_KEY"]
    texts, prompts = {}, {}
    for shape, (*_, values) in READINGS.items():
        prompts[shape] = build_prompt(shape)
        for attempt in range(3):
            result = remote.generate(prompts[shape], config, api_key)
            if not result.success:
                # A provider failure is retried; the prompt never changes.
                print(f"{shape}: attempt {attempt + 1} failed: {result.error}")
                continue
            try:
                reply = fast_path.strict_json(fast_path._unfence(result.text))
            except ValueError:
                continue
            if (isinstance(reply, dict) and set(reply) == set(values)
                    and all(isinstance(v, list) and v and all(isinstance(t, str) and t.strip() for t in v)
                            for v in reply.values())):
                texts[shape] = {label: [t.strip() for t in reply[label]] for label in values}
                break
        else:
            raise SystemExit(f"{shape}: no usable reply")
        print(shape, {label: len(v) for label, v in texts[shape].items()})
    PROSE_PATH.write_text(json.dumps({
        "writer_model": WRITER_MODEL, "per_label": PER_LABEL, "prompts": prompts,
        "texts": texts, "excluded": [], "hand_check": None,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", PROSE_PATH.name)


if __name__ == "__main__":
    main()
