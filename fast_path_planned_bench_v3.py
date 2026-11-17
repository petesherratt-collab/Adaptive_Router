"""Fresh, more varied jobs for the planned-jobs experiment V3.

Eight new job shapes, none used in any earlier run. Compared with V2 they vary
more: inputs are text lines, JSON arrays of numbers, JSON arrays of objects,
numbers and dates, and each shape's one prose field asks a different reading
(urgency, department, diet, vehicle issue, library request, site, delivery
country, formality), several of them indirect.

The prose is not in this file. It is written by a model outside the race
roster (``mistralai/mistral-large-4-0``) into
``fast_path_planned_bench_v3_prose.json`` only after the code-only reading
rules (``fast_path_code_only_v1.py``) were written from the descriptions
below and their hash recorded. Texts are checked by hand against their
planted label before any rule or model is run on them; the check is recorded
in the prose file.

Gold is by construction: ``reference(inputs, labels)`` computes the answer from
the records and the planted label. Each reference is qualified by hand-worked
tests below.

Run ``python fast_path_planned_bench_v3.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import random

STREAM_SEED = 20261117
STREAM_LENGTH = 30
OUTPUT = "result"
PROSE_PATH = Path(__file__).resolve().parent / "fast_path_planned_bench_v3_prose.json"

# The reading each shape needs: the prose input, the label name and its values.
READINGS = {
    "ticket_queue": ("email", "urgency", ["urgent", "routine"]),
    "room_bookings": ("request", "department", ["sales", "engineering", "finance", "legal"]),
    "recipe_scaling": ("guest_note", "diet", ["vegan", "vegetarian", "any"]),
    "fleet_fuel": ("report", "issue", ["tyres", "brakes", "engine", "none"]),
    "library_loans": ("message", "request", ["renew", "return", "reserve", "complain"]),
    "sensor_alerts": ("note", "site", ["north", "south", "east", "west"]),
    "invoice_vat": ("note", "country", ["UK", "Ireland", "Spain", "Italy"]),
    "event_rsvps": ("invite_note", "formality", ["formal", "casual"]),
}

FLOOR = {"sales": 2, "engineering": 5, "finance": 3, "legal": 4}
VAT = {"UK": 20, "Ireland": 23, "Spain": 21, "Italy": 22}
DRESS = {"formal": "black tie", "casual": "smart casual"}
ROOMS = ["Aspen", "Birch", "Cedar", "Maple", "Rowan"]
INGREDIENTS = [("flour", "plant"), ("rice", "plant"), ("tomato", "plant"), ("onion", "plant"),
               ("lentils", "plant"), ("spinach", "plant"), ("olive oil", "plant"),
               ("butter", "dairy"), ("cheese", "dairy"), ("cream", "dairy"), ("milk", "dairy"),
               ("chicken", "meat"), ("bacon", "meat"), ("beef", "meat"), ("anchovy", "meat")]
VANS = ["VAN-1", "VAN-2", "VAN-3", "VAN-4", "VAN-5"]
MEMBERS = ["M101", "M102", "M103", "M104", "M105", "M106"]
BOOKS = ["Dune", "Emma", "Ivanhoe", "Kim", "Middlemarch", "Persuasion", "Rebecca", "Ulysses",
         "Walden", "Beloved", "Carrie", "Hamlet", "Lolita", "Matilda"]
GOODS = ["cable", "router", "switch", "patch panel", "rack", "adapter", "fan unit", "battery"]
GUESTS = ["Asha", "Ben", "Clara", "Dev", "Elif", "Finn", "Greta", "Hugo", "Iris", "Jonas",
          "Kaja", "Luca", "Mina", "Nils", "Oona", "Pavel"]


def load_prose(path=PROSE_PATH):
    """``{shape: {label: [text, ...]}}``, hand-check exclusions removed."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    excluded = {(e["shape"], e["label"], e["text"]) for e in document.get("excluded", [])}
    return {
        shape: {label: [t for t in texts if (shape, label, t) not in excluded]
                for label, texts in labels.items()}
        for shape, labels in document["texts"].items()
    }


