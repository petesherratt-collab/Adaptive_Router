"""Write the prose for ``fast_path_planned_bench_v3.py``. Makes provider calls.

One call per job shape to a model outside the race roster asks for short
English messages for every label of that shape's reading step. The replies are
kept verbatim in ``fast_path_planned_bench_v3_prose.json``, which this script
never overwrites. The hand check against the planted labels is recorded in the
same file's ``excluded`` list afterwards, before any rule or model reads them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fast_path
from fast_path_planned_bench_v3 import PROSE_PATH, READINGS
import remote

WRITER_MODEL = "mistralai/mistral-large-4-0"
PER_LABEL = 12

CONTEXT = {
    "ticket_queue": ("emails sent to a software company's support desk", {
        "urgent": "the problem needs attention straight away",
        "routine": "the request can wait its turn in the queue"}),
    "room_bookings": ("messages from employees asking to book a meeting room, in which what the meeting "
                      "is for shows which department the writer works in", {
        "sales": "the writer works in sales", "engineering": "the writer works in engineering",
        "finance": "the writer works in finance", "legal": "the writer works in the legal team"}),
    "recipe_scaling": ("notes from dinner guests to the host about what they eat", {
        "vegan": "the guest eats no animal products at all",
        "vegetarian": "the guest eats no meat or fish but does eat dairy",
        "any": "the guest eats everything, meat included"}),
    "fleet_fuel": ("end-of-shift reports from delivery van drivers about their van", {
        "tyres": "a problem with the tyres", "brakes": "a problem with the brakes",
        "engine": "a problem with the engine", "none": "no problem with the van"}),
    "library_loans": ("messages from library members to the library", {
        "renew": "the member wants to renew a loan", "return": "the member wants to return books",
        "reserve": "the member wants to reserve a book", "complain": "the member is making a complaint"}),
    "sensor_alerts": ("notes from technicians about a sensor at one of a company's four sites, called "
                      "north, south, east and west", {
        "north": "the note is about the north site", "south": "the note is about the south site",
        "east": "the note is about the east site", "west": "the note is about the west site"}),
    "invoice_vat": ("notes attached to orders, from which the delivery country can be told", {
        "UK": "delivered to the United Kingdom", "Ireland": "delivered to Ireland",
        "Spain": "delivered to Spain", "Italy": "delivered to Italy"}),
    "event_rsvps": ("notes sent with invitations to an event", {
        "formal": "the event is formal", "casual": "the event is casual"}),
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
        for attempt in range(2):
            result = remote.generate(prompts[shape], config, api_key)
            if not result.success:
                raise SystemExit(f"{shape}: {result.error}")
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
