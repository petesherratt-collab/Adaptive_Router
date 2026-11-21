"""Hard jobs (V6): many readings per job, mixed into the logic.

Eight new job shapes, none used before. In every shape the job is a list of
records and each record carries its own short text that needs reading (a
review's topic, an incident note's severity, an expense's category, ...), so a
job holds 4 to 12 readings whose labels feed counts, filters, rankings and
rules. These are the jobs most likely to defeat writing the whole job once,
and the only kind where step-by-step planning might still win.

Gold is by construction: ``reference(inputs, labels)`` takes the planted label
of every item. The texts come from ``fast_path_planned_bench_v6_prose.json``,
written by a model outside the race roster after this file was frozen.

Run ``python fast_path_planned_bench_v6.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import json
from pathlib import Path
import random

from fast_path_planned_bench_v3 import _cents, _minutes, _money, load_prose as _load

STREAM_SEED = 20261120
STREAM_LENGTH = 30
OUTPUT = "result"
PROSE_PATH = Path(__file__).resolve().parent / "fast_path_planned_bench_v6_prose.json"

# shape -> (list input, text field, label name, labels)
READINGS = {
    "review_digest": ("reviews", "text", "topic", ["price", "quality", "delivery", "service"]),
    "incident_log": ("entries", "note", "severity", ["low", "medium", "high"]),
    "expense_lines": ("lines", "description", "category", ["travel", "meals", "equipment", "other"]),
    "survey_comments": ("responses", "comment", "sentiment", ["positive", "negative", "neutral"]),
    "menu_check": ("dishes", "description", "allergen", ["nuts", "dairy", "gluten", "none"]),
    "applicant_screen": ("applicants", "letter", "role", ["engineering", "design", "sales"]),
    "delivery_feedback": ("drops", "note", "outcome", ["delivered", "missed", "damaged"]),
    "listing_filter": ("listings", "blurb", "outdoor", ["garden", "balcony", "none"]),
}

DRIVERS = ["Ade", "Bex", "Cy", "Dru", "Em"]
NAMES = ["Asha", "Bruno", "Chloe", "Dev", "Eun", "Farid", "Gemma", "Hugo", "Isla", "Jai", "Kofi", "Lena"]
DISHES = ["Bake", "Bisque", "Curry", "Flan", "Gratin", "Pilaf", "Ragu", "Risotto", "Salad", "Stew",
          "Tagine", "Tart"]


def load_prose(path=PROSE_PATH):
    return _load(path)


def _half_up(numerator, denominator):
    """Nearest integer, halves toward positive infinity (any sign)."""
    return (2 * numerator + denominator) // (2 * denominator)


# ---- references --------------------------------------------------------

def ref_reviews(inputs, labels):
    topics = READINGS["review_digest"][3]
    counts = {t: 0 for t in topics}
    stars = {t: [] for t in topics}
    for review, topic in zip(inputs["reviews"], labels["topic"]):
        counts[topic] += 1
        stars[topic].append(review["stars"])
    present = [t for t in topics if stars[t]]
    worst = min(present, key=lambda t: (sum(stars[t]) * 1.0 / len(stars[t]), topics.index(t)))
    # Exact comparison: averages as fractions.
    for t in present:
        if sum(stars[t]) * len(stars[worst]) < sum(stars[worst]) * len(stars[t]):
            worst = t
    quality = "none"
    if stars["quality"]:
        tenths = _half_up(10 * sum(stars["quality"]), len(stars["quality"]))
        quality = f"{tenths // 10}.{tenths % 10}"
    return (", ".join(f"{t} {counts[t]}" for t in topics) + f" | worst {worst} | quality stars {quality}")


def ref_incidents(inputs, labels):
    entries = list(zip(inputs["entries"], labels["severity"]))
    count = {s: sum(sev == s for _, sev in entries) for s in ("high", "medium", "low")}
    mediums = [_minutes(e["time"]) for e, sev in entries if sev == "medium"]
    cluster = any(mediums[i + 2] - mediums[i] <= 60 for i in range(len(mediums) - 2))
    first_high = next((e["time"] for e, sev in entries if sev == "high"), "none")
    escalate = "yes" if count["high"] or cluster else "no"
    return (f"{count['high']} high, {count['medium']} medium, {count['low']} low | escalate {escalate} | "
            f"first high {first_high}")


def ref_expenses(inputs, labels):
    categories = READINGS["expense_lines"][3]
    totals = {c: 0 for c in categories}
    flagged = 0
    for line, category in zip(inputs["lines"], labels["category"]):
        cents = _cents(line["amount"])
        totals[category] += cents
        flagged += (category == "meals" and cents > 5000) or (category == "equipment" and cents > 50000)
    return " | ".join(f"{c} {_money(totals[c])}" for c in categories) + f" | {flagged} flagged"


def ref_survey(inputs, labels):
    rows = list(zip(inputs["responses"], labels["sentiment"]))
    n = len(rows)
    promoters = sum(r["rating"] >= 9 for r, _ in rows)
    detractors = sum(r["rating"] <= 6 for r, _ in rows)
    nps = _half_up(100 * (promoters - detractors), n)
    mismatches = sum((r["rating"] >= 9 and s == "negative") or (r["rating"] <= 6 and s == "positive")
                     for r, s in rows)
    positive = sum(s == "positive" for _, s in rows)
    negative = sum(s == "negative" for _, s in rows)
    return f"nps {nps} | {positive} positive, {negative} negative | {mismatches} mismatches"


def ref_menu(inputs, labels):
    rows = list(zip(inputs["dishes"], labels["allergen"]))
    safe = [d for d, a in rows if a != inputs["allergy"]]
    unsafe = [d["name"] for d, a in rows if a == inputs["allergy"]]
    cheapest = (sorted(safe, key=lambda d: (_cents(d["price"]), d["name"]))[0]["name"] if safe else "none")
    return (f"{len(safe)} of {len(rows)} safe | cheapest safe {cheapest} | avoid "
            f"{', '.join(unsafe) if unsafe else 'none'}")


def ref_applicants(inputs, labels):
    rows = list(zip(inputs["applicants"], labels["role"]))
    picks = sorted((a for a, r in rows if r == inputs["role"] and a["years"] >= 3),
                   key=lambda a: (-a["years"], a["name"]))
    others = sum(r != inputs["role"] for _, r in rows)
    return (f"{inputs['role']}: shortlist {', '.join(a['name'] for a in picks) if picks else 'none'} | "
            f"{others} other roles")


def ref_deliveries(inputs, labels):
    points = {}
    count = {"delivered": 0, "missed": 0, "damaged": 0}
    for drop, outcome in zip(inputs["drops"], labels["outcome"]):
        count[outcome] += 1
        score = {"missed": 0, "damaged": -1}.get(outcome, 2 if drop["minutes_late"] <= 10 else 1)
        points[drop["driver"]] = points.get(drop["driver"], 0) + score
    best = sorted(points, key=lambda d: (-points[d], d))[0]
    return (f"{count['delivered']} delivered, {count['missed']} missed, {count['damaged']} damaged | "
            f"best {best} ({points[best]})")


def ref_listings(inputs, labels):
    rows = list(zip(inputs["listings"], labels["outdoor"]))
    matches = sorted((l for l, o in rows if l["price"] <= inputs["budget"] and l["beds"] >= inputs["min_beds"]
                      and o != "none"), key=lambda l: (l["price"], l["id"]))
    gardens = sum(o == "garden" for _, o in rows)
    return (f"{len(matches)} matches: {', '.join(l['id'] for l in matches) if matches else 'none'} | "
            f"gardens {gardens}")


# ---- generators --------------------------------------------------------

def _items(r, prose, shape, count):
    """``count`` (label, text) pairs for a shape's list input."""
    _, _, _, values = READINGS[shape]
    picks = [r.choice(values) for _ in range(count)]
    return picks, [r.choice(prose[shape][label]) for label in picks]


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def gen_reviews(r, prose):
    labels, texts = _items(r, prose, "review_digest", r.randint(4, 10))
    return {"reviews": [{"stars": r.randint(1, 5), "text": t} for t in texts]}, {"topic": labels}