def _round_half_up(numerator, denominator):
    """Round numerator / denominator to the nearest integer, halves up (both positive)."""
    return (2 * numerator + denominator) // (2 * denominator)


def _money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def _cents(text):
    whole, frac = text.split(".")
    return int(whole) * 100 + int(frac)


def _lines(text):
    return [line for line in text.split("\n") if line.strip()]


def _rows(text):
    return [[p.strip() for p in line.split("|")] for line in _lines(text)]


def _minutes(clock):
    hour, minute = clock.split(":")
    return int(hour) * 60 + int(minute)


def _first_best(items, key):
    """The first item with the greatest key, or None."""
    best = None
    for item in items:
        if best is None or key(item) > key(best):
            best = item
    return best


# ---- references --------------------------------------------------------

def ref_tickets(inputs, labels):
    rows = _rows(inputs["tickets"])
    priority = 1 if labels["urgency"] == "urgent" else 3
    position = 1 + sum(int(p) <= priority for _, _, p in rows)
    oldest = min(rows, key=lambda r: _minutes(r[1]))[0] if rows else "none"
    return (f"{labels['urgency']} | priority {priority} | position {position} of {len(rows) + 1}"
            f" | oldest {oldest}")


def ref_rooms(inputs, labels):
    per_room = {}
    for booking in inputs["bookings"]:
        length = _minutes(booking["end"]) - _minutes(booking["start"])
        per_room[booking["room"]] = per_room.get(booking["room"], 0) + length
    busiest = sorted(per_room, key=lambda k: (-per_room[k], k))[0] if per_room else "none"
    department = labels["department"]
    return (f"{department} floor {FLOOR[department]} | {len(inputs['bookings'])} bookings"
            f" | busiest {busiest} | {sum(per_room.values())} minutes booked")


def ref_recipe(inputs, labels):
    dropped = {"vegan": {"dairy", "meat"}, "vegetarian": {"meat"}, "any": set()}[labels["diet"]]
    kept = [(i["name"], _round_half_up(i["grams"] * inputs["servings"], 4))
            for i in inputs["ingredients"] if i["kind"] not in dropped]
    heaviest = _first_best(kept, key=lambda k: k[1])
    return (f"{labels['diet']}: {len(kept)} ingredients, {sum(g for _, g in kept)}g, heaviest "
            f"{heaviest[0] if heaviest else 'none'}")


def _per_100km(tenths_litres, km):
    tenths = _round_half_up(100 * tenths_litres, km)
    return f"{tenths // 10}.{tenths % 10}"


def ref_fleet(inputs, labels):
    per_van = {}
    for van, km, litres in _rows(inputs["trips"]):
        totals = per_van.setdefault(van, [0, 0])
        totals[0] += int(km)
        totals[1] += round(float(litres) * 10)
    # Exact comparison of litres per km; alphabetical on a tie.
    worst = sorted(per_van, key=lambda v: (-Fraction(per_van[v][1], per_van[v][0]), v))[0]
    fleet_km = sum(v[0] for v in per_van.values())
    fleet_tenths = sum(v[1] for v in per_van.values())
    action = "no visit" if labels["issue"] == "none" else f"book {labels['issue']}"
    return (f"{worst} worst at {_per_100km(per_van[worst][1], per_van[worst][0])} l/100km | fleet "
            f"{_per_100km(fleet_tenths, fleet_km)} l/100km | {action}")


def _day(date):
    year, month, day = date.split("-")
    assert (year, month) == ("2026", "11"), date
    return int(day)


def ref_library(inputs, labels):
    today = _day(inputs["today"])
    late = [(title, today - _day(due)) for _, title, due in _rows(inputs["loans"])
            if _day(due) < today]
    worst = _first_best(late, key=lambda item: item[1])
    fines = 20 * sum(days for _, days in late)
    return (f"{labels['request']} | {len(late)} overdue | fines {_money(fines)} EUR | most overdue "
            f"{worst[0] if worst else 'none'}")


