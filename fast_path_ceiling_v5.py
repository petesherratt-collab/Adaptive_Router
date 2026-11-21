"""Hand-written reading steps for the ceiling arm on ``fast_path_planned_bench_v5.py``.

As the earlier ceiling modules: reference code for the mechanics, the reading
raced. Specifications written from the task descriptions before the texts
existed.
"""

from __future__ import annotations

from fast_path_ceiling_v4 import _step

READING = {
    "car_park": _step("driver_note", "permit", "Decide from the driver's note in the text which permit the driver holds",
                      ["resident", "visitor", "staff"]),
    "gym_classes": _step("member_note", "goal", "Decide from the gym member's note in the text the member's goal",
                         ["strength", "cardio", "flexibility"]),
    "shared_bills": _step("note", "split", "Decide from the housemate's note in the text how the bills are split",
                          ["equal", "weighted"]),
    "plant_watering": _step("gardener_note", "season", "Decide from the gardener's note in the text which season it is",
                            ["summer", "winter"]),
    "train_fares": _step("journey_note", "time", "Decide from the journey note in the text when the journey is",
                         ["peak", "offpeak", "weekend"]),
    "reading_challenge": _step("organiser_note", "genre", "Decide from the organiser's note in the text the challenge's genre",
                               ["mystery", "romance", "history", "science"]),
    "lab_ph": _step("technician_note", "sample", "Decide from the technician's note in the text what was sampled",
                    ["water", "soil", "blood"]),
    "donation_match": _step("appeal_note", "cause", "Decide from the appeal note in the text which cause the appeal is for",
                            ["disaster", "education", "health", "animals"]),
}