def gen_incidents(r, prose):
    labels, texts = _items(r, prose, "incident_log", r.randint(4, 10))
    t = r.randint(0, 8 * 60)
    entries = []
    for text in texts:
        entries.append({"time": _clock(t), "note": text})
        t += r.choice([5, 15, 20, 30, 45, 60, 90])
    return {"entries": entries}, {"severity": labels}


def gen_expenses(r, prose):
    labels, texts = _items(r, prose, "expense_lines", r.randint(4, 10))
    lines = [{"amount": f"{r.choice([r.randint(5, 49), r.randint(50, 120), r.randint(200, 900), 50, 500])}."
                        f"{r.choice([0, 1, 50, 99]):02d}", "description": t} for t in texts]
    return {"lines": lines}, {"category": labels}


def gen_survey(r, prose):
    labels, texts = _items(r, prose, "survey_comments", r.randint(4, 12))
    return {"responses": [{"rating": r.randint(0, 10), "comment": t} for t in texts]}, {"sentiment": labels}


def gen_menu(r, prose):
    labels, texts = _items(r, prose, "menu_check", r.randint(4, 9))
    names = r.sample(DISHES, len(texts))
    dishes = [{"name": n, "price": f"{r.randint(6, 24)}.{r.choice([0, 50, 95]):02d}", "description": t}
              for n, t in zip(names, texts)]
    return {"dishes": dishes, "allergy": r.choice(["nuts", "dairy", "gluten"])}, {"allergen": labels}