def ref_sensor(inputs, labels):
    tenths = [round(x * 10) for x in inputs["readings"]]
    limit = round(inputs["threshold"] * 10)
    above = [t > limit for t in tenths]
    run = longest = 0
    for flag in above:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    peak = max(tenths)
    mean = _round_half_up(sum(tenths), len(tenths))
    return (f"{labels['site']}: {sum(above)} alerts, peak {peak // 10}.{peak % 10}, longest run "
            f"{longest}, mean {mean // 10}.{mean % 10}")


def ref_invoice(inputs, labels):
    net = sum(line["qty"] * _cents(line["unit_price"]) for line in inputs["lines"])
    vat = _round_half_up(net * VAT[labels["country"]], 100)
    return (f"{labels['country']} | net {_money(net)} | VAT {_money(vat)} | gross {_money(net + vat)}"
            f" EUR | {len(inputs['lines'])} lines")


def ref_rsvps(inputs, labels):
    rows = _rows(inputs["rsvps"])
    yes = [(name, int(guests)) for name, answer, guests in rows if answer == "yes"]
    largest = _first_best(yes, key=lambda item: item[1])
    attending = sum(1 + guests for _, guests in yes)
    maybe = sum(answer == "maybe" for _, answer, _ in rows)
    return (f"{DRESS[labels['formality']]} | {attending} attending | {maybe} maybe | largest party "
            f"{largest[0] if largest else 'none'}")


# ---- generators --------------------------------------------------------

def _prose(r, prose, shape):
    field, name, values = READINGS[shape]
    label = r.choice(values)
    return field, label, r.choice(prose[shape][label])


def gen_tickets(r, prose):
    field, label, text = _prose(r, prose, "ticket_queue")
    ids = r.sample(range(100, 1000), r.randint(6, 15))
    lines = [f"T-{i} | {r.randint(7, 18):02d}:{r.choice([0, 5, 15, 30, 45, 50]):02d} | {r.randint(1, 3)}"
             for i in ids]
    return {"tickets": "\n".join(lines), field: text}, {"urgency": label}


def gen_rooms(r, prose):
    field, label, text = _prose(r, prose, "room_bookings")
    bookings = []
    for _ in range(r.randint(5, 12)):
        start = r.randint(16, 34) * 30
        end = start + r.choice([30, 45, 60, 90, 120])
        bookings.append({"room": r.choice(ROOMS), "start": f"{start // 60:02d}:{start % 60:02d}",
                         "end": f"{end // 60:02d}:{end % 60:02d}"})
    return {"bookings": bookings, field: text}, {"department": label}


def gen_recipe(r, prose):
    field, label, text = _prose(r, prose, "recipe_scaling")
    chosen = r.sample(INGREDIENTS, r.randint(5, 9))
    ingredients = [{"name": name, "grams": r.choice([5, 10, 15, 25, 30, 50, 75, 120, 200, 250, 333]),
                    "kind": kind} for name, kind in chosen]
    return {"ingredients": ingredients, "servings": r.randint(1, 12), field: text}, {"diet": label}


def gen_fleet(r, prose):
    field, label, text = _prose(r, prose, "fleet_fuel")
    vans = r.sample(VANS, r.randint(2, 5))
    lines = []
    for _ in range(r.randint(8, 16)):
        km = r.randint(12, 420)
        litres = round(km * r.uniform(0.06, 0.14), 1)
        lines.append(f"{r.choice(vans)} | {km} | {litres:.1f}")
    return {"trips": "\n".join(lines), field: text}, {"issue": label}


def gen_library(r, prose):
    field, label, text = _prose(r, prose, "library_loans")
    today = r.randint(10, 30)
    lines = [f"{r.choice(MEMBERS)} | {title} | 2026-11-{r.randint(1, 30):02d}"
             for title in r.sample(BOOKS, r.randint(6, 12))]
    return {"loans": "\n".join(lines), "today": f"2026-11-{today:02d}", field: text}, {"request": label}


