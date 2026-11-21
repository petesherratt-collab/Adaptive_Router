"""Hand-written reading steps for the ceiling arm on ``fast_path_planned_bench_v6.py``.

Each shape's reading is made on every item of its list input (``item_field``),
each item raced as the planning router races judgement steps; the reference
code does the rest. Specifications written from the task descriptions before
the texts existed.
"""

from __future__ import annotations

from fast_path_planned_bench_v6 import READINGS

WHAT = {
    "review_digest": "Decide what the product review in the text is mainly about",
    "incident_log": "Decide the severity of the incident note in the text",
    "expense_lines": "Decide the category of the expense described in the text",
    "survey_comments": "Decide the sentiment of the survey comment in the text",
    "menu_check": "Decide from the dish description in the text which allergen the dish contains",
    "applicant_screen": "Decide from the cover letter in the text which role the applicant is applying for",
    "delivery_feedback": "Decide from the courier's delivery note in the text the outcome of the drop",
    "listing_filter": "Decide from the flat listing blurb in the text what outdoor space the flat has",
}


def _step(shape):
    list_input, field, label, values = READINGS[shape]
    labels = ", ".join(f"'{v}'" for v in values[:-1]) + f" or '{values[-1]}'"
    return {"field": list_input, "item_field": field, "label": label,
            "signature": "def solve(text: str) -> str:",
            "spec": f"{WHAT[shape]}, as exactly one of {labels}."}


READING = {shape: _step(shape) for shape in READINGS}