def gen_applicants(r, prose):
    labels, texts = _items(r, prose, "applicant_screen", r.randint(4, 10))
    names = r.sample(NAMES, len(texts))
    applicants = [{"name": n, "years": r.randint(0, 12), "letter": t} for n, t in zip(names, texts)]
    return {"applicants": applicants, "role": r.choice(["engineering", "design", "sales"])}, {"role": labels}


def gen_deliveries(r, prose):
    labels, texts = _items(r, prose, "delivery_feedback", r.randint(5, 12))
    drops = [{"driver": r.choice(DRIVERS), "minutes_late": r.choice([0, 0, 5, 10, 11, 25, 60]), "note": t}
             for t in texts]
    return {"drops": drops}, {"outcome": labels}


def gen_listings(r, prose):
    labels, texts = _items(r, prose, "listing_filter", r.randint(4, 10))
    listings = [{"id": f"P{r.randint(100, 999)}", "price": r.randint(8, 30) * 50, "beds": r.randint(1, 4),
                 "blurb": t} for t in texts]
    return {"listings": listings, "budget": r.randint(10, 26) * 50, "min_beds": r.randint(1, 3)}, \
        {"outdoor": labels}


SHAPES = [
    {"name": "review_digest", "reference": ref_reviews, "gen": gen_reviews, "description": (
        "Digest product reviews. The reviews input is a JSON array of objects with keys 'stars' (1 to 5) "
        "and 'text'. Decide what each review's text is mainly about, as exactly one of 'price', "
        "'quality', 'delivery' or 'service'. Count the reviews per topic. The worst topic is the topic, "
        "among those with at least one review, whose reviews have the lowest average stars, the earlier "
        "in the order price, quality, delivery, service on a tie. The quality stars are the average stars "
        "of the quality reviews rounded to one decimal with halves rounded up, or 'none' if there are "
        "none. Return the text 'price <a>, quality <b>, delivery <c>, service <d> | worst <topic> | "
        "quality stars <stars>'.")},
    {"name": "incident_log", "reference": ref_incidents, "gen": gen_incidents, "description": (
        "Review an incident log. The entries input is a JSON array of objects with keys 'time' ('HH:MM', "
        "in time order on one day) and 'note'. Decide each note's severity, as exactly one of 'low', "
        "'medium' or 'high'. Escalate if any entry is high, or if three medium entries fall within 60 "
        "minutes of each other, that is, some medium entry and the second medium entry after it are at "
        "most 60 minutes apart. Return the text '<h> high, <m> medium, <l> low | escalate <yes or no> | "
        "first high <time>', where the time is that of the first high entry, or 'none'.")},
    {"name": "expense_lines", "reference": ref_expenses, "gen": gen_expenses, "description": (
        "Total expense lines by category. The lines input is a JSON array of objects with keys 'amount' "
        "(euros as text with two decimals) and 'description'. Decide each line's category from its "
        "description, as exactly one of 'travel', 'meals', 'equipment' or 'other'. Total the amounts per "
        "category. A line is flagged when it is meals over 50.00 or equipment over 500.00. Return the text "
        "'travel <t> | meals <m> | equipment <e> | other <o> | <f> flagged', each total with exactly two "
        "decimals.")},
    {"name": "survey_comments", "reference": ref_survey, "gen": gen_survey, "description": (
        "Score survey responses. The responses input is a JSON array of objects with keys 'rating' (0 to "
        "10) and 'comment'. Decide each comment's sentiment, as exactly one of 'positive', 'negative' or "
        "'neutral'. A promoter rated 9 or 10 and a detractor 0 to 6. The nps is 100 times (promoters minus "
        "detractors) divided by the number of responses, rounded to a whole number with halves rounded "
        "towards positive. A mismatch is a rating of 9 or 10 with a negative comment, or a rating of 6 or "
        "less with a positive comment. Return the text 'nps <nps> | <p> positive, <n> negative | <k> "
        "mismatches'.")},
    {"name": "menu_check", "reference": ref_menu, "gen": gen_menu, "description": (
        "Check a menu for a guest's allergy. The dishes input is a JSON array of objects with keys 'name', "
        "'price' (euros as text with two decimals) and 'description'; the allergy input is one of 'nuts', "
        "'dairy' or 'gluten'. Decide from each description which allergen the dish contains, as exactly one "
        "of 'nuts', 'dairy', 'gluten' or 'none'. A dish is safe when its allergen is not the guest's "
        "allergy. The cheapest safe dish has the lowest price, the alphabetically first name on a tie, or "
        "'none'. Return the text '<s> of <n> safe | cheapest safe <name> | avoid <names>', where the names "
        "to avoid are the unsafe dishes in menu order separated by ', ', or 'none'.")},
    {"name": "applicant_screen", "reference": ref_applicants, "gen": gen_applicants, "description": (
        "Shortlist job applicants for a role. The applicants input is a JSON array of objects with keys "
        "'name', 'years' (years of experience) and 'letter'; the role input is one of 'engineering', "
        "'design' or 'sales'. Decide from each letter which role the applicant is applying for, as exactly "
        "one of 'engineering', 'design' or 'sales'. The shortlist is the applicants applying for the role "
        "with at least 3 years, by most years first and then by name. Return the text '<role>: shortlist "
        "<names> | <k> other roles', where the names are separated by ', ' or are 'none', and k counts "
        "applicants applying for a different role.")},
    {"name": "delivery_feedback", "reference": ref_deliveries, "gen": gen_deliveries, "description": (
        "Score couriers from delivery notes. The drops input is a JSON array of objects with keys "
        "'driver', 'minutes_late' and 'note'. Decide from each note the outcome, as exactly one of "
        "'delivered', 'missed' or 'damaged'. A delivered drop scores 2 points if minutes_late is 10 or "
        "less and 1 point otherwise; missed scores 0 and damaged scores -1. The best driver has the most "
        "points in total, the alphabetically first on a tie. Return the text '<d> delivered, <m> missed, "
        "<x> damaged | best <driver> (<points>)'.")},
    {"name": "listing_filter", "reference": ref_listings, "gen": gen_listings, "description": (
        "Filter flat listings. The listings input is a JSON array of objects with keys 'id', 'price' "
        "(monthly rent in euros), 'beds' and 'blurb'; the budget and min_beds inputs are numbers. Decide "
        "from each blurb what outdoor space the flat has, as exactly one of 'garden', 'balcony' or "
        "'none'. A match costs at most the budget, has at least min_beds beds and has some outdoor space. "
        "Return the text '<k> matches: <ids> | gardens <g>', where the ids are the matches by price and "
        "then id, separated by ', ', or 'none', and g counts all listings with a garden.")},
]
for _shape in SHAPES:
    _shape["output"] = OUTPUT
    _list, _field, _label, _values = READINGS[_shape["name"]]
    _shape["reading"] = (_list, _label, _values)
    _shape["item_field"] = _field

