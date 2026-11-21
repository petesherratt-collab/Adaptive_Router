"""Write the prose for ``fast_path_planned_bench_v4.py``. Makes provider calls.

One call per job shape to a model outside the race roster asks for short
English messages for every label of that shape's reading step. The replies are
kept verbatim in ``fast_path_planned_bench_v4_prose.json``, which this script
never overwrites. The hand check against the planted labels is recorded in the
same file's ``excluded`` list afterwards, before any rule or model reads them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fast_path
from fast_path_planned_bench_v4 import PROSE_PATH, READINGS
import remote

WRITER_MODEL = "mistralai/mistral-large-4-0"
PER_LABEL = 12

CONTEXT = {
    "hotel_stays": ("messages from hotel guests to the front desk before or during their stay", {
        "late_checkout": "the guest asks to check out late", "extra_bed": "the guest asks for an extra bed or cot",
        "airport_transfer": "the guest asks for transport to or from the airport",
        "none": "the guest asks for nothing in particular"}),
    "parcel_lockers": ("notes from customers about a parcel sent to a parcel locker", {
        "damaged": "the parcel arrived damaged", "missing": "the parcel was not in the locker",
        "delayed": "the parcel has not arrived when expected", "wrong_item": "the parcel held the wrong item"}),
    "exam_marks": ("comments from a teacher about a class after an exam, describing the class's effort", {
        "high": "the class worked hard", "average": "the class's effort was middling",
        "low": "the class made little effort"}),
    "energy_meter": ("notes from people about their home, sent with a meter reading, from which the number of "
                     "people living there can be told", {
        "single": "one person lives there", "couple": "two adults live there",
        "family": "a family with children lives there"}),
    "flight_delays": ("messages from airline passengers after a disrupted flight", {
        "rebook": "the passenger wants to be put on another flight", "refund": "the passenger wants their money back",
        "compensation": "the passenger claims compensation for the disruption",
        "information": "the passenger asks for information"}),
    "bike_rentals": ("notes from people returning a rental bike, mentioning the weather on their ride", {
        "sunny": "it was sunny", "rainy": "it rained", "windy": "it was windy", "snowy": "it snowed"}),
    "volunteer_rota": ("notes from a volunteer coordinator about the week's event", {
        "fundraiser": "the event raises money", "cleanup": "the event cleans up a public place",
        "food_bank": "the event runs a food bank", "tutoring": "the event tutors children"}),
    "wine_orders": ("notes sent with orders to a wine merchant", {
        "wedding": "the wine is for a wedding", "birthday": "the wine is for a birthday",
        "corporate": "the wine is for a company or business event", "none": "no occasion is given"}),
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
    for shape, (_, _, values) in READINGS.items():
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
