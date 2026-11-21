"""Fresh unseen jobs for write-once V3 (with edge-case probes).

Eight new job shapes, none used before. Several carry rules of the kind that
caught write-once out on V4: rounding at exact halves (half fares, half fees,
matched donations, weighted shares, means), ties and thresholds. As before:
varied inputs, one prose field per shape, gold by construction from reference
functions qualified by hand-worked tests. The prose is written afterwards by a
model outside the race roster into ``fast_path_planned_bench_v5_prose.json``.

Run ``python fast_path_planned_bench_v5.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import json
from pathlib import Path
import random

from fast_path_planned_bench_v3 import (
    _cents, _first_best, _lines, _minutes, _money, _round_half_up, _rows, load_prose as _load,
)

STREAM_SEED = 20261119
STREAM_LENGTH = 30
OUTPUT = "result"
PROSE_PATH = Path(__file__).resolve().parent / "fast_path_planned_bench_v5_prose.json"

READINGS = {
    "car_park": ("driver_note", "permit", ["resident", "visitor", "staff"]),
    "gym_classes": ("member_note", "goal", ["strength", "cardio", "flexibility"]),
    "shared_bills": ("note", "split", ["equal", "weighted"]),
    "plant_watering": ("gardener_note", "season", ["summer", "winter"]),
    "train_fares": ("journey_note", "time", ["peak", "offpeak", "weekend"]),
    "reading_challenge": ("organiser_note", "genre", ["mystery", "romance", "history", "science"]),
    "lab_ph": ("technician_note", "sample", ["water", "soil", "blood"]),
    "donation_match": ("appeal_note", "cause", ["disaster", "education", "health", "animals"]),
}

ZONE_FARE = {"peak": 330, "offpeak": 245, "weekend": 195}
TARGET = {"mystery": 300, "romance": 250, "history": 400, "science": 350}
PH_RANGE = {"water": (650, 850), "soil": (550, 750), "blood": (735, 745)}
MATCHED = {"education", "health"}

PLATES = ["AB12 CDE", "KL09 XYZ", "MN71 PQR", "ST03 UVW", "GH55 JKL", "RT18 BNM", "WX64 QAZ", "YP27 HTD"]
CLASSES = [("Barbell Basics", "strength"), ("Kettlebell Flow", "strength"), ("Power Hour", "strength"),
           ("Spin Sprint", "cardio"), ("Rowing Intervals", "cardio"), ("Step Up", "cardio"),
           ("Gentle Yoga", "flexibility"), ("Stretch Lab", "flexibility"), ("Pilates Core", "flexibility")]
HOUSEMATES = ["Ama", "Ben", "Cas", "Dee", "Eli", "Fay"]
PLANTS = ["basil", "fern", "fig", "ivy", "jade", "mint", "orchid", "palm", "sage", "yucca"]
PASSENGERS = ["Ada", "Bryn", "Cal", "Dot", "Eve", "Finn", "Gwen", "Huw", "Iris", "Jon"]
READERS = ["Anil", "Beth", "Cora", "Dmitri", "Effie", "Gil", "Hira", "Ivo"]
DONORS = ["Ash", "Bea", "Col", "Dina", "Ed", "Flo", "Gus", "Hoa", "Ike", "Jas", "Kit"]


def load_prose(path=PROSE_PATH):
    return _load(path)


# ---- references --------------------------------------------------------

def ref_car_park(inputs, labels):
    rows = _rows(inputs["entries"])
    fees, over, longest = 0, 0, None
    for plate, start, end in rows:
        minutes = _minutes(end) - _minutes(start)
        visitor = 225 * -(-minutes // 60)
        fee = {"visitor": visitor, "resident": _round_half_up(visitor, 2), "staff": 0}[labels["permit"]]
        fees += fee
        over += minutes > 240
        if longest is None or minutes > longest[1]:
            longest = (plate, minutes)
    return (f"{labels['permit']} | {len(rows)} stays | fees {_money(fees)} EUR | {over} over 4h | longest "
            f"{longest[0] if longest else 'none'}")


def ref_gym(inputs, labels):
    classes = inputs["classes"]
    free = [(c["name"], c["capacity"] - c["booked"]) for c in classes
            if c["type"] == labels["goal"] and c["capacity"] > c["booked"]]
    pick = sorted(free, key=lambda f: (-f[1], f[0]))[0][0] if free else "none"
    fill = _round_half_up(100 * sum(c["booked"] for c in classes), sum(c["capacity"] for c in classes))
    full = sum(c["booked"] >= c["capacity"] for c in classes)
    return f"{labels['goal']}: recommend {pick} | fill {fill}% | {full} full classes"


def ref_bills(inputs, labels):
    rows = [(name, _cents(amount)) for name, amount in _rows(inputs["payments"])]
    total = sum(c for _, c in rows)
    weights = inputs["weights"]
    if labels["split"] == "equal":
        shares = {name: _round_half_up(total, len(rows)) for name, _ in rows}
    else:
        weight_sum = sum(weights[name] for name, _ in rows)
        shares = {name: _round_half_up(total * weights[name], weight_sum) for name, _ in rows}
    balances = [(name, paid - shares[name]) for name, paid in rows]
    owed = _first_best(balances, key=lambda b: b[1])
    owing = _first_best(balances, key=lambda b: -b[1])
    return (f"{labels['split']} | total {_money(total)} | most owed {owed[0]} {_money(abs(owed[1]))} | "
            f"most owing {owing[0]} {_money(abs(owing[1]))}")


def _day(date):
    year, month, day = date.split("-")
    assert (year, month) == ("2026", "12"), date
    return int(day)


def ref_plants(inputs, labels):
    today = _day(inputs["today"])
    due = []
    for plant in inputs["plants"]:
        interval = (_round_half_up(plant["every"], 2) if labels["season"] == "summer"
                    else plant["every"] * 2)
        late = today - _day(plant["last"]) - interval
        if late >= 0:
            due.append((plant["name"], late))
    worst = _first_best(due, key=lambda d: d[1])
    return (f"{labels['season']}: {len(due)} of {len(inputs['plants'])} due, most overdue "
            f"{worst[0] if worst else 'none'}")


def ref_fares(inputs, labels):
    fares = []
    for name, age, zones in _rows(inputs["passengers"]):
        adult = ZONE_FARE[labels["time"]] * int(zones)
        age = int(age)
        fare = 0 if age >= 65 else _round_half_up(adult, 2) if age < 16 else adult
        fares.append((name, fare))
    top = _first_best(fares, key=lambda f: f[1])
    return (f"{labels['time']} | {len(fares)} passengers | total {_money(sum(f for _, f in fares))} EUR | "
            f"{sum(f == 0 for _, f in fares)} free | top fare {top[0]}")


def ref_reading(inputs, labels):
    totals = {name: sum(weeks) for name, weeks in inputs["pages"].items()}
    met = sum(t >= TARGET[labels["genre"]] for t in totals.values())
    average = _round_half_up(sum(totals.values()), len(totals))
    top = sorted(totals, key=lambda n: (-totals[n], n))[0]
    return f"{labels['genre']}: {met} of {len(totals)} met target, average {average} pages, top {top}"


def ref_ph(inputs, labels):
    values = [round(x * 100) for x in inputs["readings"]]
    low, high = PH_RANGE[labels["sample"]]
    out = [i + 1 for i, v in enumerate(values) if not low <= v <= high]
    mean = _round_half_up(sum(values), len(values))
    return (f"{labels['sample']}: {len(out)} of {len(values)} out of range, mean {mean // 100}.{mean % 100:02d}, "
            f"first out {out[0] if out else 'none'}")


def ref_donations(inputs, labels):
    rows = [(name, _cents(amount)) for name, amount in _rows(inputs["donations"])]
    match = 0
    if labels["cause"] in MATCHED:
        match = sum(min(_round_half_up(c, 2), 10000) for _, c in rows)
    top = _first_best(rows, key=lambda r: r[1])
    return (f"{labels['cause']} | {len(rows)} donations | raised {_money(sum(c for _, c in rows) + match)} EUR | "
            f"matched {_money(match)} | top donor {top[0]}")


# ---- generators --------------------------------------------------------

def _prose(r, prose, shape):
    field, _, values = READINGS[shape]
    label = r.choice(values)
    return field, label, r.choice(prose[shape][label])


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _amount(r, low, high):
    return f"{r.randint(low, high)}.{r.choice([0, 1, 5, 25, 33, 50, 67, 99]):02d}"


def gen_car_park(r, prose):
    field, label, text = _prose(r, prose, "car_park")
    lines = []
    for plate in r.sample(PLATES, r.randint(3, 8)):
        start = r.randint(6 * 60, 14 * 60)
        lines.append(f"{plate} | {_clock(start)} | {_clock(start + r.choice([r.randint(10, 300), 60, 120, 240, 241]))}")
    return {"entries": "\n".join(lines), field: text}, {"permit": label}


def gen_gym(r, prose):
    field, label, text = _prose(r, prose, "gym_classes")
    classes = []
    for name, kind in r.sample(CLASSES, r.randint(4, 8)):
        capacity = r.choice([8, 10, 12, 15, 20])
        classes.append({"name": name, "type": kind, "capacity": capacity,
                        "booked": r.choice([capacity, capacity - r.randint(1, capacity), r.randint(0, capacity)])})
    return {"classes": classes, field: text}, {"goal": label}


def gen_bills(r, prose):
    field, label, text = _prose(r, prose, "shared_bills")
    people = r.sample(HOUSEMATES, r.randint(2, 6))
    lines = [f"{name} | {_amount(r, 0, 400)}" for name in people]
    weights = {name: r.randint(1, 4) for name in people}
    return {"payments": "\n".join(lines), "weights": weights, field: text}, {"split": label}


def gen_plants(r, prose):
    field, label, text = _prose(r, prose, "plant_watering")
    today = r.randint(15, 31)
    plants = [{"name": p, "last": f"2026-12-{r.randint(1, today):02d}", "every": r.randint(1, 9)}
              for p in r.sample(PLANTS, r.randint(3, 8))]
    return {"plants": plants, "today": f"2026-12-{today:02d}", field: text}, {"season": label}


def gen_fares(r, prose):
    field, label, text = _prose(r, prose, "train_fares")
    lines = [f"{name} | {r.choice([r.randint(4, 15), r.randint(16, 64), r.randint(16, 64), r.randint(65, 90), 15, 16, 65])} | "
             f"{r.randint(1, 6)}" for name in r.sample(PASSENGERS, r.randint(2, 8))]
    return {"passengers": "\n".join(lines), field: text}, {"time": label}


def gen_reading(r, prose):
    field, label, text = _prose(r, prose, "reading_challenge")
    weeks = r.randint(2, 5)
    pages = {name: [r.randint(0, 160) for _ in range(weeks)] for name in r.sample(READERS, r.randint(3, 7))}
    return {"pages": pages, field: text}, {"genre": label}


def gen_ph(r, prose):
    field, label, text = _prose(r, prose, "lab_ph")
    centre = {"water": 750, "soil": 650, "blood": 740}[label] + r.randint(-60, 60)
    readings = [round((centre + r.randint(-120, 120)) / 100, 2) for _ in range(r.randint(5, 14))]
    return {"readings": readings, field: text}, {"sample": label}


def gen_donations(r, prose):
    field, label, text = _prose(r, prose, "donation_match")
    lines = [f"{name} | {_amount(r, 1, 400)}" for name in r.sample(DONORS, r.randint(3, 9))]
    return {"donations": "\n".join(lines), field: text}, {"cause": label}


SHAPES = [
    {"name": "car_park", "reference": ref_car_park, "gen": gen_car_park, "description": (
        "Charge a day of car park stays for a driver's note. Each line of the entries input has the form "
        "'PLATE | HH:MM | HH:MM', the arrival and departure times on one day. Decide from the driver_note "
        "which permit the driver holds, as exactly one of 'resident', 'visitor' or 'staff'. A visitor pays "
        "2.25 euros for each started hour of a stay. A resident pays half the visitor fee for each stay, "
        "rounded to the nearest cent with halves rounded up. Staff pay nothing. Every stay is charged at "
        "the driver's permit. The fees are the sum over all stays. A stay is over 4h when it lasts more "
        "than 240 minutes. The longest stay is the plate with the most minutes, the first listed on a "
        "tie. Return the text '<permit> | <n> stays | fees <fees> EUR | <k> over 4h | longest <plate>', "
        "with the fees written with exactly two decimals.")},
    {"name": "gym_classes", "reference": ref_gym, "gen": gen_gym, "description": (
        "Recommend a gym class for a member's note. The classes input is a JSON array of objects with "
        "keys 'name', 'type' ('strength', 'cardio' or 'flexibility'), 'capacity' and 'booked'. Decide from "
        "the member_note the member's goal, as exactly one of 'strength', 'cardio' or 'flexibility'. A "
        "class's free places are capacity minus booked. The recommendation is the class of the goal's type "
        "with the most free places, the alphabetically first name on a tie, or 'none' if no class of that "
        "type has a free place. The fill is the total booked over all classes divided by the total "
        "capacity, as a whole percentage with halves rounded up. A class is full when booked is at least "
        "capacity. Return the text '<goal>: recommend <name> | fill <fill>% | <f> full classes'.")},
    {"name": "shared_bills", "reference": ref_bills, "gen": gen_bills, "description": (
        "Settle a shared house's bills for a housemate's note. Each line of the payments input has the "
        "form 'Name | amount', what that housemate paid towards the shared bills, in euros with two "
        "decimals; the weights input is a JSON object giving each housemate a whole-number weight. Decide "
        "from the note how the bills are split, as exactly one of 'equal' or 'weighted'. The total is the "
        "sum of all payments. Each housemate's share is the total divided by the number of housemates for "
        "an equal split, or the total times their weight divided by the sum of the weights for a weighted "
        "split, each share rounded to the nearest cent with halves rounded up. A housemate's balance is "
        "what they paid minus their share. The most owed is the housemate with the largest balance, and "
        "the most owing the one with the smallest, the first listed on a tie in each case. Return the text "
        "'<split> | total <total> | most owed <name> <amount> | most owing <name> <amount>', where each "
        "amount is the size of that balance without a sign, all amounts with exactly two decimals.")},
    {"name": "plant_watering", "reference": ref_plants, "gen": gen_plants, "description": (
        "List the plants due for watering for a gardener's note. The plants input is a JSON array of "
        "objects with keys 'name', 'last' (the date last watered, 'YYYY-MM-DD') and 'every' (the usual "
        "interval in days); the today input is today's date; all dates are in December 2026. Decide from "
        "the gardener_note which season it is, as exactly one of 'summer' or 'winter'. In summer a plant's "
        "interval is half its usual interval, rounded to a whole number of days with halves rounded up; in "
        "winter it is double. A plant is due when the days from last to today are at least its interval; "
        "how overdue it is is those days minus the interval. The most overdue plant is the due plant with "
        "the largest such number, the first listed on a tie, or 'none'. Return the text '<season>: <d> of "
        "<n> due, most overdue <name>', where d counts the due plants and n all plants.")},
    {"name": "train_fares", "reference": ref_fares, "gen": gen_fares, "description": (
        "Price a group's train tickets for a journey note. Each line of the passengers input has the form "
        "'Name | age | zones'. Decide from the journey_note when the journey is, as exactly one of 'peak', "
        "'offpeak' or 'weekend'; the fare per zone for those is 3.30, 2.45 and 1.95 euros. An adult fare "
        "is the fare per zone times the zones. A passenger under 16 pays half the adult fare, rounded to "
        "the nearest cent with halves rounded up; a passenger aged 65 or over travels free; everyone else "
        "pays the adult fare. The top fare is the passenger who pays the most, the first listed on a tie. "
        "Return the text '<time> | <n> passengers | total <total> EUR | <f> free | top fare <name>', with "
        "the total written with exactly two decimals and f the number who travel free.")},
    {"name": "reading_challenge", "reference": ref_reading, "gen": gen_reading, "description": (
        "Score a reading challenge for an organiser's note. The pages input is a JSON object mapping each "
        "member's name to a list of the pages they read each week. Decide from the organiser_note the "
        "challenge's genre, as exactly one of 'mystery', 'romance', 'history' or 'science'; the page "
        "targets for those are 300, 250, 400 and 350. A member meets the target when their total pages "
        "are at least the target. The average is the mean of the members' totals, rounded to a whole "
        "number with halves rounded up. The top reader has the largest total, the alphabetically first on "
        "a tie. Return the text '<genre>: <m> of <n> met target, average <average> pages, top <name>'.")},
    {"name": "lab_ph", "reference": ref_ph, "gen": gen_ph, "description": (
        "Check a run of pH readings for a technician's note. The readings input is a JSON array of pH "
        "values with two decimals, in order. Decide from the technician_note what was sampled, as exactly "
        "one of 'water', 'soil' or 'blood'; their acceptable ranges, ends included, are 6.50 to 8.50, 5.50 "
        "to 7.50 and 7.35 to 7.45. A reading is out of range when it is outside the acceptable range. The "
        "mean is the average reading rounded to two decimals with halves rounded up. The first out is the "
        "1-based position of the first reading out of range, or 'none'. Return the text '<sample>: <k> of "
        "<n> out of range, mean <mean>, first out <position>', with the mean written with exactly two "
        "decimals.")},
    {"name": "donation_match", "reference": ref_donations, "gen": gen_donations, "description": (
        "Total a donation drive for an appeal note. Each line of the donations input has the form "
        "'Donor | amount', in euros with two decimals. Decide from the appeal_note which cause the appeal "
        "is for, as exactly one of 'disaster', 'education', 'health' or 'animals'. For education and "
        "health only, an employer matches each donation with half its amount, rounded to the nearest cent "
        "with halves rounded up, and at most 100.00 euros per donation; other causes get no match. The "
        "raised amount is the sum of the donations plus the match. The top donor gave the largest "
        "donation, the first listed on a tie. Return the text '<cause> | <n> donations | raised <raised> "
        "EUR | matched <match> | top donor <name>', with both amounts written with exactly two decimals.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT
    _shape["reading"] = READINGS[_shape["name"]]

TESTS = {
    "car_park": [
        ({"entries": "AB12 CDE | 08:00 | 09:00\nKL09 XYZ | 08:00 | 12:01\nMN71 PQR | 10:00 | 12:59"},
         {"permit": "resident"}, "resident | 3 stays | fees 10.14 EUR | 1 over 4h | longest KL09 XYZ"),
        ({"entries": "AB12 CDE | 08:00 | 09:00\nKL09 XYZ | 08:00 | 12:01\nMN71 PQR | 10:00 | 12:59"},
         {"permit": "visitor"}, "visitor | 3 stays | fees 20.25 EUR | 1 over 4h | longest KL09 XYZ"),
        ({"entries": "ST03 UVW | 09:00 | 13:00"}, {"permit": "staff"},
         "staff | 1 stays | fees 0.00 EUR | 0 over 4h | longest ST03 UVW"),
    ],
    "gym_classes": [
        ({"classes": [{"name": "Step Up", "type": "cardio", "capacity": 10, "booked": 7},
                      {"name": "Spin Sprint", "type": "cardio", "capacity": 12, "booked": 9},
                      {"name": "Gentle Yoga", "type": "flexibility", "capacity": 8, "booked": 8}]},
         {"goal": "cardio"}, "cardio: recommend Spin Sprint | fill 80% | 1 full classes"),
        ({"classes": [{"name": "Gentle Yoga", "type": "flexibility", "capacity": 8, "booked": 8},
                      {"name": "Power Hour", "type": "strength", "capacity": 8, "booked": 3}]},
         {"goal": "flexibility"}, "flexibility: recommend none | fill 69% | 1 full classes"),
    ],
    "shared_bills": [
        ({"payments": "Ama | 100.00\nBen | 0.00\nCas | 0.01", "weights": {"Ama": 1, "Ben": 1, "Cas": 2}},
         {"split": "equal"}, "equal | total 100.01 | most owed Ama 66.66 | most owing Ben 33.34"),
        ({"payments": "Ama | 100.00\nBen | 0.00\nCas | 0.01", "weights": {"Ama": 1, "Ben": 1, "Cas": 2}},
         {"split": "weighted"}, "weighted | total 100.01 | most owed Ama 75.00 | most owing Cas 50.00"),
    ],
    "plant_watering": [
        ({"plants": [{"name": "fern", "last": "2026-12-10", "every": 5},
                     {"name": "fig", "last": "2026-12-12", "every": 3},
                     {"name": "ivy", "last": "2026-12-01", "every": 9}], "today": "2026-12-13"},
         {"season": "summer"}, "summer: 2 of 3 due, most overdue ivy"),
        ({"plants": [{"name": "fern", "last": "2026-12-10", "every": 5},
                     {"name": "ivy", "last": "2026-12-01", "every": 6}], "today": "2026-12-13"},
         {"season": "winter"}, "winter: 1 of 2 due, most overdue ivy"),
        ({"plants": [{"name": "jade", "last": "2026-12-12", "every": 4}], "today": "2026-12-13"},
         {"season": "winter"}, "winter: 0 of 1 due, most overdue none"),
    ],
    "train_fares": [
        ({"passengers": "Ada | 40 | 3\nBryn | 10 | 3\nCal | 65 | 5\nDot | 15 | 1"}, {"time": "offpeak"},
         "offpeak | 4 passengers | total 12.26 EUR | 1 free | top fare Ada"),
        ({"passengers": "Eve | 16 | 1\nFinn | 64 | 1"}, {"time": "weekend"},
         "weekend | 2 passengers | total 3.90 EUR | 0 free | top fare Eve"),
    ],
    "reading_challenge": [
        ({"pages": {"Beth": [100, 150], "Anil": [200, 50], "Cora": [10, 20]}}, {"genre": "romance"},
         "romance: 2 of 3 met target, average 177 pages, top Anil"),
        ({"pages": {"Ivo": [400], "Gil": [399]}}, {"genre": "history"},
         "history: 1 of 2 met target, average 400 pages, top Ivo"),
    ],
    "lab_ph": [
        ({"readings": [7.35, 7.46, 7.34, 7.40]}, {"sample": "blood"},
         "blood: 2 of 4 out of range, mean 7.39, first out 2"),
        ({"readings": [6.5, 8.5]}, {"sample": "water"}, "water: 0 of 2 out of range, mean 7.50, first out none"),
        ({"readings": [5.49, 5.50]}, {"sample": "soil"}, "soil: 1 of 2 out of range, mean 5.50, first out 1"),
    ],
    "donation_match": [
        ({"donations": "Ash | 10.01\nBea | 250.00\nCol | 250.00"}, {"cause": "health"},
         "health | 3 donations | raised 715.02 EUR | matched 205.01 | top donor Bea"),
        ({"donations": "Ash | 10.01"}, {"cause": "animals"},
         "animals | 1 donations | raised 10.01 EUR | matched 0.00 | top donor Ash"),
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
    import fast_path_planned_bench_v4

    earlier = {s["name"] for module in (fast_path_jobs_bench_v1, fast_path_jobs_bench_v2_large,
                                        fast_path_planned_bench_v2, fast_path_planned_bench_v3,
                                        fast_path_planned_bench_v4) for s in module.SHAPES}
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
    print("fast_path_planned_bench_v5.py sha256:", bench_sha256())
