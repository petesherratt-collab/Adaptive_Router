"""Hand-written reading steps for the ceiling arm on ``fast_path_planned_bench_v3.py``.

As in ``fast_path_ceiling_v1.py``: the mechanical work is the benchmark's
reference function, and only the reading step goes to models, raced exactly as
the planning router races its judgement steps. The step specifications were
written from the task descriptions, before the texts existed, and use their
words.
"""

from __future__ import annotations

TEXT = "def solve(text: str) -> str:"

READING = {
    "ticket_queue": {
        "field": "email", "label": "urgency", "signature": TEXT,
        "spec": "Decide whether the support email in the text is 'urgent' or 'routine'. Return exactly "
                "one of 'urgent' or 'routine'.",
    },
    "room_bookings": {
        "field": "request", "label": "department", "signature": TEXT,
        "spec": "Decide which department the person who wrote the meeting room request in the text works "
                "in, as exactly one of 'sales', 'engineering', 'finance' or 'legal'.",
    },
    "recipe_scaling": {
        "field": "guest_note", "label": "diet", "signature": TEXT,
        "spec": "Decide from the guest's note in the text what the guest eats, as exactly one of "
                "'vegan', 'vegetarian' or 'any'.",
    },
    "fleet_fuel": {
        "field": "report", "label": "issue", "signature": TEXT,
        "spec": "Decide which problem the driver's report in the text describes, as exactly one of "
                "'tyres', 'brakes', 'engine' or 'none'.",
    },
    "library_loans": {
        "field": "message", "label": "request", "signature": TEXT,
        "spec": "Classify what the library member's message in the text asks for, as exactly one of "
                "'renew', 'return', 'reserve' or 'complain'.",
    },
    "sensor_alerts": {
        "field": "note", "label": "site", "signature": TEXT,
        "spec": "Decide which site the technician's note in the text is about, as exactly one of "
                "'north', 'south', 'east' or 'west'.",
    },
    "invoice_vat": {
        "field": "note", "label": "country", "signature": TEXT,
        "spec": "Decide from the note in the text which country the order is delivered to, as exactly "
                "one of 'UK', 'Ireland', 'Spain' or 'Italy'.",
    },
    "event_rsvps": {
        "field": "invite_note", "label": "formality", "signature": TEXT,
        "spec": "Decide whether the invitation note in the text describes a 'formal' or a 'casual' "
                "event. Return exactly one of 'formal' or 'casual'.",
    },
}
