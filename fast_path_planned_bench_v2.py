"""Fresh plain-language jobs for the planned-jobs experiment V2.

Seven new job shapes, none used in any earlier run. Each is a plain-language
description plus inputs: a long structured record list and one prose field
whose label (tone, topic, language, intent or kind) is planted by the
generator. The router gets no plan.

Gold is by construction: ``reference(inputs, labels)`` computes the answer from
the records and the planted label. Each reference is qualified by hand-worked
tests below.

Run ``python fast_path_planned_bench_v2.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import json
import random

from fast_path_jobs_bench_v1 import INTENT, KIND, LANGUAGE, TONE, TOPIC

STREAM_SEED = 20261120
STREAM_LENGTH = 15
OUTPUT = "result"

CATEGORIES = ["lodging", "meals", "supplies", "training", "travel"]
PLACES = ["Lyon", "Paris", "Turin", "Milan", "Porto", "Madrid", "Hamburg", "Vienna", "Ghent"]
STATUSES = ["in_transit", "in_transit", "at_depot", "delayed", "out_for_delivery"]
STAFF = ["Ana", "Bram", "Chen", "Dita", "Emre", "Farah"]
PROJECTS = ["alpha", "beta", "gamma", "delta"]
PAYEES = ["Rent", "Salary", "Coffee", "Grocer", "Fuel", "Refund", "Insurance", "Phone", "Books", "Taxi"]
ARTISTS = ["Ana Lua", "Key Lime", "Old Pines", "Nora Vale", "The Quays", "Milo Fenn"]
TITLES = ["Blue Morning", "Night Drive", "Slow River", "Glass Town", "North Wind", "Paper Moon",
          "Low Tide", "Red Kite", "Quiet Hours", "Salt Road", "Late Train", "Open Field",
          "Cold Light", "Long Way", "Iron Gate", "Soft Rain", "Wild Fern", "High Noon"]
LANG_CODE = {"english": "EN", "french": "FR", "spanish": "ES", "german": "DE"}
HEADING = {"english": "Playlist", "french": "Liste", "spanish": "Lista", "german": "Wiedergabeliste"}
ZONE = {"animal": "Z1", "tool": "Z2", "food": "Z3"}


def _pick(r, table):
    label = r.choice(sorted(table))
    return label, r.choice(table[label])


def _cents(text):
    sign = -1 if text.startswith("-") else 1
    whole, frac = text.lstrip("+-").split(".")
    return sign * (int(whole) * 100 + int(frac))


def _euros(cents):
    return ("-" if cents < 0 else "") + f"{abs(cents) // 100}.{abs(cents) % 100:02d}"


def _top(totals):
    return sorted(totals, key=lambda k: (-totals[k], k))[0] if totals else "none"


def _lines(text):
    return [line for line in text.split("\n") if line.strip()]


# ---- references --------------------------------------------------------

def ref_expenses(inputs, labels):
    rows = [[p.strip() for p in line.split("|")] for line in _lines(inputs["claims"])]
    totals, over, total = {}, 0, 0
    for _, category, amount in rows:
        cents = _cents(amount)
        total += cents
        totals[category] = totals.get(category, 0) + cents
        over += cents > 15000
    return (f"{LANG_CODE[labels['language']]} | {len(rows)} claims | total {_euros(total)} EUR"
            f" | top {_top(totals)} | {over} over limit")


def ref_shipment(inputs, labels):
    rows = [[p.strip() for p in line.split("|")] for line in _lines(inputs["events"])]

    def minutes(stamp):
        date, clock = stamp.split()
        _, _, day = date.split("-")
        hour, minute = clock.split(":")
        return int(day) * 1440 + int(hour) * 60 + int(minute)

    hours = (minutes(rows[-1][0]) - minutes(rows[0][0])) // 60
    delivered = any(status == "delivered" for _, _, status in rows)
    intent = labels["intent"]
    if delivered and intent == "order_status":
        action = "close"
    elif intent in ("refund", "cancel"):
        action = "review"
    else:
        action = "update"
    delays = sum(status == "delayed" for _, _, status in rows)
    return f"{action}: {hours}h, last at {rows[-1][1]}, {delays} delays"


def ref_survey(inputs, labels):
    answers = [[int(x) for x in line.split(":")[1].split(",")] for line in _lines(inputs["responses"])]
    n = len(answers)
    averages = []
    for q in range(3):
        total = sum(a[q] for a in answers)
        tenths = (20 * total + n) // (2 * n)
        averages.append(f"{tenths // 10}.{tenths % 10}")
    net = sum(sum(a) >= 13 for a in answers) - sum(sum(a) <= 8 for a in answers)
    text = f"q1 {averages[0]}, q2 {averages[1]}, q3 {averages[2]} | net {net} | {labels['tone']}"
    return text + (" - follow up" if labels["tone"] == "negative" or net < 0 else "")


def ref_timesheet(inputs, labels):
    rows = [[p.strip() for p in line.split("|")] for line in _lines(inputs["entries"])]
    per_person, per_day, projects, total = {}, {}, set(), 0
    for name, date, hours, project in rows:
        tenths = round(float(hours) * 10)
        total += tenths
        per_person[name] = per_person.get(name, 0) + tenths
        per_day[(name, date)] = per_day.get((name, date), 0) + tenths
        projects.add(project)
    overtime = sum(t > 80 for t in per_day.values())
    return (f"{labels['topic']}: {total // 10}.{total % 10}h total, top {_top(per_person)}, "
            f"{overtime} overtime days, {len(projects)} projects")


def ref_bank(inputs, labels):
    rows = [[p.strip() for p in line.split("|")] for line in _lines(inputs["rows"])]
    balance = _cents(inputs["opening"])
    worst, worst_name, credits = 0, "none", 0
    for _, description, amount in rows:
        cents = _cents(amount)
        balance += cents
        credits += cents > 0
        if cents < worst:
            worst, worst_name = cents, description
    text = f"closing {_euros(balance)} EUR | largest debit {worst_name} | {credits} credits"
    return text + (" | escalate" if labels["tone"] == "negative" and balance < 0 else "")


def ref_playlist(inputs, labels):
    tracks = []
    for line in _lines(inputs["tracks"]):
        artist, rest = line.split(" - ", 1)
        title, length = rest.rsplit(" (", 1)
        m, s = length.rstrip(")").split(":")
        tracks.append((artist, title, int(m) * 60 + int(s)))
    total = sum(t[2] for t in tracks)
    longest = max(tracks, key=lambda t: t[2])[1] if tracks else "none"
    duration = f"{total // 3600}:{total // 60 % 60:02d}:{total % 60:02d}"
    return (f"{HEADING[labels['language']]}: {len(tracks)} tracks, {duration}, longest {longest}, "
            f"{len({t[0] for t in tracks})} artists")


def ref_picks(inputs, labels):
    rows = [[p.strip() for p in line.split("|")] for line in _lines(inputs["picks"])]
    per_bin = {}
    for bin_, _, qty in rows:
        per_bin[bin_] = per_bin.get(bin_, 0) + int(qty)
    total = sum(per_bin.values())
    return f"{ZONE[labels['kind']]} | {total} units | {len(per_bin)} bins | busiest {_top(per_bin)}"


# ---- generators --------------------------------------------------------

def gen_expenses(r):
    language, note = _pick(r, LANGUAGE)
    lines = [f"2026-11-{r.randint(1, 28):02d} | {r.choice(CATEGORIES)} | "
             f"{r.choice([r.randint(5, 140), r.randint(5, 140), r.randint(140, 400)])}.{r.choice([0, 50, 99, 5]):02d}"
             for _ in range(r.randint(10, 18))]
    return {"claims": "\n".join(lines), "cover_note": note}, {"language": language}


def gen_shipment(r):
    intent, message = _pick(r, INTENT)
    t = r.randint(1, 8) * 1440 + r.randint(6, 18) * 60 + r.randint(0, 59)
    lines = []
    count = r.randint(8, 14)
    delivered = r.random() < 0.5
    for i in range(count):
        if i == 0:
            status = "picked_up"
        elif i == count - 1 and delivered:
            status = "delivered"
        else:
            status = r.choice(STATUSES)
        lines.append(f"2026-11-{t // 1440:02d} {t // 60 % 24:02d}:{t % 60:02d} | {r.choice(PLACES)} | {status}")
        t += r.randint(30, 1500)
    return {"events": "\n".join(lines), "message": message}, {"intent": intent}


def gen_survey(r):
    tone, comment = _pick(r, TONE)
    lines = [f"R{i + 1:02d}: {r.randint(1, 5)}, {r.randint(1, 5)}, {r.randint(1, 5)}"
             for i in range(r.randint(10, 20))]
    return {"responses": "\n".join(lines), "comment": comment}, {"tone": tone}


def gen_timesheet(r):
    topic, note = _pick(r, TOPIC)
    people = r.sample(STAFF, r.randint(3, 5))
    lines = [f"{r.choice(people)} | 2026-11-{r.randint(16, 20):02d} | {r.randint(1, 16) / 2:.1f} | "
             f"{r.choice(PROJECTS)}" for _ in range(r.randint(12, 20))]
    return {"entries": "\n".join(lines), "manager_note": note}, {"topic": topic}


def gen_bank(r):
    tone, note = _pick(r, TONE)
    lines = []
    for _ in range(r.randint(10, 16)):
        amount = r.randint(1, 900) * 100 + r.choice([0, 5, 20, 99])
        sign = "+" if r.random() < 0.35 else "-"
        lines.append(f"2026-11-{r.randint(1, 28):02d} | {r.choice(PAYEES)} | {sign}{_euros(amount)}")
    opening = _euros(r.randint(0, 3000) * 100 + r.choice([0, 15, 50]))
    return {"opening": opening, "rows": "\n".join(lines), "dispute_note": note}, {"tone": tone}


def gen_playlist(r):
    language, note = _pick(r, LANGUAGE)
    lines = [f"{r.choice(ARTISTS)} - {title} ({r.randint(1, 7)}:{r.randint(0, 59):02d})"
             for title in r.sample(TITLES, r.randint(10, 16))]
    return {"tracks": "\n".join(lines), "note": note}, {"language": language}


def gen_picks(r):
    kind = r.choice(sorted(KIND))
    bins = [f"{r.choice('ABCD')}-{r.randint(1, 30):02d}" for _ in range(r.randint(4, 7))]
    lines = [f"{r.choice(bins)} | {r.randint(4000, 4099)} | {r.randint(1, 12)}" for _ in range(r.randint(12, 22))]
    return {"picks": "\n".join(lines), "focus_item": r.choice(KIND[kind])}, {"kind": kind}


SHAPES = [
    {"name": "expense_claims", "reference": ref_expenses, "gen": gen_expenses, "description": (
        "Review a set of expense claims. Each line of the claims input has the form "
        "'YYYY-MM-DD | category | amount', with the amount in euros with two decimals. Identify the "
        "language of the cover_note as exactly one of 'english', 'french', 'spanish' or 'german'; the "
        "language code for those is 'EN', 'FR', 'ES' and 'DE'. The total is the sum of all amounts. The "
        "top category is the category with the greatest summed amount, the alphabetically first on a tie, "
        "or 'none' if there are no claims. A claim is over the limit when its amount is more than 150.00. "
        "Return the text '<code> | <n> claims | total <total> EUR | top <category> | <k> over limit', where "
        "n is the number of claims, total is written with exactly two decimals and k is the number of "
        "claims over the limit.")},
    {"name": "shipment_tracking", "reference": ref_shipment, "gen": gen_shipment, "description": (
        "Summarise a shipment's tracking events. Each line of the events input has the form "
        "'YYYY-MM-DD HH:MM | location | status', in time order, all in the same month. Classify what the "
        "customer wants in the message as exactly one of 'refund', 'cancel', 'change_address' or "
        "'order_status'. The hours in transit are the whole hours from the first event's time to the last "
        "event's time, rounded down. The shipment is delivered if any event's status is 'delivered'. The "
        "action is 'close' if it is delivered and the intent is 'order_status'; otherwise 'review' if the "
        "intent is 'refund' or 'cancel'; otherwise 'update'. Count the events whose status is 'delayed'. "
        "Return the text '<action>: <hours>h, last at <location>, <d> delays', where location is the last "
        "event's location and d is the number of delayed events.")},
    {"name": "survey_scores", "reference": ref_survey, "gen": gen_survey, "description": (
        "Summarise survey responses. Each line of the responses input has the form 'Rnn: a, b, c', the "
        "respondent's answers to questions 1, 2 and 3, each from 1 to 5. Classify the tone of the comment "
        "as exactly one of 'positive', 'negative' or 'neutral'. For each question, compute the average "
        "answer rounded to one decimal place with halves rounded up, and write it with exactly one "
        "decimal. A promoter is a respondent whose three answers add up to 13 or more; a detractor's add "
        "up to 8 or less. The net score is the number of promoters minus the number of detractors. Return "
        "the text 'q1 <avg1>, q2 <avg2>, q3 <avg3> | net <net> | <tone>', followed by ' - follow up' if "
        "the tone is negative or the net score is below zero.")},
    {"name": "timesheet", "reference": ref_timesheet, "gen": gen_timesheet, "description": (
        "Summarise a timesheet. Each line of the entries input has the form "
        "'Name | YYYY-MM-DD | hours | project', with hours in steps of 0.5. Classify what the manager_note "
        "is about as exactly one of 'billing', 'technical', 'account' or 'shipping'. The total is the sum "
        "of all hours, written with exactly one decimal. The top person has the most hours in total, the "
        "alphabetically first on a tie, or 'none'. An overtime day is a person and a date for which that "
        "person's hours on that date add up to more than 8. Count the distinct projects. Return the text "
        "'<topic>: <total>h total, top <person>, <o> overtime days, <p> projects'.")},
    {"name": "bank_statement", "reference": ref_bank, "gen": gen_bank, "description": (
        "Reconcile a bank statement. The opening input is the opening balance in euros as text with two "
        "decimals. Each line of the rows input has the form 'YYYY-MM-DD | description | amount', where the "
        "amount is signed, such as '+12.34' or '-45.00'. Classify the tone of the dispute_note as exactly "
        "one of 'positive', 'negative' or 'neutral'. The closing balance is the opening balance plus every "
        "amount. The largest debit is the description of the row with the most negative amount, the "
        "earliest such row on a tie, or 'none' if no amount is negative. A credit is a row with a positive "
        "amount. Return the text 'closing <balance> EUR | largest debit <description> | <c> credits', with "
        "the balance written with exactly two decimals and a leading '-' if it is negative, followed by "
        "' | escalate' if the tone is negative and the closing balance is below zero.")},
    {"name": "playlist", "reference": ref_playlist, "gen": gen_playlist, "description": (
        "Summarise a playlist. Each line of the tracks input has the form 'Artist - Title (m:ss)'. "
        "Identify the language of the note as exactly one of 'english', 'french', 'spanish' or 'german'; "
        "the heading for those is 'Playlist', 'Liste', 'Lista' and 'Wiedergabeliste'. The total duration "
        "is the sum of all track lengths, written as H:MM:SS with the hours not padded. The longest track "
        "is the title of the track with the greatest length, the earliest such track on a tie. Count the "
        "distinct artists. Return the text '<heading>: <n> tracks, <duration>, longest <title>, "
        "<a> artists', where n is the number of tracks.")},
    {"name": "pick_list", "reference": ref_picks, "gen": gen_picks, "description": (
        "Summarise a warehouse pick list. Each line of the picks input has the form 'bin | sku | qty', "
        "such as 'B-12 | 4021 | 3'. Classify the thing named by the focus_item as exactly one of "
        "'animal', 'tool' or 'food'; its zone is 'Z1' for animal, 'Z2' for tool and 'Z3' for food. The "
        "total is the sum of all quantities. Count the distinct bins. The busiest bin has the largest "
        "summed quantity, the alphabetically first on a tie, or 'none' if there are no picks. Return the "
        "text '<zone> | <total> units | <b> bins | busiest <bin>'.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT

TESTS = {
    "expense_claims": [
        ({"claims": "2026-11-01 | travel | 200.00\n2026-11-02 | meals | 30.50\n2026-11-03 | travel | 10.00"},
         {"language": "french"}, "FR | 3 claims | total 240.50 EUR | top travel | 1 over limit"),
        ({"claims": "2026-11-01 | meals | 50.00\n2026-11-01 | lodging | 50.00\n2026-11-04 | travel | 150.00"},
         {"language": "german"}, "DE | 3 claims | total 250.00 EUR | top travel | 0 over limit"),
        ({"claims": "2026-11-01 | meals | 50.00\n2026-11-01 | lodging | 50.00"},
         {"language": "english"}, "EN | 2 claims | total 100.00 EUR | top lodging | 0 over limit"),
    ],
    "shipment_tracking": [
        ({"events": "2026-11-01 08:00 | Lyon | picked_up\n2026-11-02 09:30 | Paris | delayed\n"
                    "2026-11-03 07:59 | Paris | delivered"},
         {"intent": "order_status"}, "close: 47h, last at Paris, 1 delays"),
        ({"events": "2026-11-05 10:00 | Turin | picked_up"}, {"intent": "refund"},
         "review: 0h, last at Turin, 0 delays"),
        ({"events": "2026-11-05 10:00 | Turin | picked_up\n2026-11-05 12:30 | Milan | delayed\n"
                    "2026-11-06 09:00 | Milan | delayed"},
         {"intent": "order_status"}, "update: 23h, last at Milan, 2 delays"),
    ],
    "survey_scores": [
        ({"responses": "R01: 5, 5, 4\nR02: 1, 2, 3\nR03: 3, 3, 3"}, {"tone": "neutral"},
         "q1 3.0, q2 3.3, q3 3.3 | net 0 | neutral"),
        ({"responses": "R01: 4, 1, 1\nR02: 3, 1, 1\nR03: 3, 1, 1\nR04: 3, 1, 1"}, {"tone": "positive"},
         "q1 3.3, q2 1.0, q3 1.0 | net -4 | positive - follow up"),
        ({"responses": "R01: 5, 5, 5\nR02: 4, 4, 5"}, {"tone": "negative"},
         "q1 4.5, q2 4.5, q3 5.0 | net 2 | negative - follow up"),
    ],
    "timesheet": [
        ({"entries": "Ana | 2026-11-02 | 6.0 | alpha\nAna | 2026-11-02 | 3.0 | beta\n"
                     "Bram | 2026-11-02 | 8.0 | alpha\nBram | 2026-11-03 | 1.5 | alpha"},
         {"topic": "technical"}, "technical: 18.5h total, top Bram, 1 overtime days, 2 projects"),
        ({"entries": "Chen | 2026-11-02 | 4.0 | gamma\nAna | 2026-11-03 | 4.0 | gamma"},
         {"topic": "billing"}, "billing: 8.0h total, top Ana, 0 overtime days, 1 projects"),
    ],
    "bank_statement": [
        ({"opening": "100.00", "rows": "2026-11-01 | Rent | -150.00\n2026-11-02 | Salary | +20.50\n"
                                       "2026-11-03 | Coffee | -3.20"},
         {"tone": "negative"}, "closing -32.70 EUR | largest debit Rent | 1 credits | escalate"),
        ({"opening": "0.05", "rows": "2026-11-01 | Refund | +5.00"}, {"tone": "neutral"},
         "closing 5.05 EUR | largest debit none | 1 credits"),
        ({"opening": "10.00", "rows": "2026-11-01 | Fuel | -10.50\n2026-11-02 | Taxi | -10.50"},
         {"tone": "positive"}, "closing -11.00 EUR | largest debit Fuel | 0 credits"),
        ({"opening": "1.00", "rows": "2026-11-01 | Fuel | -1.50"}, {"tone": "negative"},
         "closing -0.50 EUR | largest debit Fuel | 0 credits | escalate"),
    ],
    "playlist": [
        ({"tracks": "Ana Lua - Blue Morning (3:05)\nKey Lime - Night Drive (4:10)\nAna Lua - Slow River (4:10)"},
         {"language": "spanish"}, "Lista: 3 tracks, 0:11:25, longest Night Drive, 2 artists"),
        ({"tracks": "Old Pines - Long Way (59:59)\nOld Pines - Low Tide (0:02)"}, {"language": "german"},
         "Wiedergabeliste: 2 tracks, 1:00:01, longest Long Way, 1 artists"),
    ],
    "pick_list": [
        ({"picks": "B-12 | 4021 | 3\nA-07 | 5000 | 2\nB-12 | 4022 | 1\nA-07 | 4021 | 2"},
         {"kind": "tool"}, "Z2 | 8 units | 2 bins | busiest A-07"),
        ({"picks": "C-01 | 4000 | 5"}, {"kind": "food"}, "Z3 | 5 units | 1 bins | busiest C-01"),
    ],
}


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH):
    rng = random.Random(f"{seed}:{shape['name']}")
    seen, out = set(), []
    for _ in range(length * 200):
        inputs, labels = shape["gen"](rng)
        key = json.dumps(inputs, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append((inputs, labels))
            if len(out) == length:
                return out
    raise ValueError(f"{shape['name']}: generator cannot supply {length} distinct inputs")


def gold(shape, instances):
    return [{OUTPUT: shape["reference"](inputs, labels)} for inputs, labels in instances]


def self_verify():
    import fast_path_jobs_bench_v1
    import fast_path_jobs_bench_v2_large

    earlier = {s["name"] for s in fast_path_jobs_bench_v1.SHAPES + fast_path_jobs_bench_v2_large.SHAPES}
    names = [s["name"] for s in SHAPES]
    assert len(names) == len(set(names)) and not set(names) & earlier, "shape names must be new"
    for shape in SHAPES:
        for inputs, labels, expected in TESTS[shape["name"]]:
            got = shape["reference"](inputs, labels)
            assert got == expected, f"{shape['name']}: {got!r} != {expected!r}"
        instances = stream(shape)
        assert [i for i, _ in instances] == [i for i, _ in stream(shape)], "stream not reproducible"
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
    print("fast_path_planned_bench_v2.py sha256:", bench_sha256())