def gen_sensor(r, prose):
    field, label, text = _prose(r, prose, "sensor_alerts")
    base = r.randint(150, 400)
    readings = [round((base + r.randint(-60, 60)) / 10, 1) for _ in range(r.randint(12, 24))]
    threshold = round((base + r.randint(0, 40)) / 10, 1)
    return {"readings": readings, "threshold": threshold, field: text}, {"site": label}


def gen_invoice(r, prose):
    field, label, text = _prose(r, prose, "invoice_vat")
    lines = [{"item": item, "qty": r.randint(1, 25),
              "unit_price": f"{r.randint(1, 400)}.{r.choice([0, 5, 25, 49, 50, 95, 99]):02d}"}
             for item in r.sample(GOODS, r.randint(2, 6))]
    return {"lines": lines, field: text}, {"country": label}


def gen_rsvps(r, prose):
    field, label, text = _prose(r, prose, "event_rsvps")
    lines = [f"{name} | {r.choice(['yes', 'yes', 'no', 'maybe'])} | {r.choice([0, 0, 1, 1, 2, 3])}"
             for name in r.sample(GUESTS, r.randint(8, 14))]
    return {"rsvps": "\n".join(lines), field: text}, {"formality": label}


SHAPES = [
    {"name": "ticket_queue", "reference": ref_tickets, "gen": gen_tickets, "description": (
        "Triage a new support email into a queue. Each line of the tickets input has the form "
        "'T-nnn | HH:MM | p': an existing ticket's id, the time it was opened and its priority from 1 "
        "(highest) to 3 (lowest). Decide whether the email is 'urgent' or 'routine'. The new ticket "
        "gets priority 1 if the email is urgent and 3 if it is routine. Its position in the queue is "
        "one plus the number of existing tickets whose priority number is less than or equal to the new "
        "ticket's. The oldest ticket is the id of the existing ticket with the earliest time, the first "
        "listed on a tie. Return the text '<urgency> | priority <p> | position <k> of <n> | oldest <id>', "
        "where n is the number of existing tickets plus one.")},
    {"name": "room_bookings", "reference": ref_rooms, "gen": gen_rooms, "description": (
        "Summarise a day's meeting room bookings for a new request. The bookings input is a JSON array "
        "of objects with keys 'room', 'start' and 'end', times as 'HH:MM' on the same day. Decide which "
        "department the person writing the request works in, as exactly one of 'sales', 'engineering', "
        "'finance' or 'legal'; their floors are 2, 5, 3 and 4. A booking's length is the minutes from "
        "its start to its end. The busiest room has the most minutes booked in total, the alphabetically "
        "first on a tie, or 'none' if there are no bookings. Return the text '<department> floor "
        "<floor> | <b> bookings | busiest <room> | <m> minutes booked', where b is the number of "
        "bookings and m is the total minutes over all bookings.")},
    {"name": "recipe_scaling", "reference": ref_recipe, "gen": gen_recipe, "description": (
        "Adapt a recipe written for 4 servings. The ingredients input is a JSON array of objects with "
        "keys 'name', 'grams' (for 4 servings) and 'kind', which is 'plant', 'dairy' or 'meat'; the "
        "servings input is the number of servings wanted. Decide from the guest_note what the guest "
        "eats, as exactly one of 'vegan', 'vegetarian' or 'any'. Vegan removes dairy and meat "
        "ingredients, vegetarian removes meat ingredients, and any removes nothing. Scale each remaining "
        "ingredient's grams by servings / 4, rounded to the nearest whole gram with halves rounded up. "
        "The heaviest ingredient is the remaining one with the most scaled grams, the first listed on a "
        "tie, or 'none'. Return the text '<diet>: <k> ingredients, <total>g, heaviest <name>', where k "
        "is the number of remaining ingredients and total is the sum of their scaled grams.")},
    {"name": "fleet_fuel", "reference": ref_fleet, "gen": gen_fleet, "description": (
        "Review a delivery fleet's fuel use. Each line of the trips input has the form "
        "'VAN-n | km | litres', with whole kilometres and litres to one decimal. Decide from the "
        "driver's report which problem it describes, as exactly one of 'tyres', 'brakes', 'engine' or "
        "'none'. A van's consumption is its total litres times 100 divided by its total kilometres, in "
        "litres per 100 km. The worst van has the highest consumption, the alphabetically first on a "
        "tie. The fleet consumption is the same calculation over all trips. Write each consumption "
        "rounded to one decimal with halves rounded up. The action is 'no visit' if the problem is "
        "'none' and otherwise 'book ' followed by the problem. Return the text '<van> worst at <c> "
        "l/100km | fleet <f> l/100km | <action>'.")},
    {"name": "library_loans", "reference": ref_library, "gen": gen_library, "description": (
        "Summarise a library's loans for a member's message. Each line of the loans input has the form "
        "'member | title | YYYY-MM-DD', the date being the due date; the today input is today's date in "
        "the same form, and all dates are in November 2026. Classify what the message asks for as "
        "exactly one of 'renew', 'return', 'reserve' or 'complain'. A loan is overdue when its due date "
        "is before today; its days overdue are the days from the due date to today. The fine is 0.20 "
        "EUR per overdue day summed over all overdue loans. The most overdue title is the title with the "
        "most days overdue, the first listed on a tie, or 'none'. Return the text '<request> | <o> "
        "overdue | fines <fine> EUR | most overdue <title>', with the fine written with two decimals and "
        "o the number of overdue loans.")},
    {"name": "sensor_alerts", "reference": ref_sensor, "gen": gen_sensor, "description": (
        "Summarise a sensor's readings. The readings input is a JSON array of numbers with one decimal, "
        "in time order, and the threshold input is a number with one decimal. Decide which site the "
        "technician's note is about, as exactly one of 'north', 'south', 'east' or 'west'. A reading is "
        "an alert when it is greater than the threshold. The longest run is the largest number of "
        "consecutive alerts. The peak is the largest reading. The mean is the average reading rounded to "
        "one decimal with halves rounded up. Write the peak and the mean with exactly one decimal. Return "
        "the text '<site>: <a> alerts, peak <peak>, longest run <r>, mean <mean>', where a is the number "
        "of alerts.")},
    {"name": "invoice_vat", "reference": ref_invoice, "gen": gen_invoice, "description": (
        "Total an invoice with VAT. The lines input is a JSON array of objects with keys 'item', 'qty' "
        "(a whole number) and 'unit_price' (euros as text with two decimals). Decide from the note which "
        "country the order is delivered to, as exactly one of 'UK', 'Ireland', 'Spain' or 'Italy'; their "
        "VAT rates are 20, 23, 21 and 22 percent. The net is the sum of qty times unit_price over all "
        "lines. The VAT is the net times the rate divided by 100, rounded to the nearest cent with halves "
        "rounded up. The gross is net plus VAT. Return the text '<country> | net <net> | VAT <vat> | "
        "gross <gross> EUR | <n> lines', with each amount written with exactly two decimals and n the "
        "number of lines.")},
    {"name": "event_rsvps", "reference": ref_rsvps, "gen": gen_rsvps, "description": (
        "Summarise replies to an invitation. Each line of the rsvps input has the form "
        "'Name | answer | guests', where answer is 'yes', 'no' or 'maybe' and guests is the number of "
        "extra people the person would bring. Decide whether the invite_note describes a 'formal' or a "
        "'casual' event; the dress code is 'black tie' for formal and 'smart casual' for casual. The "
        "number attending is the sum, over 'yes' answers, of one plus guests. Count the 'maybe' answers. "
        "The largest party is the name of the 'yes' answer with the most guests, the first listed on a "
        "tie, or 'none' if nobody said yes. Return the text '<dress code> | <h> attending | <m> maybe | "
        "largest party <name>'.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT
    _shape["reading"] = READINGS[_shape["name"]]

TESTS = {
    "ticket_queue": [
        ({"tickets": "T-101 | 09:30 | 2\nT-102 | 08:15 | 1\nT-103 | 08:15 | 3"}, {"urgency": "urgent"},
         "urgent | priority 1 | position 2 of 4 | oldest T-102"),
        ({"tickets": "T-101 | 09:30 | 2\nT-102 | 08:15 | 1\nT-103 | 08:15 | 3"}, {"urgency": "routine"},
         "routine | priority 3 | position 4 of 4 | oldest T-102"),
        ({"tickets": "T-500 | 17:00 | 2"}, {"urgency": "urgent"},
         "urgent | priority 1 | position 1 of 2 | oldest T-500"),
    ],
    "room_bookings": [
        ({"bookings": [{"room": "Cedar", "start": "09:00", "end": "10:30"},
                       {"room": "Aspen", "start": "11:00", "end": "12:00"},
                       {"room": "Aspen", "start": "13:00", "end": "13:30"}]},
         {"department": "legal"}, "legal floor 4 | 3 bookings | busiest Aspen | 180 minutes booked"),
        ({"bookings": [{"room": "Maple", "start": "08:00", "end": "09:00"},
                       {"room": "Birch", "start": "10:00", "end": "11:00"}]},
         {"department": "sales"}, "sales floor 2 | 2 bookings | busiest Birch | 120 minutes booked"),
        ({"bookings": []}, {"department": "finance"},
         "finance floor 3 | 0 bookings | busiest none | 0 minutes booked"),
    ],
    "recipe_scaling": [
        ({"ingredients": [{"name": "flour", "grams": 250, "kind": "plant"},
                          {"name": "butter", "grams": 333, "kind": "dairy"},
                          {"name": "bacon", "grams": 120, "kind": "meat"}], "servings": 6},
         {"diet": "vegetarian"}, "vegetarian: 2 ingredients, 875g, heaviest butter"),
        ({"ingredients": [{"name": "flour", "grams": 250, "kind": "plant"},
                          {"name": "butter", "grams": 333, "kind": "dairy"},
                          {"name": "bacon", "grams": 120, "kind": "meat"}], "servings": 6},
         {"diet": "vegan"}, "vegan: 1 ingredients, 375g, heaviest flour"),
        ({"ingredients": [{"name": "rice", "grams": 10, "kind": "plant"},
                          {"name": "onion", "grams": 10, "kind": "plant"}], "servings": 1},
         {"diet": "any"}, "any: 2 ingredients, 6g, heaviest rice"),
        ({"ingredients": [{"name": "beef", "grams": 30, "kind": "meat"}], "servings": 3},
         {"diet": "vegan"}, "vegan: 0 ingredients, 0g, heaviest none"),
    ],
    "fleet_fuel": [
        ({"trips": "VAN-1 | 100 | 8.0\nVAN-2 | 200 | 20.0\nVAN-1 | 100 | 10.0"}, {"issue": "brakes"},
         "VAN-2 worst at 10.0 l/100km | fleet 9.5 l/100km | book brakes"),
        ({"trips": "VAN-3 | 300 | 25.1\nVAN-2 | 150 | 12.5"}, {"issue": "none"},
         "VAN-3 worst at 8.4 l/100km | fleet 8.4 l/100km | no visit"),
        ({"trips": "VAN-4 | 100 | 9.0\nVAN-1 | 50 | 4.5"}, {"issue": "tyres"},
         "VAN-1 worst at 9.0 l/100km | fleet 9.0 l/100km | book tyres"),
        ({"trips": "VAN-5 | 40 | 3.0"}, {"issue": "engine"},
         "VAN-5 worst at 7.5 l/100km | fleet 7.5 l/100km | book engine"),
    ],
    "library_loans": [
        ({"loans": "M101 | Dune | 2026-11-10\nM102 | Emma | 2026-11-20\nM103 | Kim | 2026-11-05",
          "today": "2026-11-15"}, {"request": "renew"},
         "renew | 2 overdue | fines 3.00 EUR | most overdue Kim"),
        ({"loans": "M101 | Dune | 2026-11-15\nM102 | Emma | 2026-11-20", "today": "2026-11-15"},
         {"request": "complain"}, "complain | 0 overdue | fines 0.00 EUR | most overdue none"),
        ({"loans": "M101 | Dune | 2026-11-01\nM102 | Emma | 2026-11-01", "today": "2026-11-02"},
         {"request": "reserve"}, "reserve | 2 overdue | fines 0.40 EUR | most overdue Dune"),
    ],
    "sensor_alerts": [
        ({"readings": [20.0, 25.5, 26.0, 19.9, 25.1], "threshold": 25.0}, {"site": "east"},
         "east: 3 alerts, peak 26.0, longest run 2, mean 23.3"),
        ({"readings": [10.0, 10.1], "threshold": 10.1}, {"site": "north"},
         "north: 0 alerts, peak 10.1, longest run 0, mean 10.1"),
        ({"readings": [1.0, 1.1, 1.1, 1.1], "threshold": 0.5}, {"site": "west"},
         "west: 4 alerts, peak 1.1, longest run 4, mean 1.1"),
    ],
    "invoice_vat": [
        ({"lines": [{"item": "cable", "qty": 3, "unit_price": "10.50"},
                    {"item": "router", "qty": 1, "unit_price": "99.99"}]},
         {"country": "Ireland"}, "Ireland | net 131.49 | VAT 30.24 | gross 161.73 EUR | 2 lines"),
        ({"lines": [{"item": "fan unit", "qty": 1, "unit_price": "0.50"}]}, {"country": "Spain"},
         "Spain | net 0.50 | VAT 0.11 | gross 0.61 EUR | 1 lines"),
        ({"lines": [{"item": "rack", "qty": 2, "unit_price": "1.25"}]}, {"country": "UK"},
         "UK | net 2.50 | VAT 0.50 | gross 3.00 EUR | 1 lines"),
    ],
    "event_rsvps": [
        ({"rsvps": "Asha | yes | 2\nBen | no | 1\nClara | maybe | 0\nDev | yes | 2\nElif | yes | 0"},
         {"formality": "formal"}, "black tie | 7 attending | 1 maybe | largest party Asha"),
        ({"rsvps": "Asha | no | 2\nBen | maybe | 1"}, {"formality": "casual"},
         "smart casual | 0 attending | 1 maybe | largest party none"),
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
    """Stand-in texts for checking the generators before the real prose exists."""
    return {shape: {label: [f"placeholder {label}"] for label in values}
            for shape, (_, _, values) in READINGS.items()}


def self_verify(prose=None):
    import fast_path_jobs_bench_v1
    import fast_path_jobs_bench_v2_large
    import fast_path_planned_bench_v2

    earlier = {s["name"] for s in fast_path_jobs_bench_v1.SHAPES + fast_path_jobs_bench_v2_large.SHAPES
               + fast_path_planned_bench_v2.SHAPES}
    names = [s["name"] for s in SHAPES]
    assert len(names) == len(set(names)) and not set(names) & earlier, "shape names must be new"
    assert set(names) == set(READINGS)
    if prose is None:
        prose = load_prose() if PROSE_PATH.exists() else placeholder_prose()
    for shape in SHAPES:
        for inputs, labels, expected in TESTS[shape["name"]]:
            got = shape["reference"](inputs, labels)
            assert got == expected, f"{shape['name']}: {got!r} != {expected!r}"
        field, label, values = shape["reading"]
        assert field in shape["description"], f"{shape['name']}: reading field not named"
        assert all(f"'{v}'" in shape["description"] for v in values), f"{shape['name']}: label missing"
        assert set(prose[shape["name"]]) == set(values), f"{shape['name']}: prose labels"
        assert all(prose[shape["name"]][v] for v in values), f"{shape['name']}: empty label"
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
    print("fast_path_planned_bench_v3.py sha256:", bench_sha256())