TESTS = {
    "review_digest": [
        ({"reviews": [{"stars": 4, "text": ""}, {"stars": 5, "text": ""}, {"stars": 2, "text": ""},
                      {"stars": 3, "text": ""}]},
         {"topic": ["quality", "quality", "price", "delivery"]},
         "price 1, quality 2, delivery 1, service 0 | worst price | quality stars 4.5"),
        ({"reviews": [{"stars": 3, "text": ""}, {"stars": 3, "text": ""}]}, {"topic": ["service", "delivery"]},
         "price 0, quality 0, delivery 1, service 1 | worst delivery | quality stars none"),
    ],
    "incident_log": [
        ({"entries": [{"time": "08:00", "note": ""}, {"time": "08:30", "note": ""}, {"time": "08:45", "note": ""},
                      {"time": "09:00", "note": ""}]},
         {"severity": ["medium", "low", "medium", "medium"]}, "0 high, 3 medium, 1 low | escalate yes | first high none"),
        ({"entries": [{"time": "08:00", "note": ""}, {"time": "08:45", "note": ""}, {"time": "09:01", "note": ""}]},
         {"severity": ["medium", "medium", "medium"]}, "0 high, 3 medium, 0 low | escalate no | first high none"),
        ({"entries": [{"time": "07:10", "note": ""}, {"time": "07:20", "note": ""}]}, {"severity": ["low", "high"]},
         "1 high, 0 medium, 1 low | escalate yes | first high 07:20"),
    ],
    "expense_lines": [
        ({"lines": [{"amount": "50.00", "description": ""}, {"amount": "50.01", "description": ""},
                    {"amount": "500.00", "description": ""}, {"amount": "12.50", "description": ""}]},
         {"category": ["meals", "meals", "equipment", "travel"]},
         "travel 12.50 | meals 100.01 | equipment 500.00 | other 0.00 | 1 flagged"),
    ],
    "survey_comments": [
        ({"responses": [{"rating": 10, "comment": ""}, {"rating": 9, "comment": ""}, {"rating": 3, "comment": ""},
                        {"rating": 7, "comment": ""}]},
         {"sentiment": ["positive", "negative", "positive", "neutral"]},
         "nps 25 | 2 positive, 1 negative | 2 mismatches"),
        ({"responses": [{"rating": 0, "comment": ""}, {"rating": 8, "comment": ""}, {"rating": 9, "comment": ""},
                        {"rating": 2, "comment": ""}, {"rating": 5, "comment": ""}, {"rating": 8, "comment": ""},
                        {"rating": 1, "comment": ""}, {"rating": 8, "comment": ""}]},
         {"sentiment": ["negative"] * 8}, "nps -37 | 0 positive, 8 negative | 1 mismatches"),
    ],
    "menu_check": [
        ({"dishes": [{"name": "Tart", "price": "8.00", "description": ""},
                     {"name": "Bake", "price": "8.00", "description": ""},
                     {"name": "Stew", "price": "12.50", "description": ""}], "allergy": "nuts"},
         {"allergen": ["nuts", "none", "dairy"]}, "2 of 3 safe | cheapest safe Bake | avoid Tart"),
        ({"dishes": [{"name": "Flan", "price": "6.50", "description": ""}], "allergy": "dairy"},
         {"allergen": ["dairy"]}, "0 of 1 safe | cheapest safe none | avoid Flan"),
    ],
    "applicant_screen": [
        ({"applicants": [{"name": "Isla", "years": 5, "letter": ""}, {"name": "Dev", "years": 5, "letter": ""},
                         {"name": "Hugo", "years": 2, "letter": ""}, {"name": "Lena", "years": 9, "letter": ""}],
          "role": "design"},
         {"role": ["design", "design", "design", "sales"]}, "design: shortlist Dev, Isla | 1 other roles"),
        ({"applicants": [{"name": "Kofi", "years": 3, "letter": ""}], "role": "sales"}, {"role": ["engineering"]},
         "sales: shortlist none | 1 other roles"),
    ],
    "delivery_feedback": [
        ({"drops": [{"driver": "Bex", "minutes_late": 10, "note": ""}, {"driver": "Ade", "minutes_late": 11, "note": ""},
                    {"driver": "Ade", "minutes_late": 0, "note": ""}, {"driver": "Bex", "minutes_late": 0, "note": ""}]},
         {"outcome": ["delivered", "delivered", "damaged", "missed"]},
         "2 delivered, 1 missed, 1 damaged | best Bex (2)"),
        ({"drops": [{"driver": "Cy", "minutes_late": 0, "note": ""}]}, {"outcome": ["damaged"]},
         "0 delivered, 0 missed, 1 damaged | best Cy (-1)"),
    ],
    "listing_filter": [
        ({"listings": [{"id": "P200", "price": 900, "beds": 2, "blurb": ""},
                       {"id": "P150", "price": 900, "beds": 3, "blurb": ""},
                       {"id": "P300", "price": 950, "beds": 2, "blurb": ""},
                       {"id": "P400", "price": 600, "beds": 1, "blurb": ""}], "budget": 900, "min_beds": 2},
         {"outdoor": ["balcony", "garden", "garden", "garden"]}, "2 matches: P150, P200 | gardens 3"),
        ({"listings": [{"id": "P101", "price": 400, "beds": 1, "blurb": ""}], "budget": 500, "min_beds": 1},
         {"outdoor": ["none"]}, "0 matches: none | gardens 0"),
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
    return {shape: {label: [f"placeholder {label} {i}" for i in range(3)] for label in values}
            for shape, (_, _, _, values) in READINGS.items()}


def self_verify(prose=None):
    import fast_path_jobs_bench_v1
    import fast_path_jobs_bench_v2_large
    import fast_path_planned_bench_v2
    import fast_path_planned_bench_v3
    import fast_path_planned_bench_v4
    import fast_path_planned_bench_v5

    earlier = {s["name"] for module in (fast_path_jobs_bench_v1, fast_path_jobs_bench_v2_large,
                                        fast_path_planned_bench_v2, fast_path_planned_bench_v3,
                                        fast_path_planned_bench_v4, fast_path_planned_bench_v5)
               for s in module.SHAPES}
    names = [s["name"] for s in SHAPES]
    assert len(names) == len(set(names)) and not set(names) & earlier, "shape names must be new"
    if prose is None:
        prose = load_prose() if PROSE_PATH.exists() else placeholder_prose()
    for shape in SHAPES:
        for inputs, labels, expected in TESTS[shape["name"]]:
            got = shape["reference"](inputs, labels)
            assert got == expected, f"{shape['name']}: {got!r} != {expected!r}"
        list_input, _, values = shape["reading"]
        assert all(f"'{v}'" in shape["description"] for v in values), f"{shape['name']}: label missing"
        assert set(prose[shape["name"]]) == set(values) and all(prose[shape["name"]][v] for v in values)
        instances = stream(shape, prose=prose)
        assert [i for i, _ in instances] == [i for i, _ in stream(shape, prose=prose)], "not reproducible"
        for inputs, labels in instances:
            for name in inputs:
                assert name in shape["description"], f"{shape['name']}: input {name} not named"
            assert len(labels[shape["reading"][1]]) == len(inputs[list_input])
        gold(shape, instances)
    print(f"self_verify OK: {len(SHAPES)} job shapes, {STREAM_LENGTH} jobs each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_planned_bench_v6.py sha256:", bench_sha256())
