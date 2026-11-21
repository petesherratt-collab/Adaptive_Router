"""Unseen jobs for the write-once test (planned jobs V4).

Eight new job shapes, none used before, written for the prospective test of
the write-once arm. As in V3: varied inputs (text lines, JSON arrays of
objects and numbers, a JSON object of lists, dates and clock times), one prose
field per shape whose reading is new (guest request, parcel issue, effort,
occupancy, passenger request, weather, event type, occasion), and gold by
construction from a reference function qualified by hand-worked tests.

The prose is not in this file. It is written by a model outside the race
roster into ``fast_path_planned_bench_v4_prose.json`` only after the
code-only rules (``fast_path_code_only_v2.py``) were written from the
descriptions below and their hash recorded.

Run ``python fast_path_planned_bench_v4.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import json
from pathlib import Path
import random

from fast_path_planned_bench_v3 import (
    _cents, _first_best, _lines, _minutes, _money, _round_half_up, _rows, load_prose as _load,
)

STREAM_SEED = 20261118
STREAM_LENGTH = 30
OUTPUT = "result"
PROSE_PATH = Path(__file__).resolve().parent / "fast_path_planned_bench_v4_prose.json"

READINGS = {
    "hotel_stays": ("guest_message", "request", ["late_checkout", "extra_bed", "airport_transfer", "none"]),
    "parcel_lockers": ("customer_note", "issue", ["damaged", "missing", "delayed", "wrong_item"]),
    "exam_marks": ("teacher_comment", "effort", ["high", "average", "low"]),
    "energy_meter": ("household_note", "occupancy", ["single", "couple", "family"]),
    "flight_delays": ("passenger_message", "request", ["rebook", "refund", "compensation", "information"]),
    "bike_rentals": ("rider_note", "weather", ["sunny", "rainy", "windy", "snowy"]),
    "volunteer_rota": ("coordinator_note", "event", ["fundraiser", "cleanup", "food_bank", "tutoring"]),
    "wine_orders": ("note", "occasion", ["wedding", "birthday", "corporate", "none"]),
}

SURCHARGE = {"late_checkout": 3000, "extra_bed": 4500, "airport_transfer": 6000, "none": 0}
LOCKER_ACTION = {"damaged": "claim", "missing": "investigate", "wrong_item": "investigate",
                 "delayed": "apologise"}
ALLOWANCE = {"single": 80, "couple": 120, "family": 180}  # tenths of a kWh per day
WEATHER_DISCOUNT = {"sunny": 0, "windy": 0, "rainy": 20, "snowy": 50}
MINIMUM = {"fundraiser": 4, "cleanup": 6, "food_bank": 3, "tutoring": 2}
OCCASION_DISCOUNT = {"wedding": 15, "corporate": 10, "birthday": 5, "none": 0}

GUESTS = ["Abara", "Brandt", "Costa", "Dubois", "Eriksen", "Fujita", "Garcia", "Haddad", "Ivanova"]
LOCKERS = [f"L{n:02d}" for n in range(1, 25)]
STUDENTS = ["Aiko", "Bea", "Cyril", "Dana", "Ezra", "Fern", "Gus", "Hana", "Ines", "Jude", "Kemal", "Lior"]
CARRIERS = ["AX", "BQ", "CY", "DZ"]
BIKES = [f"B{n:02d}" for n in range(1, 31)]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
VOLUNTEERS = ["Ari", "Bo", "Cleo", "Dov", "Esme", "Femi", "Gia", "Hal", "Isa", "Jem"]
CUSTOMERS = ["Arden Ltd", "Bloom Cafe", "Carver", "Dale & Co", "Elm House", "Fenwick", "Grove Inn"]


def load_prose(path=PROSE_PATH):
    return _load(path)


# ---- references --------------------------------------------------------

def ref_hotel(inputs, labels):
    rows = _rows(inputs["stays"])
    nights = [int(n) for _, _, n, _ in rows]
    revenue = sum(int(n) * _cents(rate) for _, _, n, rate in rows) + SURCHARGE[labels["request"]]
    longest = _first_best(rows, key=lambda r: int(r[2]))
    return (f"{labels['request']} | {len(rows)} stays | {sum(nights)} nights | revenue {_money(revenue)} EUR"
            f" | longest {longest[0] if longest else 'none'}")


def ref_lockers(inputs, labels):
    deposits = inputs["deposits"]
    uncollected = sum(d["out"] is None for d in deposits)
    waits = [_minutes(d["out"]) - _minutes(d["in"]) for d in deposits if d["out"] is not None]
    counts = {size: sum(d["size"] == size for d in deposits) for size in "SML"}
    busiest = max("SML", key=lambda size: (counts[size], -"SML".index(size)))
    return (f"{LOCKER_ACTION[labels['issue']]} ({labels['issue']}) | {uncollected} uncollected | longest wait "
            f"{max(waits) if waits else 0} min | busiest size {busiest}")


def ref_exam(inputs, labels):
    grades = {"A": 0, "B": 0, "C": 0, "F": 0}
    averages = []
    for line in _lines(inputs["marks"]):
        name, rest = line.split(":")
        marks = [int(x) for x in rest.split(",")]
        average = _round_half_up(sum(marks), 3)
        averages.append((name.strip(), average))
        grade = "A" if average >= 70 else "B" if average >= 60 else "C" if average >= 50 else "F"
        grades[grade] += 1
    top = _first_best(averages, key=lambda a: a[1])
    text = (f"A {grades['A']}, B {grades['B']}, C {grades['C']}, F {grades['F']} | top "
            f"{top[0] if top else 'none'} | effort {labels['effort']}")
    return text + (" | meeting" if labels["effort"] == "low" and grades["F"] else "")


def ref_energy(inputs, labels):
    tenths = [round(x * 10) for x in inputs["readings"]]
    daily = [b - a for a, b in zip(tenths, tenths[1:])]
    total = tenths[-1] - tenths[0]
    peak = 1 + daily.index(max(daily))
    over = sum(d > ALLOWANCE[labels["occupancy"]] for d in daily)
    bill = _round_half_up(total * inputs["day_rate"], 10)  # cents
    return (f"{labels['occupancy']}: {total // 10}.{total % 10} kWh over {len(daily)} days, peak day {peak}, "
            f"{over} days over allowance, bill {_money(bill)} EUR")


def ref_flights(inputs, labels):
    flights = inputs["flights"]
    delays = [(f["flight"], _minutes(f["actual"]) - _minutes(f["sched"])) for f in flights]
    late = [m for _, m in delays if m > 15]
    average = _round_half_up(sum(late), len(late)) if late else 0
    worst = _first_best(delays, key=lambda d: d[1])
    return (f"{labels['request']} | {len(late)} of {len(flights)} delayed | average {average} min | worst "
            f"{worst[0]} ({worst[1]:+d} min)")


def ref_bikes(inputs, labels):
    rows = _rows(inputs["rentals"])
    charge, km, longest = 0, 0, None
    for bike, start, end, distance in rows:
        minutes = _minutes(end) - _minutes(start)
        charge += 150 * -(-minutes // 30)
        km += round(float(distance) * 10)
        if longest is None or minutes > longest[1]:
            longest = (bike, minutes)
    charge -= _round_half_up(charge * WEATHER_DISCOUNT[labels["weather"]], 100)
    return (f"{labels['weather']}: {len(rows)} rentals, {km // 10}.{km % 10} km, charge {_money(charge)} EUR, "
            f"longest {longest[0] if longest else 'none'}")


def ref_rota(inputs, labels):
    rota = inputs["rota"]
    minimum = MINIMUM[labels["event"]]
    short = [day for day, names in rota.items() if len(set(names)) < minimum]
    days_by_person = {}
    for names in rota.values():
        for name in set(names):
            days_by_person[name] = days_by_person.get(name, 0) + 1
    busiest = sorted(days_by_person, key=lambda n: (-days_by_person[n], n))[0] if days_by_person else "none"
    return (f"{labels['event']}: {len(days_by_person)} volunteers, short on "
            f"{', '.join(short) if short else 'none'}, busiest {busiest}")


def ref_wine(inputs, labels):
    rows = _rows(inputs["orders"])
    total, discounted = 0, 0
    percent = OCCASION_DISCOUNT[labels["occasion"]]
    for _, bottles, price in rows:
        cents = int(bottles) * _cents(price)
        if int(bottles) >= 12 and percent:
            cents -= _round_half_up(cents * percent, 100)
            discounted += 1
        total += cents
    return (f"{labels['occasion']} | {len(rows)} orders | {sum(int(b) for _, b, _ in rows)} bottles | total "
            f"{_money(total)} EUR | {discounted} discounted")


# ---- generators --------------------------------------------------------

def _prose(r, prose, shape):
    field, _, values = READINGS[shape]
    label = r.choice(values)
    return field, label, r.choice(prose[shape][label])


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def gen_hotel(r, prose):
    field, label, text = _prose(r, prose, "hotel_stays")
    lines = [f"{g} | 2026-12-{r.randint(1, 28):02d} | {r.randint(1, 9)} | "
             f"{r.randint(60, 320)}.{r.choice([0, 50, 90, 95]):02d}"
             for g in r.sample(GUESTS, r.randint(4, 9))]
    return {"stays": "\n".join(lines), field: text}, {"request": label}


def gen_lockers(r, prose):
    field, label, text = _prose(r, prose, "parcel_lockers")
    deposits = []
    for locker in r.sample(LOCKERS, r.randint(6, 14)):
        start = r.randint(7 * 60, 15 * 60)
        out = None if r.random() < 0.3 else _clock(start + r.randint(5, 480))
        deposits.append({"locker": locker, "size": r.choice("SSMML"), "in": _clock(start), "out": out})
    return {"deposits": deposits, field: text}, {"issue": label}


def gen_exam(r, prose):
    field, label, text = _prose(r, prose, "exam_marks")
    lines = [f"{s}: {r.randint(25, 98)}, {r.randint(25, 98)}, {r.randint(25, 98)}"
             for s in r.sample(STUDENTS, r.randint(5, 11))]
    return {"marks": "\n".join(lines), field: text}, {"effort": label}


def gen_energy(r, prose):
    field, label, text = _prose(r, prose, "energy_meter")
    value = r.randint(10000, 90000)
    readings = [value / 10]
    for _ in range(r.randint(6, 13)):
        value += r.randint(40, 260)
        readings.append(value / 10)
    return {"readings": readings, "day_rate": r.randint(18, 41), field: text}, {"occupancy": label}


def gen_flights(r, prose):
    field, label, text = _prose(r, prose, "flight_delays")
    flights = []
    for _ in range(r.randint(5, 12)):
        sched = r.randint(6 * 60, 20 * 60) // 5 * 5
        delay = r.choice([r.randint(-10, 15), r.randint(-10, 15), r.randint(16, 180)])
        flights.append({"flight": f"{r.choice(CARRIERS)}{r.randint(100, 999)}", "sched": _clock(sched),
                        "actual": _clock(sched + delay)})
    return {"flights": flights, field: text}, {"request": label}


def gen_bikes(r, prose):
    field, label, text = _prose(r, prose, "bike_rentals")
    lines = []
    for bike in r.sample(BIKES, r.randint(6, 14)):
        start = r.randint(7 * 60, 19 * 60)
        lines.append(f"{bike} | {_clock(start)} | {_clock(start + r.randint(5, 200))} | "
                     f"{r.randint(5, 400) / 10:.1f}")
    return {"rentals": "\n".join(lines), field: text}, {"weather": label}


def gen_rota(r, prose):
    field, label, text = _prose(r, prose, "volunteer_rota")
    rota = {day: r.sample(VOLUNTEERS, r.randint(1, 7)) for day in DAYS[: r.randint(4, 7)]}
    return {"rota": rota, field: text}, {"event": label}


def gen_wine(r, prose):
    field, label, text = _prose(r, prose, "wine_orders")
    lines = [f"{c} | {r.choice([r.randint(1, 11), r.randint(12, 60)])} | "
             f"{r.randint(6, 45)}.{r.choice([0, 50, 95, 99]):02d}" for c in r.sample(CUSTOMERS, r.randint(3, 7))]
    return {"orders": "\n".join(lines), field: text}, {"occasion": label}


SHAPES = [
    {"name": "hotel_stays", "reference": ref_hotel, "gen": gen_hotel, "description": (
        "Summarise a hotel's stays for a guest's message. Each line of the stays input has the form "
        "'Guest | YYYY-MM-DD | nights | rate', with the rate per night in euros with two decimals. Decide "
        "what the guest_message asks for, as exactly one of 'late_checkout', 'extra_bed', "
        "'airport_transfer' or 'none'; the surcharges for those are 30.00, 45.00, 60.00 and 0.00 euros. "
        "The revenue is the sum over all stays of nights times rate, plus the surcharge. The longest stay "
        "is the guest with the most nights, the first listed on a tie, or 'none'. Return the text "
        "'<request> | <n> stays | <total nights> nights | revenue <revenue> EUR | longest <guest>', with "
        "the revenue written with exactly two decimals.")},
    {"name": "parcel_lockers", "reference": ref_lockers, "gen": gen_lockers, "description": (
        "Summarise a day of parcel locker deposits for a customer's note. The deposits input is a JSON "
        "array of objects with keys 'locker', 'size' ('S', 'M' or 'L'), 'in' (the time deposited, 'HH:MM') "
        "and 'out' (the time collected, 'HH:MM', or null if not collected), all on one day. Decide which "
        "issue the customer_note reports, as exactly one of 'damaged', 'missing', 'delayed' or "
        "'wrong_item'. The action is 'claim' for damaged, 'investigate' for missing or wrong_item, and "
        "'apologise' for delayed. A wait is the minutes from in to out of a collected parcel; the longest "
        "wait is the largest, or 0 if none was collected. The busiest size is the size with the most "
        "deposits, S before M before L on a tie. Return the text '<action> (<issue>) | <u> uncollected | "
        "longest wait <m> min | busiest size <size>', where u is the number not collected.")},
    {"name": "exam_marks", "reference": ref_exam, "gen": gen_exam, "description": (
        "Summarise exam results for a teacher's comment. Each line of the marks input has the form "
        "'Name: p1, p2, p3', three paper marks from 0 to 100. Decide from the teacher_comment the class's "
        "effort, as exactly one of 'high', 'average' or 'low'. A student's average is the mean of the "
        "three marks rounded to a whole number with halves rounded up. The grade is A for an average of 70 "
        "or more, B for 60 or more, C for 50 or more, and F otherwise. The top student has the highest "
        "average, the first listed on a tie. Return the text 'A <a>, B <b>, C <c>, F <f> | top <name> | "
        "effort <effort>', where a, b, c and f count the grades, followed by ' | meeting' if the effort is "
        "low and at least one student has F.")},
    {"name": "energy_meter", "reference": ref_energy, "gen": gen_energy, "description": (
        "Summarise an electricity meter for a household. The readings input is a JSON array of meter "
        "readings in kWh with one decimal, one at the end of each day, in order and never decreasing; the "
        "day_rate input is the price in cents per kWh. Decide from the household_note how many live in the "
        "home, as exactly one of 'single', 'couple' or 'family'; their daily allowances are 8.0, 12.0 and "
        "18.0 kWh. A day's use is a reading minus the one before it, so there is one day fewer than "
        "readings. The total is the last reading minus the first, written with one decimal. The peak day "
        "is the 1-based number of the day with the largest use, the first on a tie. A day is over "
        "allowance when its use is greater than the allowance. The bill is the total times the day_rate, "
        "in euros rounded to the nearest cent with halves rounded up. Return the text '<occupancy>: "
        "<total> kWh over <d> days, peak day <k>, <o> days over allowance, bill <bill> EUR', with the bill "
        "written with exactly two decimals.")},
    {"name": "flight_delays", "reference": ref_flights, "gen": gen_flights, "description": (
        "Summarise a day's flights for a passenger's message. The flights input is a JSON array of objects "
        "with keys 'flight', 'sched' and 'actual', times 'HH:MM' on the same day. Classify what the "
        "passenger_message asks for, as exactly one of 'rebook', 'refund', 'compensation' or "
        "'information'. A flight's delay is the minutes from sched to actual, negative if early. A flight "
        "is delayed when its delay is more than 15 minutes. The average is the mean delay of the delayed "
        "flights rounded to a whole number of minutes with halves rounded up, or 0 if none is delayed. The "
        "worst flight has the largest delay, the first listed on a tie. Return the text '<request> | <d> of "
        "<n> delayed | average <a> min | worst <flight> (<delay> min)', where the delay carries a sign, "
        "such as +45 or -3 or +0.")},
    {"name": "bike_rentals", "reference": ref_bikes, "gen": gen_bikes, "description": (
        "Summarise a day of bike rentals for a rider's note. Each line of the rentals input has the form "
        "'bike | HH:MM | HH:MM | km', the start and end times on one day and the distance with one "
        "decimal. Decide from the rider_note what the weather was, as exactly one of 'sunny', 'rainy', "
        "'windy' or 'snowy'; the weather discounts are 0, 20, 0 and 50 percent. A rental costs 1.50 euros "
        "for each started 30 minutes of its length. The charge is the sum of the rentals' costs, less the "
        "discount on that sum rounded to the nearest cent with halves rounded up. The longest rental is "
        "the bike with the most minutes, the first listed on a tie, or 'none'. Return the text "
        "'<weather>: <n> rentals, <km> km, charge <charge> EUR, longest <bike>', with the total distance "
        "written with one decimal and the charge with two.")},
    {"name": "volunteer_rota", "reference": ref_rota, "gen": gen_rota, "description": (
        "Check a volunteer rota. The rota input is a JSON object whose keys are day names in order, each "
        "mapping to a list of volunteer names. Decide from the coordinator_note what the event is, as "
        "exactly one of 'fundraiser', 'cleanup', 'food_bank' or 'tutoring'; the minimum volunteers per day "
        "for those are 4, 6, 3 and 2. A day is short when it has fewer distinct names than the minimum. "
        "Count the distinct volunteers over all days. The busiest volunteer is on the most days, the "
        "alphabetically first on a tie, or 'none'. Return the text '<event>: <v> volunteers, short on "
        "<days>, busiest <name>', where days are the short days in rota order separated by ', ', or 'none'.")},
    {"name": "wine_orders", "reference": ref_wine, "gen": gen_wine, "description": (
        "Total a wine merchant's orders for a note. Each line of the orders input has the form "
        "'Customer | bottles | price', with the price per bottle in euros with two decimals. Decide from "
        "the note what the occasion is, as exactly one of 'wedding', 'birthday', 'corporate' or 'none'; "
        "the discounts for those are 15, 5, 10 and 0 percent. An order's value is bottles times price. An "
        "order of 12 or more bottles is discounted when the discount is above zero: its value is reduced "
        "by the discount, rounded to the nearest cent with halves rounded up. The total is the sum of the "
        "orders' values after discounts. Return the text '<occasion> | <n> orders | <b> bottles | total "
        "<total> EUR | <k> discounted', with the total written with exactly two decimals and k the number "
        "of discounted orders.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT
    _shape["reading"] = READINGS[_shape["name"]]

TESTS = {
    "hotel_stays": [
        ({"stays": "Abara | 2026-12-01 | 3 | 100.00\nBrandt | 2026-12-02 | 5 | 80.50\nCosta | 2026-12-03 | 5 | 90.00"},
         {"request": "extra_bed"}, "extra_bed | 3 stays | 13 nights | revenue 1197.50 EUR | longest Brandt"),
        ({"stays": "Dubois | 2026-12-04 | 1 | 60.95"}, {"request": "none"},
         "none | 1 stays | 1 nights | revenue 60.95 EUR | longest Dubois"),
    ],
    "parcel_lockers": [
        ({"deposits": [{"locker": "L01", "size": "M", "in": "08:00", "out": "09:15"},
                       {"locker": "L02", "size": "S", "in": "08:30", "out": None},
                       {"locker": "L03", "size": "M", "in": "10:00", "out": "14:05"},
                       {"locker": "L04", "size": "S", "in": "11:00", "out": "11:20"}]},
         {"issue": "wrong_item"}, "investigate (wrong_item) | 1 uncollected | longest wait 245 min | busiest size S"),
        ({"deposits": [{"locker": "L09", "size": "L", "in": "07:00", "out": None}]}, {"issue": "delayed"},
         "apologise (delayed) | 1 uncollected | longest wait 0 min | busiest size L"),
    ],
    "exam_marks": [
        ({"marks": "Aiko: 70, 71, 69\nBea: 40, 45, 50\nCyril: 60, 61, 60\nDana: 90, 50, 50"},
         {"effort": "low"}, "A 1, B 2, C 0, F 1 | top Aiko | effort low | meeting"),
        ({"marks": "Ezra: 49, 50, 50\nFern: 50, 50, 49"}, {"effort": "high"},
         "A 0, B 0, C 2, F 0 | top Ezra | effort high"),
        ({"marks": "Gus: 30, 30, 31"}, {"effort": "average"}, "A 0, B 0, C 0, F 1 | top Gus | effort average"),
    ],
    "energy_meter": [
        ({"readings": [100.0, 110.5, 118.0, 130.0], "day_rate": 25}, {"occupancy": "single"},
         "single: 30.0 kWh over 3 days, peak day 3, 2 days over allowance, bill 7.50 EUR"),
        ({"readings": [5.5, 17.5, 29.5], "day_rate": 33}, {"occupancy": "couple"},
         "couple: 24.0 kWh over 2 days, peak day 1, 0 days over allowance, bill 7.92 EUR"),
        ({"readings": [0.0, 0.3], "day_rate": 25}, {"occupancy": "family"},
         "family: 0.3 kWh over 1 days, peak day 1, 0 days over allowance, bill 0.08 EUR"),
    ],
    "flight_delays": [
        ({"flights": [{"flight": "AX101", "sched": "08:00", "actual": "08:45"},
                      {"flight": "BQ202", "sched": "09:00", "actual": "08:57"},
                      {"flight": "CY303", "sched": "10:00", "actual": "10:16"}]},
         {"request": "refund"}, "refund | 2 of 3 delayed | average 31 min | worst AX101 (+45 min)"),
        ({"flights": [{"flight": "DZ404", "sched": "12:00", "actual": "11:57"},
                      {"flight": "AX505", "sched": "13:00", "actual": "12:57"}]},
         {"request": "information"}, "information | 0 of 2 delayed | average 0 min | worst DZ404 (-3 min)"),
        ({"flights": [{"flight": "BQ606", "sched": "06:00", "actual": "06:15"}]}, {"request": "rebook"},
         "rebook | 0 of 1 delayed | average 0 min | worst BQ606 (+15 min)"),
    ],
    "bike_rentals": [
        ({"rentals": "B01 | 09:00 | 09:30 | 5.0\nB02 | 10:00 | 10:31 | 7.5\nB03 | 11:00 | 12:01 | 12.3"},
         {"weather": "rainy"}, "rainy: 3 rentals, 24.8 km, charge 7.20 EUR, longest B03"),
        ({"rentals": "B04 | 08:00 | 08:05 | 0.5"}, {"weather": "snowy"},
         "snowy: 1 rentals, 0.5 km, charge 0.75 EUR, longest B04"),
        ({"rentals": "B05 | 08:00 | 08:40 | 3.0\nB06 | 09:00 | 09:40 | 4.1"}, {"weather": "sunny"},
         "sunny: 2 rentals, 7.1 km, charge 6.00 EUR, longest B05"),
    ],
    "volunteer_rota": [
        ({"rota": {"Mon": ["Ari", "Bo", "Cleo"], "Tue": ["Ari"], "Wed": ["Bo", "Ari", "Dov", "Esme"]}},
         {"event": "food_bank"}, "food_bank: 5 volunteers, short on Tue, busiest Ari"),
        ({"rota": {"Mon": ["Bo", "Cleo"], "Tue": ["Cleo", "Bo"]}}, {"event": "tutoring"},
         "tutoring: 2 volunteers, short on none, busiest Bo"),
        ({"rota": {"Sat": ["Gia"], "Sun": ["Hal", "Hal"]}}, {"event": "cleanup"},
         "cleanup: 2 volunteers, short on Sat, Sun, busiest Gia"),
    ],
    "wine_orders": [
        ({"orders": "Arden Ltd | 12 | 10.00\nBloom Cafe | 6 | 9.95\nCarver | 24 | 7.99"},
         {"occasion": "wedding"}, "wedding | 3 orders | 42 bottles | total 324.70 EUR | 2 discounted"),
        ({"orders": "Fenwick | 12 | 10.05"}, {"occasion": "none"},
         "none | 1 orders | 12 bottles | total 120.60 EUR | 0 discounted"),
        ({"orders": "Grove Inn | 13 | 0.95"}, {"occasion": "birthday"},
         "birthday | 1 orders | 13 bottles | total 11.73 EUR | 1 discounted"),
    ],
}


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH, prose=None):
    prose = prose if prose is not None else load_prose()
    rng = random.Random(f"{seed}:{shape['name']}")
    seen, out = set(), []
    for _ in range(length * 200):
        inputs, labels = shape["gen"](rng, prose)
        key = json.dumps(inputs, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append((inputs, labels))
            if len(out) == length:
                return out
    raise ValueError(f"{shape['name']}: generator cannot supply {length} distinct inputs")


def gold(shape, instances):
    return [{OUTPUT: shape["reference"](inputs, labels)} for inputs, labels in instances]


def placeholder_prose():
    return {shape: {label: [f"placeholder {label}"] for label in values}
            for shape, (_, _, values) in READINGS.items()}


def self_verify(prose=None):
    import fast_path_jobs_bench_v1
    import fast_path_jobs_bench_v2_large
    import fast_path_planned_bench_v2
    import fast_path_planned_bench_v3

    earlier = {s["name"] for module in (fast_path_jobs_bench_v1, fast_path_jobs_bench_v2_large,
                                        fast_path_planned_bench_v2, fast_path_planned_bench_v3)
               for s in module.SHAPES}
    names = [s["name"] for s in SHAPES]
    assert len(names) == len(set(names)) and not set(names) & earlier, "shape names must be new"
    assert set(names) == set(READINGS)
    if prose is None:
        prose = load_prose() if PROSE_PATH.exists() else placeholder_prose()
    for shape in SHAPES:
        for inputs, labels, expected in TESTS[shape["name"]]:
            got = shape["reference"](inputs, labels)
            assert got == expected, f"{shape['name']}: {got!r} != {expected!r}"
        field, _, values = shape["reading"]
        assert field in shape["description"], f"{shape['name']}: reading field not named"
        assert all(f"'{v}'" in shape["description"] for v in values), f"{shape['name']}: label missing"
        assert set(prose[shape["name"]]) == set(values) and all(prose[shape["name"]][v] for v in values)
        instances = stream(shape, prose=prose)
        assert [i for i, _ in instances] == [i for i, _ in stream(shape, prose=prose)], "not reproducible"
        for inputs, _ in instances:
            for name in inputs:
                assert name in shape["description"], f"{shape['name']}: input {name} not named"
        gold(shape, instances)
    print(f"self_verify OK: {len(SHAPES)} job shapes, {STREAM_LENGTH} jobs each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_planned_bench_v4.py sha256:", bench_sha256())
