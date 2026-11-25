"""Write the prose for ``fast_path_planned_bench_v7.py``. Makes provider calls.

One call per job shape to a model outside the race roster asks for short
English messages for every label of that shape's reading step. The replies are
kept verbatim in ``fast_path_planned_bench_v7_prose.json``, which this script
never overwrites. The hand check against the planted labels is recorded in the
same file's ``excluded`` list afterwards, before any rule or model reads them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fast_path
from fast_path_planned_bench_v7 import PROSE_PATH, SHAPES
import remote

WRITER_MODEL = "mistralai/mistral-large-4-0"
PER_LABEL = 12

CONTEXT = {
    "parcel_postage": ("short messages a customer sends to a post office counter about how they want their parcels sent", {
        "standard": "they want the ordinary, cheapest service with no extras",
        "express": "they want the parcels to arrive as fast as possible",
        "tracked": "they want to be able to track the parcels and get proof of delivery, without needing speed"}),
    "room_booking": ("short messages from customers booking a room at a venue, saying what the event is", {
        "meeting": "a business meeting or discussion", "workshop": "a hands-on workshop or training session",
        "party": "a party or celebration"}),
    "tip_split": ("short comments a table leaves about the service they had at a restaurant", {
        "poor": "the service was poor", "good": "the service was good",
        "excellent": "the service was excellent, outstanding"}),
    "library_fines": ("short notes a librarian writes about a borrower when they return books", {
        "child": "the borrower is a child", "adult": "the borrower is an adult of working age",
        "senior": "the borrower is a pensioner or older person"}),
    "ticket_triage": ("customer support tickets, one or two sentences each", {
        "billing": "about a charge, invoice, refund or payment", "bug": "reporting something in the product that is broken or erroring",
        "account": "about logging in, passwords, profile or account settings"}),
    "shopping_receipt": ("short item descriptions as they appear on a supermarket receipt or order", {
        "food": "food or a non-alcoholic drink", "household": "a household item such as cleaning products or toiletries",
        "alcohol": "an alcoholic drink"}),
    "repair_requests": ("short repair requests tenants send to a landlord", {
        "emergency": "an emergency that needs fixing at once (danger, flooding, no heating in winter, gas)",
        "routine": "a real fault that needs fixing soon but is not dangerous",
        "cosmetic": "a cosmetic issue that only affects appearance"}),
    "party_replies": ("short replies to a party invitation", {
        "yes": "they are coming", "maybe": "they are not sure yet whether they can come",
        "no": "they cannot come"}),
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
    # The writer reasons before answering; 8192 tokens ran out on one shape.
    config = {**remote_config, "model": WRITER_MODEL, "max_tokens": 32000, "timeout_seconds": 600}
    api_key = os.environ["OPENROUTER_API_KEY"]
    partial = PROSE_PATH.with_name(PROSE_PATH.name + ".partial")
    texts, prompts = {}, {}
    if partial.exists():
        saved = json.loads(partial.read_text(encoding="utf-8"))
        texts, prompts = saved["texts"], saved["prompts"]
    for shape, values in ((s["name"], s["reading"][2]) for s in SHAPES):
        if shape in texts:
            continue
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
        partial.write_text(json.dumps({"texts": texts, "prompts": prompts}, ensure_ascii=False), encoding="utf-8")
    partial.unlink(missing_ok=True)
    PROSE_PATH.write_text(json.dumps({
        "writer_model": WRITER_MODEL, "per_label": PER_LABEL, "prompts": prompts,
        "texts": texts, "excluded": [], "hand_check": None,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", PROSE_PATH.name)


if __name__ == "__main__":
    main()
