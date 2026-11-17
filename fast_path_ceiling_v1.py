"""Hand-written plans for the ceiling arm on ``fast_path_planned_bench_v2.py``.

The ceiling arm stands for a programmer having already written the job: the
mechanical work is the benchmark's reference function, and only the reading
step goes to models. Because the reference function is the code that defines
the correct answers, the ceiling's mechanical work is correct by definition;
its accuracy measures its reading step alone.

Each entry names the one prose input a shape has, the label the reference
function needs, and the judgement step that reads it. The step specifications
were written from the task descriptions and use their words.
"""

from __future__ import annotations

TEXT = "def solve(text: str) -> str:"

READING = {
    "expense_claims": {
        "field": "cover_note", "label": "language", "signature": TEXT,
        "spec": "Identify the language the text is written in as exactly one of 'english', 'french', "
                "'spanish' or 'german'.",
    },
    "shipment_tracking": {
        "field": "message", "label": "intent", "signature": TEXT,
        "spec": "Classify what the customer wants in the text as exactly one of 'refund', 'cancel', "
                "'change_address' or 'order_status'.",
    },
    "survey_scores": {
        "field": "comment", "label": "tone", "signature": TEXT,
        "spec": "Classify the tone of the text as exactly one of 'positive', 'negative' or 'neutral'.",
    },
    "timesheet": {
        "field": "manager_note", "label": "topic", "signature": TEXT,
        "spec": "Classify what the text is about as exactly one of 'billing', 'technical', 'account' or "
                "'shipping'.",
    },
    "bank_statement": {
        "field": "dispute_note", "label": "tone", "signature": TEXT,
        "spec": "Classify the tone of the text as exactly one of 'positive', 'negative' or 'neutral'.",
    },
    "playlist": {
        "field": "note", "label": "language", "signature": TEXT,
        "spec": "Identify the language the text is written in as exactly one of 'english', 'french', "
                "'spanish' or 'german'.",
    },
    "pick_list": {
        "field": "focus_item", "label": "kind", "signature": "def solve(word: str) -> str:",
        "spec": "Classify the thing named by the word as exactly one of 'animal', 'tool' or 'food'.",
    },
}
