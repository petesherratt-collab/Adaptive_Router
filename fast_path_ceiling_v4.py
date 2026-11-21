"""Hand-written reading steps for the ceiling arm on ``fast_path_planned_bench_v4.py``.

As ``fast_path_ceiling_v3.py``: the mechanical work is the benchmark's
reference function, and only the reading step goes to models. Specifications
written from the task descriptions, before the texts existed.
"""

from __future__ import annotations

TEXT = "def solve(text: str) -> str:"


def _step(field, label, what, values):
    labels = ", ".join(f"'{v}'" for v in values[:-1]) + f" or '{values[-1]}'"
    return {"field": field, "label": label, "signature": TEXT,
            "spec": f"{what}, as exactly one of {labels}."}


READING = {
    "hotel_stays": _step("guest_message", "request", "Decide what the hotel guest's message in the text asks for",
                         ["late_checkout", "extra_bed", "airport_transfer", "none"]),
    "parcel_lockers": _step("customer_note", "issue", "Decide which issue the customer's note in the text reports",
                            ["damaged", "missing", "delayed", "wrong_item"]),
    "exam_marks": _step("teacher_comment", "effort", "Decide from the teacher's comment in the text the class's effort",
                        ["high", "average", "low"]),
    "energy_meter": _step("household_note", "occupancy", "Decide from the household's note in the text how many live in the home",
                          ["single", "couple", "family"]),
    "flight_delays": _step("passenger_message", "request", "Classify what the passenger's message in the text asks for",
                           ["rebook", "refund", "compensation", "information"]),
    "bike_rentals": _step("rider_note", "weather", "Decide from the rider's note in the text what the weather was",
                          ["sunny", "rainy", "windy", "snowy"]),
    "volunteer_rota": _step("coordinator_note", "event", "Decide from the coordinator's note in the text what the event is",
                            ["fundraiser", "cleanup", "food_bank", "tutoring"]),
    "wine_orders": _step("note", "occasion", "Decide from the note in the text what the occasion is",
                         ["wedding", "birthday", "corporate", "none"]),
}
