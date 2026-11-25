"""Phase C jobs (V7): unseen shapes, both kinds mixed.

Eight new job shapes, none used before, in two families:

- **one reading** (calculation-heavy): one prose note decides one label, and the
  rest is pricing, rounding, caps, thresholds and ties. These are the jobs where
  writing the whole job once has been fastest.
- **many readings**: a list whose items each carry a short text needing reading.
  These are the jobs where the written program has been more accurate than the
  race but slower.

Gold is by construction: ``reference(inputs, labels)`` takes the planted labels.
The texts come from ``fast_path_planned_bench_v7_prose.json``, written by a model
outside the race roster after this file was frozen.

Run ``python fast_path_planned_bench_v7.py`` to self-verify and print the SHA-256.
"""

from __future__ import annotations

import json
from pathlib import Path
import random

from fast_path_planned_bench_v3 import _cents, _money, _minutes, _round_half_up, load_prose as _load

STREAM_SEED = 20261125
STREAM_LENGTH = 30
OUTPUT = "result"
PROSE_PATH = Path(__file__).resolve().parent / "fast_path_planned_bench_v7_prose.json"

# one-reading shapes: shape -> (note input, label name, labels)
ONE = {
    "parcel_postage": ("sender_note", "service", ["standard", "express", "tracked"]),
    "room_booking": ("booking_note", "event", ["meeting", "workshop", "party"]),
    "tip_split": ("tip_note", "service", ["poor", "good", "excellent"]),
    "library_fines": ("member_note", "member", ["child", "adult", "senior"]),
}
# many-reading shapes: shape -> (list input, text field, label name, labels)
MANY = {
    "ticket_triage": ("tickets", "text", "category", ["billing", "bug", "account"]),
    "shopping_receipt": ("lines", "text", "kind", ["food", "household", "alcohol"]),
    "repair_requests": ("requests", "text", "urgency", ["emergency", "routine", "cosmetic"]),
    "party_replies": ("replies", "text", "answer", ["yes", "maybe", "no"]),
}
FAMILY = {**{name: "one" for name in ONE}, **{name: "many" for name in MANY}}

TIP_PER_MILLE = {"poor": 0, "good": 125, "excellent": 150}
SLA_MINUTES = {"billing": 240, "bug": 60, "account": 120}
FINE_PER_DAY = {"child": 0, "adult": 25, "senior": 10}
FINE_CAP = 500

PARCEL_IDS = ["A1", "B2", "C3", "D4", "E5", "F6", "G7", "H8"]
ROOMS = ["Ash", "Birch", "Cedar", "Elm", "Hazel", "Larch", "Oak", "Rowan", "Yew"]
TITLES = ["Atlas", "Bees", "Clay", "Dune", "Emma", "Fog", "Gale", "Hush", "Iris", "Jade"]
NAMES = ["Abi", "Bo", "Cat", "Dan", "Eve", "Fin", "Gus", "Hal", "Ivy", "Joe", "Kim", "Lou"]
FLATS = ["1A", "1B", "2A", "2B", "3A", "3B"]


def load_prose(path=PROSE_PATH):
    return _load(path)


