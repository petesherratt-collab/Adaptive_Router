"""Write the prose for ``fast_path_planned_bench_v5.py``. Makes provider calls.

One call per job shape to a model outside the race roster asks for short
English messages for every label of that shape's reading step. The replies are
kept verbatim in ``fast_path_planned_bench_v5_prose.json``, which this script
never overwrites. The hand check against the planted labels is recorded in the
same file's ``excluded`` list afterwards, before any rule or model reads them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fast_path
from fast_path_planned_bench_v5 import PROSE_PATH, READINGS
import remote

WRITER_MODEL = "mistralai/mistral-large-4-0"
PER_LABEL = 12

CONTEXT = {
    "car_park": ("notes left by drivers at a car park, from which the driver's permit can be told", {
        "resident": "the driver lives locally and holds a resident permit",
        "visitor": "the driver is visiting and holds no permit",
        "staff": "the driver works at the site and holds a staff permit"}),
    "gym_classes": ("notes from gym members about what they want from their training", {
        "strength": "the member wants to build strength or muscle", "cardio": "the member wants fitness and stamina",
        "flexibility": "the member wants flexibility and mobility"}),
    "shared_bills": ("notes from a housemate in a shared house about how to split the bills", {
        "equal": "everyone pays the same share",
        "weighted": "shares are weighted, for example by room size or use"}),
    "plant_watering": ("notes from a gardener about the weather and the season", {
        "summer": "it is summer", "winter": "it is winter"}),
    "train_fares": ("notes about when a group will travel by train", {
        "peak": "travelling at a weekday peak time", "offpeak": "travelling at a weekday off-peak time",
        "weekend": "travelling at the weekend"}),
    "reading_challenge": ("notes from a book club organiser announcing this month's reading challenge", {
        "mystery": "the challenge is mystery or crime books", "romance": "the challenge is romance books",
        "history": "the challenge is history books", "science": "the challenge is science books"}),
    "lab_ph": ("notes from a laboratory technician about a batch of samples", {
        "water": "the samples are water", "soil": "the samples are soil", "blood": "the samples are blood"}),
    "donation_match": ("appeal notes from a charity drive", {
        "disaster": "the appeal is for disaster relief", "education": "the appeal is for education",
        "health": "the appeal is for health care", "animals": "the appeal is for animal welfare"}),
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