def _ceil_div(a, b):
    return -(-a // b)


# ---- references: one reading --------------------------------------------

def _parcel_base(grams):
    if grams <= 100:
        return 85
    if grams <= 500:
        return 155
    if grams <= 1000:
        return 240
    return 240 + 75 * _ceil_div(grams - 1000, 500)


def ref_parcels(inputs, labels):
    service = labels["service"]
    total = 0
    for parcel in inputs["parcels"]:
        base = _parcel_base(parcel["grams"])
        total += {"standard": base, "express": _round_half_up(3 * base, 2), "tracked": base + 120}[service]
    heaviest = inputs["parcels"][0]
    for parcel in inputs["parcels"][1:]:
        if parcel["grams"] > heaviest["grams"]:
            heaviest = parcel
    return f"{service}: total {_money(total)} | {len(inputs['parcels'])} parcels | heaviest {heaviest['id']}"


def ref_rooms(inputs, labels):
    event, people = labels["event"], inputs["attendees"]
    need = people + _ceil_div(people, 5) if event == "workshop" else people
    fits = [r for r in inputs["rooms"] if r["seats"] >= need and (event != "party" or r["music"])]
    if not fits:
        return f"{event}: none"
    room = sorted(fits, key=lambda r: (_cents(r["rate"]), r["seats"], r["name"]))[0]
    cost = _cents(room["rate"]) * inputs["hours"]
    if event == "party":
        cost = _round_half_up(cost * 11, 10)
    return f"{event}: {room['name']} {_money(cost)}"


def ref_tips(inputs, labels):
    subtotal = sum(_cents(item) for item in inputs["items"])
    total = subtotal + _round_half_up(subtotal * TIP_PER_MILLE[labels["service"]], 1000)
    each = _ceil_div(total, inputs["diners"])
    return f"total {_money(total)} | each {_money(each)} | extra {_money(each * inputs['diners'] - total)}"


def ref_fines(inputs, labels):
    member, today = labels["member"], int(inputs["today"][-2:])
    fines, overdue, worst = 0, 0, None
    for loan in inputs["loans"]:
        days = today - int(loan["due"][-2:])
        if days > 0:
            overdue += 1
            fines += min(days * FINE_PER_DAY[member], FINE_CAP)
            if worst is None or days > worst[0]:
                worst = (days, loan["title"])
    return f"{member}: fines {_money(fines)} | {overdue} overdue | most overdue {worst[1] if worst else 'none'}"


# ---- references: many readings ------------------------------------------

def ref_tickets(inputs, labels):
    rows = list(zip(inputs["tickets"], labels["category"]))
    counts = {c: sum(cat == c for _, cat in rows) for c in MANY["ticket_triage"][3]}
    now = _minutes(inputs["now"])
    breached = [t["id"] for t, cat in rows if now - _minutes(t["opened"]) > SLA_MINUTES[cat]]
    return (f"billing {counts['billing']}, bug {counts['bug']}, account {counts['account']} | breached "
            f"{', '.join(breached) if breached else 'none'}")


def ref_receipt(inputs, labels):
    totals = {k: 0 for k in MANY["shopping_receipt"][3]}
    treats = 0
    for line, kind in zip(inputs["lines"], labels["kind"]):
        totals[kind] += _cents(line["price"]) * line["qty"]
        treats += kind == "food" and _cents(line["price"]) > 500
    return (f"food {_money(totals['food'])} | household {_money(totals['household'])} | alcohol "
            f"{_money(totals['alcohol'])} | card {_money(totals['food'] + totals['household'])} | {treats} treats")


def ref_repairs(inputs, labels):
    rows = list(zip(inputs["requests"], labels["urgency"]))
    count = {u: sum(x == u for _, x in rows) for u in MANY["repair_requests"][3]}
    flats = sorted({r["flat"] for r, u in rows if u == "emergency"})
    per_flat = {}
    for request, _ in rows:
        per_flat[request["flat"]] = per_flat.get(request["flat"], 0) + 1
    busiest = sorted(per_flat, key=lambda f: (-per_flat[f], f))[0]
    return (f"{count['emergency']} emergency in {', '.join(flats) if flats else 'none'} | {count['routine']} routine | "
            f"{count['cosmetic']} cosmetic | busiest {busiest}")


def ref_replies(inputs, labels):
    rows = list(zip(inputs["replies"], labels["answer"]))
    n = {a: sum(x == a for _, x in rows) for a in ("yes", "maybe", "no")}
    coming = sum(1 + r["guests"] for r, a in rows if a == "yes")
    maybe = sum(1 + r["guests"] for r, a in rows if a == "maybe")
    return (f"{n['yes']} yes, {n['maybe']} maybe, {n['no']} no | coming {coming} | estimate "
            f"{coming + _ceil_div(maybe, 2)}")


# ---- generators -----------------------------------------------------------

def _note(r, prose, shape):
    _, label, values = ONE[shape]
    pick = r.choice(values)
    return pick, r.choice(prose[shape][pick])


def _items(r, prose, shape, count):
    values = MANY[shape][3]
    picks = [r.choice(values) for _ in range(count)]
    return picks, [r.choice(prose[shape][label]) for label in picks]


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def gen_parcels(r, prose):
    label, text = _note(r, prose, "parcel_postage")
    ids = r.sample(PARCEL_IDS, r.randint(1, 5))
    grams = [r.choice([100, 101, 500, 501, 1000, 1001, 1500, 1501, r.randint(20, 3000)]) for _ in ids]
    return {"parcels": [{"id": i, "grams": g} for i, g in zip(ids, grams)], "sender_note": text}, {"service": label}


def gen_rooms(r, prose):
    label, text = _note(r, prose, "room_booking")
    rooms = [{"name": n, "seats": r.choice([6, 8, 10, 12, 12, 15, 20, 30]),
              "rate": f"{r.randint(12, 45)}.{r.choice([0, 25, 50, 75]):02d}", "music": r.random() < 0.4}
             for n in r.sample(ROOMS, r.randint(2, 6))]
    return {"rooms": rooms, "attendees": r.randint(4, 24), "hours": r.randint(1, 6), "booking_note": text}, \
        {"event": label}


def gen_tips(r, prose):
    label, text = _note(r, prose, "tip_split")
    items = [f"{r.randint(1, 40)}.{r.choice([0, 4, 5, 20, 50, 95, 99]):02d}" for _ in range(r.randint(1, 6))]
    return {"items": items, "diners": r.randint(1, 7), "tip_note": text}, {"service": label}


def gen_fines(r, prose):
    label, text = _note(r, prose, "library_fines")
    today = r.randint(5, 31)
    loans = [{"title": t, "due": f"2026-12-{r.randint(1, 31):02d}"} for t in r.sample(TITLES, r.randint(1, 5))]
    return {"loans": loans, "today": f"2026-12-{today:02d}", "member_note": text}, {"member": label}


def gen_tickets(r, prose):
    labels, texts = _items(r, prose, "ticket_triage", r.randint(4, 10))
    t, tickets = r.randint(6 * 60, 10 * 60), []
    for i, text in enumerate(texts, 1):
        tickets.append({"id": f"T{i}", "opened": _clock(t), "text": text})
        t += r.choice([5, 15, 30, 45, 60])
    now = t + r.choice([0, 30, 60, 61, 120, 121, 240, 241])
    return {"tickets": tickets, "now": _clock(min(now, 23 * 60 + 59))}, {"category": labels}


def gen_receipt(r, prose):
    labels, texts = _items(r, prose, "shopping_receipt", r.randint(4, 10))
    lines = [{"price": f"{r.choice([r.randint(0, 4), 5, r.randint(6, 15)])}.{r.choice([0, 1, 49, 99]):02d}",
              "qty": r.randint(1, 4), "text": t} for t in texts]
    for line in lines:
        if line["price"] == "0.00":
            line["price"] = "0.99"
    return {"lines": lines}, {"kind": labels}


def gen_repairs(r, prose):
    labels, texts = _items(r, prose, "repair_requests", r.randint(4, 10))
    return {"requests": [{"flat": r.choice(FLATS), "text": t} for t in texts]}, {"urgency": labels}


def gen_replies(r, prose):
    labels, texts = _items(r, prose, "party_replies", r.randint(4, 11))
    names = r.sample(NAMES, len(texts))
    return {"replies": [{"name": n, "guests": r.choice([0, 0, 1, 1, 2, 3]), "text": t}
                        for n, t in zip(names, texts)]}, {"answer": labels}


SHAPES = [
    {"name": "parcel_postage", "reference": ref_parcels, "gen": gen_parcels, "description": (
        "Price a batch of parcels. The parcels input is a JSON array of objects with keys 'id' and 'grams'; the "
        "sender_note input is the sender's message. Decide from the note which service the sender wants, as exactly "
        "one of 'standard', 'express' or 'tracked'. Each parcel's base price is 0.85 up to 100 grams, 1.55 up to "
        "500 grams, 2.40 up to 1000 grams, and above 1000 grams 2.40 plus 0.75 for every started 500 grams over "
        "1000. Standard costs the base price; express costs one and a half times the base price, rounded to the "
        "penny with halves rounded up; tracked costs the base price plus 1.20. The heaviest parcel is the one with "
        "the most grams, the first in the list on a tie. Return the text '<service>: total <total> | <n> parcels | "
        "heaviest <id>', the total in pounds with exactly two decimals.")},
    {"name": "room_booking", "reference": ref_rooms, "gen": gen_rooms, "description": (
        "Choose a room for a booking. The rooms input is a JSON array of objects with keys 'name', 'seats', 'rate' "
        "(pounds per hour as text with two decimals) and 'music' (true or false); attendees and hours are numbers; "
        "the booking_note input is the customer's message. Decide from the note what the event is, as exactly one "
        "of 'meeting', 'workshop' or 'party'. A meeting needs seats for the attendees; a workshop needs seats for "
        "the attendees plus one more for every started five attendees; a party needs seats for the attendees and a "
        "room with music. Choose the suitable room with the lowest rate, then the fewest seats, then the "
        "alphabetically first name. The cost is the rate times the hours, and for a party 10% more, rounded to the "
        "penny with halves rounded up. Return the text '<event>: <room> <cost>' with the cost to two decimals, or "
        "'<event>: none' if no room is suitable.")},
    {"name": "tip_split", "reference": ref_tips, "gen": gen_tips, "description": (
        "Split a restaurant bill. The items input is a JSON array of prices (pounds as text with two decimals), "
        "diners is a number and the tip_note input is the table's comment on the service. Decide from the note how "
        "the service was, as exactly one of 'poor', 'good' or 'excellent'. The tip is 0% for poor, 12.5% for good "
        "and 15% for excellent service, of the sum of the items, rounded to the penny with halves rounded up. The "
        "total is the sum plus the tip. Each diner pays the total divided by the diners, rounded up to the next "
        "penny; the extra is what the diners pay together minus the total. Return the text 'total <total> | each "
        "<each> | extra <extra>', all in pounds with exactly two decimals.")},
    {"name": "library_fines", "reference": ref_fines, "gen": gen_fines, "description": (
        "Work out library fines. The loans input is a JSON array of objects with keys 'title' and 'due' (a date "
        "'YYYY-MM-DD' in December 2026); today is a date in the same month; the member_note input is a message "
        "about the borrower. Decide from the note what kind of member the borrower is, as exactly one of 'child', "
        "'adult' or 'senior'. A loan is overdue by the number of days from its due date to today, when that is more "
        "than zero. Each overdue loan's fine is its days overdue times 0.00 for a child, 0.25 for an adult or 0.10 "
        "for a senior, at most 5.00 per loan. The most overdue loan is the one overdue by the most days, the first "
        "in the list on a tie. Return the text '<member>: fines <total> | <k> overdue | most overdue <title>', the "
        "total in pounds with two decimals and the title 'none' if no loan is overdue.")},
    {"name": "ticket_triage", "reference": ref_tickets, "gen": gen_tickets, "description": (
        "Triage support tickets. The tickets input is a JSON array of objects with keys 'id', 'opened' ('HH:MM', "
        "the same day) and 'text'; now is the time 'HH:MM'. Decide from each ticket's text its category, as exactly "
        "one of 'billing', 'bug' or 'account'. A ticket has breached its target when the minutes from opened to now "
        "are more than 240 for billing, 60 for a bug or 120 for account. Return the text 'billing <b>, bug <g>, "
        "account <a> | breached <ids>', where the ids are the breached tickets in list order separated by ', ', "
        "or 'none'.")},
    {"name": "shopping_receipt", "reference": ref_receipt, "gen": gen_receipt, "description": (
        "Sort a shopping receipt. The lines input is a JSON array of objects with keys 'price' (pounds as text with "
        "two decimals, for one unit), 'qty' and 'text'; decide from each line's text what was bought, as exactly one "
        "of 'food', 'household' or 'alcohol'. Each line costs its price times its qty. The card total is food plus "
        "household. A treat is a food line whose unit price is over 5.00. Return the text 'food <f> | household "
        "<h> | alcohol <a> | card <c> | <t> treats', the amounts in pounds with exactly two decimals.")},
    {"name": "repair_requests", "reference": ref_repairs, "gen": gen_repairs, "description": (
        "Summarise repair requests from tenants. The requests input is a JSON array of objects with keys 'flat' "
        "and 'text'; decide from each text how urgent the repair is, as exactly one of 'emergency', 'routine' or "
        "'cosmetic'. The busiest flat has the most requests of any kind, the alphabetically first on a tie. Return "
        "the text '<e> emergency in <flats> | <r> routine | <c> cosmetic | busiest <flat>', where the flats are "
        "those with an emergency, each once, in alphabetical order separated by ', ', or 'none'.")},
    {"name": "party_replies", "reference": ref_replies, "gen": gen_replies, "description": (
        "Count party replies. The replies input is a JSON array of objects with keys 'name', 'guests' (people they "
        "would bring) and 'text'; decide from each text the answer, as exactly one of 'yes', 'maybe' or 'no'. Coming "
        "counts each yes and its guests. The estimate is coming plus half of the maybes with their guests, rounded "
        "up to a whole person. Return the text '<y> yes, <m> maybe, <n> no | coming <c> | estimate <e>', where y, "
        "m and n count replies.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT
    _shape["family"] = FAMILY[_shape["name"]]
    if _shape["name"] in ONE:
        _shape["reading"] = ONE[_shape["name"]]
    else:
        _list, _field, _label, _values = MANY[_shape["name"]]
        _shape["reading"] = (_list, _label, _values)
        _shape["item_field"] = _field

# Hand-worked cases: every expected string below was computed by hand, not by the reference.
TESTS = {
    "parcel_postage": [
        # bases 85, 155, 240, 240+75*ceil(1/500)=315; tracked adds 120 each: 205+275+360+435 = 1275
        ({"parcels": [{"id": "A", "grams": 100}, {"id": "B", "grams": 101}, {"id": "C", "grams": 1000},
                      {"id": "D", "grams": 1001}]}, {"service": "tracked"},
         "tracked: total 12.75 | 4 parcels | heaviest D"),
        # A: 240+75*1 = 315, x1.5 = 472.5 -> 473; B: 85 x1.5 = 127.5 -> 128; 601
        ({"parcels": [{"id": "A", "grams": 1500}, {"id": "B", "grams": 90}]}, {"service": "express"},
         "express: total 6.01 | 2 parcels | heaviest A"),
        # tie on grams: first in list
        ({"parcels": [{"id": "X", "grams": 500}, {"id": "Y", "grams": 500}]}, {"service": "standard"},
         "standard: total 3.10 | 2 parcels | heaviest X"),
    ],
    "room_booking": [
        # rates tie 18.50 (Elm, Ash), seats tie 12: name Ash; 1850 * 3 = 5550
        ({"rooms": [{"name": "Oak", "seats": 10, "rate": "20.00", "music": False},
                    {"name": "Elm", "seats": 12, "rate": "18.50", "music": True},
                    {"name": "Ash", "seats": 12, "rate": "18.50", "music": False},
                    {"name": "Yew", "seats": 30, "rate": "40.00", "music": True}],
          "attendees": 10, "hours": 3}, {"event": "meeting"}, "meeting: Ash 55.50"),
        # workshop needs 10 + 2 = 12: still Ash
        ({"rooms": [{"name": "Oak", "seats": 10, "rate": "20.00", "music": False},
                    {"name": "Elm", "seats": 12, "rate": "18.50", "music": True},
                    {"name": "Ash", "seats": 12, "rate": "18.50", "music": False},
                    {"name": "Yew", "seats": 30, "rate": "40.00", "music": True}],
          "attendees": 10, "hours": 3}, {"event": "workshop"}, "workshop: Ash 55.50"),
        # party needs music: Elm; 5550 * 1.1 = 6105
        ({"rooms": [{"name": "Oak", "seats": 10, "rate": "20.00", "music": False},
                    {"name": "Elm", "seats": 12, "rate": "18.50", "music": True},
                    {"name": "Ash", "seats": 12, "rate": "18.50", "music": False},
                    {"name": "Yew", "seats": 30, "rate": "40.00", "music": True}],
          "attendees": 10, "hours": 3}, {"event": "party"}, "party: Elm 61.05"),
        # 1825 * 1.1 = 2007.5 -> 2008
        ({"rooms": [{"name": "Hall", "seats": 50, "rate": "18.25", "music": True}], "attendees": 40, "hours": 1},
         {"event": "party"}, "party: Hall 20.08"),
        # workshop of 11 needs 11 + 3 = 14 seats; only 12 available
        ({"rooms": [{"name": "Oak", "seats": 12, "rate": "10.00", "music": False}], "attendees": 11, "hours": 2},
         {"event": "workshop"}, "workshop: none"),
    ],
    "tip_split": [
        # 3000 + 375 = 3375; /4 = 843.75 -> 844; 3376 - 3375 = 1
        ({"items": ["10.00", "20.00"], "diners": 4}, {"service": "good"}, "total 33.75 | each 8.44 | extra 0.01"),
        # 1234 * 0.15 = 185.1 -> 185; 1419 / 3 = 473
        ({"items": ["12.34"], "diners": 3}, {"service": "excellent"}, "total 14.19 | each 4.73 | extra 0.00"),
        # 4 * 0.125 = 0.5 -> 1 (half up); 5 / 2 = 2.5 -> 3; extra 1
        ({"items": ["0.04"], "diners": 2}, {"service": "good"}, "total 0.05 | each 0.03 | extra 0.01"),
        ({"items": ["7.00", "3.01"], "diners": 1}, {"service": "poor"}, "total 10.01 | each 10.01 | extra 0.00"),
    ],
    "library_fines": [
        # 24 days * 25 = 600 -> cap 500; 15 * 25 = 375; 5 * 25 = 125; 1000
        ({"loans": [{"title": "Atlas", "due": "2026-12-01"}, {"title": "Bees", "due": "2026-12-10"},
                    {"title": "Clay", "due": "2026-12-20"}], "today": "2026-12-25"}, {"member": "adult"},
         "adult: fines 10.00 | 3 overdue | most overdue Atlas"),
        ({"loans": [{"title": "Atlas", "due": "2026-12-01"}, {"title": "Bees", "due": "2026-12-10"},
                    {"title": "Clay", "due": "2026-12-20"}], "today": "2026-12-25"}, {"member": "child"},
         "child: fines 0.00 | 3 overdue | most overdue Atlas"),
        # due today is not overdue; 2 days * 10 each; tie: first in list
        ({"loans": [{"title": "Dune", "due": "2026-12-20"}, {"title": "Emma", "due": "2026-12-18"},
                    {"title": "Fog", "due": "2026-12-18"}], "today": "2026-12-20"}, {"member": "senior"},
         "senior: fines 0.40 | 2 overdue | most overdue Emma"),
        ({"loans": [{"title": "Gale", "due": "2026-12-05"}], "today": "2026-12-01"}, {"member": "adult"},
         "adult: fines 0.00 | 0 overdue | most overdue none"),
    ],
    "ticket_triage": [
        # now 11:00: T1 bug 120 > 60 breached; T2 billing 90; T3 account 60; T4 bug 1
        ({"tickets": [{"id": "T1", "opened": "09:00", "text": ""}, {"id": "T2", "opened": "09:30", "text": ""},
                      {"id": "T3", "opened": "10:00", "text": ""}, {"id": "T4", "opened": "10:59", "text": ""}],
          "now": "11:00"}, {"category": ["bug", "billing", "account", "bug"]},
         "billing 1, bug 2, account 1 | breached T1"),
        # exactly 120 is not a breach; 121 is
        ({"tickets": [{"id": "T5", "opened": "07:00", "text": ""}, {"id": "T6", "opened": "07:01", "text": ""}],
          "now": "09:01"}, {"category": ["account", "account"]}, "billing 0, bug 0, account 2 | breached T5"),
    ],
    "shopping_receipt": [
        # food 500 + 600 + 500 = 1600; household 399*3 = 1197; alcohol 1800; card 2797; treat: 6.00 only
        ({"lines": [{"price": "2.50", "qty": 2, "text": ""}, {"price": "6.00", "qty": 1, "text": ""},
                    {"price": "5.00", "qty": 1, "text": ""}, {"price": "3.99", "qty": 3, "text": ""},
                    {"price": "9.00", "qty": 2, "text": ""}]},
         {"kind": ["food", "food", "food", "household", "alcohol"]},
         "food 16.00 | household 11.97 | alcohol 18.00 | card 27.97 | 1 treats"),
    ],
    "repair_requests": [
        # 1A and 2B both have 2 requests: 1A first alphabetically
        ({"requests": [{"flat": "2B", "text": ""}, {"flat": "1A", "text": ""}, {"flat": "2B", "text": ""},
                       {"flat": "1A", "text": ""}, {"flat": "3C", "text": ""}]},
         {"urgency": ["emergency", "routine", "cosmetic", "emergency", "routine"]},
         "2 emergency in 1A, 2B | 2 routine | 1 cosmetic | busiest 1A"),
        ({"requests": [{"flat": "4D", "text": ""}]}, {"urgency": ["cosmetic"]},
         "0 emergency in none | 0 routine | 1 cosmetic | busiest 4D"),
    ],
    "party_replies": [
        # coming 1 + 3 = 4; maybes 2 + 1 = 3 -> half 1.5 -> 2; estimate 6
        ({"replies": [{"name": "A", "guests": 0, "text": ""}, {"name": "B", "guests": 2, "text": ""},
                      {"name": "C", "guests": 1, "text": ""}, {"name": "D", "guests": 0, "text": ""},
                      {"name": "E", "guests": 3, "text": ""}]},
         {"answer": ["yes", "yes", "maybe", "maybe", "no"]}, "2 yes, 2 maybe, 1 no | coming 4 | estimate 6"),
        ({"replies": [{"name": "F", "guests": 0, "text": ""}]}, {"answer": ["maybe"]},
         "0 yes, 1 maybe, 0 no | coming 0 | estimate 1"),
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


def label_values(shape):
    return shape["reading"][2]


def placeholder_prose():
    return {s["name"]: {label: [f"placeholder {label} {i}" for i in range(3)] for label in label_values(s)}
            for s in SHAPES}


def self_verify(prose=None):
    import fast_path_jobs_bench_v1
    import fast_path_jobs_bench_v2_large
    import fast_path_planned_bench_v2
    import fast_path_planned_bench_v3
    import fast_path_planned_bench_v4
    import fast_path_planned_bench_v5
    import fast_path_planned_bench_v6

    earlier = {s["name"] for module in (fast_path_jobs_bench_v1, fast_path_jobs_bench_v2_large,
                                        fast_path_planned_bench_v2, fast_path_planned_bench_v3,
                                        fast_path_planned_bench_v4, fast_path_planned_bench_v5,
                                        fast_path_planned_bench_v6)
               for s in module.SHAPES}
    names = [s["name"] for s in SHAPES]
    assert len(names) == len(set(names)) and not set(names) & earlier, "shape names must be new"
    assert sorted(FAMILY.values()) == ["many"] * 4 + ["one"] * 4
    if prose is None:
        prose = load_prose() if PROSE_PATH.exists() else placeholder_prose()
    for shape in SHAPES:
        for inputs, labels, expected in TESTS[shape["name"]]:
            got = shape["reference"](inputs, labels)
            assert got == expected, f"{shape['name']}: {got!r} != {expected!r}"
        values = label_values(shape)
        assert all(f"'{v}'" in shape["description"] for v in values), f"{shape['name']}: label missing"
        assert set(prose[shape["name"]]) == set(values) and all(prose[shape["name"]][v] for v in values)
        instances = stream(shape, prose=prose)
        assert [i for i, _ in instances] == [i for i, _ in stream(shape, prose=prose)], "not reproducible"
        for inputs, labels in instances:
            for name in inputs:
                assert name in shape["description"], f"{shape['name']}: input {name} not named"
            if shape["family"] == "many":
                assert len(labels[shape["reading"][1]]) == len(inputs[shape["reading"][0]])
        outputs = gold(shape, instances)
        assert len({o[OUTPUT] for o in outputs}) > 5, f"{shape['name']}: answers too uniform"
    print(f"self_verify OK: {len(SHAPES)} job shapes ({len(ONE)} one-reading, {len(MANY)} many-reading), "
          f"{STREAM_LENGTH} jobs each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_planned_bench_v7.py sha256:", bench_sha256())
