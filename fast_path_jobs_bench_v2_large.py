"""Larger multi-step jobs for the fast-path jobs experiment V2.

Same recipe as ``fast_path_jobs_bench_v1.py``, but each job carries a long
structured input (12 to 25 records) and five to seven function steps around
one or two judgement steps. These are the conditions in which a single model
call over the whole job is expected to be slowest and most error-prone, and in
which replacing model calls with code has the most to gain.

Gold is by construction: planted labels for judgement steps, reference
outputs for function steps, each reference qualified by hand-written tests.

Run ``python fast_path_jobs_bench_v2_large.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import fast_path_jobs_bench_v1 as _v1
from fast_path_jobs_bench_v1 import (  # noqa: F401  (job_document and gold are re-exported)
    F, INTENT, J, LANGUAGE, NAMES, TONE, TOPIC, gold, job_document, ref,
)

STREAM_SEED = 20261119
STREAM_LENGTH = 15

SERVICES = ["auth", "billing", "cart", "search", "mailer", "gateway"]
LEVELS = ["INFO", "INFO", "INFO", "WARN", "ERROR"]
COUNTRIES = ["DE", "ES", "FR", "IT", "PT"]
PEOPLE = ["Ana", "Bram", "Chen", "Dita", "Emre", "Farah", "Goran", "Hana"]
STOCK = ["bolts", "nails", "washers", "hinges", "brackets", "screws", "rivets", "clamps",
         "springs", "pulleys", "gaskets", "valves", "fuses", "cables", "levers", "pins"]
CHATTER = ["Agreed, moving on.", "Notes from last week were approved.", "Budget is unchanged.",
           "The room is booked for next time.", "No other business was raised."]
TASKS = ["update the roadmap", "send the invoice", "review the draft", "book the venue",
         "fix the login bug", "call the supplier", "renew the licence", "prepare slides"]
S_TONE, S_TOPIC, S_LANGUAGE, S_INTENT = _v1.S_TONE, _v1.S_TOPIC, _v1.S_LANGUAGE, _v1.S_INTENT
EUROS = (
    "def euros(cents):\n"
    "    return str(cents // 100) + '.' + str(cents % 100).zfill(2)\n"
)


def _pick(r, table):
    label = r.choice(sorted(table))
    return label, r.choice(table[label])


def _gen_invoice(r):
    tone, note = _pick(r, TONE)
    lines = []
    for _ in range(r.randint(12, 20)):
        sku = f"SKU-{r.choice([1001, 1002, 2040, 2041, 3300, 3301, 4815, 5000, 6120, 7777])}"
        lines.append(f"{sku} x{r.randint(1, 9)} @ {r.randint(1, 60)}.{r.choice([0, 5, 25, 50, 99]):02d}")
    return {"lines": "\n".join(lines), "note": note}, {"tone": tone}


def _gen_log(r):
    topic, incident = _pick(r, TOPIC)
    lines, seconds = [], r.randint(0, 3000)
    for _ in range(r.randint(18, 25)):
        seconds += r.randint(1, 90)
        stamp = f"{10 + seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        level = r.choice(LEVELS)
        lines.append(f"{stamp} {level} {r.choice(SERVICES)}: event {r.randint(100, 999)}")
    return {"log": "\n".join(lines), "incident": incident}, {"topic": topic}


def _gen_orders(r):
    language, note = _pick(r, LANGUAGE)
    rows = ["id,country,qty,unit_cents"]
    for index in range(r.randint(14, 20)):
        rows.append(f"A{100 + index},{r.choice(COUNTRIES)},{r.randint(1, 12)},{r.randint(150, 2500)}")
    return {"csv": "\n".join(rows), "note": note}, {"language": language}


def _gen_thread(r):
    intent, opener = _pick(r, INTENT)
    tone, closer = _pick(r, TONE)
    minute, lines = r.randint(480, 700), []
    speakers = r.sample(PEOPLE, r.randint(3, 5))
    for _ in range(r.randint(8, 14)):
        minute += r.randint(1, 25)
        lines.append(f"[{minute // 60:02d}:{minute % 60:02d}] {r.choice(speakers)}: {r.choice(CHATTER)}")
    return ({"thread": "\n".join(lines), "opener": opener, "closer": closer},
            {"intent": intent, "tone": tone})


def _gen_grades(r):
    tone, comment = _pick(r, TONE)
    names = r.sample(PEOPLE + NAMES, r.randint(12, 16))
    scores = "\n".join(f"{name}: {r.randint(35, 100)}" for name in names)
    return {"scores": scores, "comment": comment}, {"tone": tone}


def _gen_stock(r):
    tone, note = _pick(r, TONE)
    items = r.sample(STOCK, r.randint(12, 16))
    lines = [f"{item} | {r.randint(0, 40)} | {r.randint(5, 30)} | {r.randint(20, 900)}" for item in items]
    return {"stock": "\n".join(lines), "supplier_note": note}, {"tone": tone}


def _gen_minutes(r):
    topic, summary = _pick(r, TOPIC)
    lines = []
    for _ in range(r.randint(12, 18)):
        if r.random() < 0.6:
            lines.append(f"ACTION @{r.choice(PEOPLE)} due 2026-{r.randint(10, 12):02d}-{r.randint(1, 28):02d}: "
                         f"{r.choice(TASKS)}")
        else:
            lines.append(r.choice(CHATTER))
    return ({"minutes": "\n".join(lines), "summary": summary, "today": "2026-11-17"}, {"topic": topic})


SHAPES = [
    {
        "name": "invoice_audit",
        "steps": [
            J("tone", S_TONE, ref("note")),
            F("items", "Parse invoice lines of the form 'SKU-dddd xQ @ E.CC', one per line, into a list of [sku, quantity, unit price in cents] in the order given. Example: 'SKU-1001 x3 @ 12.50' gives ['SKU-1001', 3, 1250].",
              "def solve(lines: str) -> list:",
              "import re\ndef solve(lines):\n    out = []\n    for sku, qty, euros, cents in re.findall(r'(SKU-\\d{4}) x(\\d+) @ (\\d+)\\.(\\d{2})', lines):\n        out.append([sku, int(qty), int(euros) * 100 + int(cents)])\n    return out\n",
              [[["SKU-1001 x3 @ 12.50"], [["SKU-1001", 3, 1250]]], [[""], []],
               [["SKU-2040 x1 @ 0.99\nSKU-1001 x10 @ 3.05"], [["SKU-2040", 1, 99], ["SKU-1001", 10, 305]]],
               [["SKU-7777 x2 @ 60.00"], [["SKU-7777", 2, 6000]]]],
              ref("lines")),
            F("subtotal", "Given a list of [sku, quantity, unit cents], return the sum of quantity times unit cents.",
              "def solve(items: list) -> int:",
              "def solve(items):\n    return sum(q * c for _, q, c in items)\n",
              [[[[["a", 2, 100], ["b", 1, 5]]], 205], [[[]], 0], [[[["a", 3, 1250]]], 3750],
               [[[["a", 1, 1], ["a", 1, 1]]], 2]],
              ref("items")),
            F("top_sku", "Given a list of [sku, quantity, unit cents], return the sku of the line with the largest quantity times unit cents. On a tie return the earliest such line's sku. Return 'none' for an empty list.",
              "def solve(items: list) -> str:",
              "def solve(items):\n    best, top = None, 'none'\n    for sku, q, c in items:\n        if best is None or q * c > best:\n            best, top = q * c, sku\n    return top\n",
              [[[[["a", 2, 100], ["b", 1, 300]]], "b"], [[[]], "none"], [[[["a", 1, 100], ["b", 2, 50]]], "a"],
               [[[["x", 5, 5]]], "x"]],
              ref("items")),
            F("distinct", "Given a list of [sku, quantity, unit cents], return the number of distinct skus.",
              "def solve(items: list) -> int:",
              "def solve(items):\n    return len({sku for sku, _, _ in items})\n",
              [[[[["a", 2, 100], ["a", 1, 300]]], 1], [[[]], 0], [[[["a", 1, 1], ["b", 1, 1], ["c", 1, 1]]], 3],
               [[[["a", 1, 1], ["b", 1, 1], ["a", 2, 2]]], 2]],
              ref("items")),
            F("discount", "Return a discount in cents. If the tone is 'negative' and the subtotal is more than 20000, the discount is 10 percent of the subtotal; if the tone is 'negative' otherwise, it is 5 percent; for any other tone it is 0. Round down to whole cents.",
              "def solve(subtotal: int, tone: str) -> int:",
              "def solve(subtotal, tone):\n    if tone != 'negative':\n        return 0\n    return subtotal * (10 if subtotal > 20000 else 5) // 100\n",
              [[[30000, "negative"], 3000], [[20000, "negative"], 1000], [[999, "negative"], 49],
               [[50000, "positive"], 0], [[20001, "negative"], 2000]],
              ref("subtotal"), ref("tone")),
            F("summary", "Return 'total <amount> | top <sku> | <n> skus', where amount is the subtotal minus the discount written in euros with exactly two decimals. Example: 3750 and 0 with top 'SKU-1' and 2 give 'total 37.50 | top SKU-1 | 2 skus'.",
              "def solve(subtotal: int, discount: int, top: str, distinct: int) -> str:",
              EUROS + "def solve(subtotal, discount, top, distinct):\n    return 'total ' + euros(subtotal - discount) + ' | top ' + top + ' | ' + str(distinct) + ' skus'\n",
              [[[3750, 0, "SKU-1", 2], "total 37.50 | top SKU-1 | 2 skus"], [[1000, 1000, "none", 0], "total 0.00 | top none | 0 skus"],
               [[123456, 6172, "SKU-9", 7], "total 1172.84 | top SKU-9 | 7 skus"], [[5, 0, "a", 1], "total 0.05 | top a | 1 skus"]],
              ref("subtotal"), ref("discount"), ref("top_sku"), ref("distinct")),
        ],
        "output": "summary",
        "gen": _gen_invoice,
    },
    {
        "name": "log_triage",
        "steps": [
            J("topic", S_TOPIC, ref("incident")),
            F("lines", "Return the number of non-empty lines in the text.",
              "def solve(log: str) -> int:",
              "def solve(log):\n    return sum(1 for line in log.split('\\n') if line.strip())\n",
              [[["a\nb\nc"], 3], [[""], 0], [["a\n\nb\n"], 2], [["one"], 1]],
              ref("log")),
            F("errors", "Each log line is 'HH:MM:SS LEVEL service: message'. Return the number of lines whose level is ERROR.",
              "def solve(log: str) -> int:",
              "def solve(log):\n    return sum(1 for line in log.split('\\n') if len(line.split()) > 1 and line.split()[1] == 'ERROR')\n",
              [[["10:00:01 ERROR auth: x\n10:00:02 INFO cart: y"], 1], [[""], 0],
               [["10:00:01 WARN a: ERROR\n10:00:02 ERROR b: z\n10:00:03 ERROR a: q"], 2], [["10:00:01 INFO a: b"], 0]],
              ref("log")),
            F("first_error", "Each log line is 'HH:MM:SS LEVEL service: message'. Return the timestamp of the first ERROR line, or 'none' if there is none.",
              "def solve(log: str) -> str:",
              "def solve(log):\n    for line in log.split('\\n'):\n        parts = line.split()\n        if len(parts) > 1 and parts[1] == 'ERROR':\n            return parts[0]\n    return 'none'\n",
              [[["10:00:01 INFO a: x\n10:00:05 ERROR b: y"], "10:00:05"], [[""], "none"],
               [["10:00:01 WARN a: ERROR"], "none"], [["09:59:59 ERROR a: b\n10:00:00 ERROR c: d"], "09:59:59"]],
              ref("log")),
            F("worst", "Each log line is 'HH:MM:SS LEVEL service: message'. Return the service with the most ERROR lines. On a tie return the alphabetically first. Return 'none' if there are no ERROR lines.",
              "def solve(log: str) -> str:",
              "def solve(log):\n    counts = {}\n    for line in log.split('\\n'):\n        parts = line.split()\n        if len(parts) > 2 and parts[1] == 'ERROR':\n            name = parts[2].rstrip(':')\n            counts[name] = counts.get(name, 0) + 1\n    if not counts:\n        return 'none'\n    return sorted(counts, key=lambda k: (-counts[k], k))[0]\n",
              [[["1 ERROR b: x\n2 ERROR a: y"], "a"], [[""], "none"], [["1 ERROR b: x\n2 ERROR b: y\n3 ERROR a: z"], "b"],
               [["1 WARN a: x"], "none"]],
              ref("log")),
            F("rate", "Return the error count as a percentage of the line count, rounded to the nearest whole number with halves rounded up. Return 0 if the line count is 0.",
              "def solve(errors: int, lines: int) -> int:",
              "def solve(errors, lines):\n    if lines == 0:\n        return 0\n    return (200 * errors + lines) // (2 * lines)\n",
              [[[1, 8], 13], [[0, 5], 0], [[1, 3], 33], [[2, 3], 67], [[0, 0], 0], [[5, 5], 100]],
              ref("errors"), ref("lines")),
            F("report", "Return '<topic>: <errors> errors (<rate>%), worst <service>, first at <timestamp>'.",
              "def solve(topic: str, errors: int, rate: int, worst: str, first: str) -> str:",
              "def solve(topic, errors, rate, worst, first):\n    return topic + ': ' + str(errors) + ' errors (' + str(rate) + '%), worst ' + worst + ', first at ' + first\n",
              [[["billing", 3, 14, "auth", "10:01:00"], "billing: 3 errors (14%), worst auth, first at 10:01:00"],
               [["account", 0, 0, "none", "none"], "account: 0 errors (0%), worst none, first at none"],
               [["t", 1, 5, "x", "y"], "t: 1 errors (5%), worst x, first at y"], [["a", 2, 2, "b", "c"], "a: 2 errors (2%), worst b, first at c"]],
              ref("topic"), ref("errors"), ref("rate"), ref("worst"), ref("first_error")),
        ],
        "output": "report",
        "gen": _gen_log,
    },
    {
        "name": "order_batch",
        "steps": [
            J("language", S_LANGUAGE, ref("note")),
            F("rows", "Parse CSV text with the header 'id,country,qty,unit_cents' into a list of [id, country, qty, unit_cents] with qty and unit_cents as integers, in order, without the header.",
              "def solve(csv: str) -> list:",
              "def solve(csv):\n    out = []\n    for line in csv.split('\\n')[1:]:\n        if line.strip():\n            i, c, q, u = line.split(',')\n            out.append([i, c, int(q), int(u)])\n    return out\n",
              [[["id,country,qty,unit_cents\nA1,DE,2,500"], [["A1", "DE", 2, 500]]], [["id,country,qty,unit_cents"], []],
               [["id,country,qty,unit_cents\nA1,DE,2,500\nA2,FR,1,99"], [["A1", "DE", 2, 500], ["A2", "FR", 1, 99]]],
               [["id,country,qty,unit_cents\nX,PT,10,1"], [["X", "PT", 10, 1]]]],
              ref("csv")),
            F("by_country", "Given rows [id, country, qty, unit_cents], return an object mapping each country to the sum of qty times unit_cents over its rows.",
              "def solve(rows: list) -> dict:",
              "def solve(rows):\n    out = {}\n    for _, c, q, u in rows:\n        out[c] = out.get(c, 0) + q * u\n    return out\n",
              [[[[["A1", "DE", 2, 500], ["A2", "DE", 1, 1]]], {"DE": 1001}], [[[]], {}],
               [[[["A1", "DE", 1, 5], ["A2", "FR", 2, 5]]], {"DE": 5, "FR": 10}], [[[["a", "IT", 0, 9]]], {"IT": 0}]],
              ref("rows")),
            F("top_country", "Given an object mapping countries to totals, return the country with the largest total. On a tie return the alphabetically first. Return 'none' for an empty object.",
              "def solve(totals: dict) -> str:",
              "def solve(totals):\n    if not totals:\n        return 'none'\n    return sorted(totals, key=lambda k: (-totals[k], k))[0]\n",
              [[[{"DE": 5, "FR": 10}], "FR"], [[{}], "none"], [[{"FR": 3, "DE": 3}], "DE"], [[{"IT": 0}], "IT"]],
              ref("by_country")),
            F("big_orders", "Given rows [id, country, qty, unit_cents], return the ids, in order, of rows whose qty times unit_cents is more than 10000.",
              "def solve(rows: list) -> list:",
              "def solve(rows):\n    return [i for i, _, q, u in rows if q * u > 10000]\n",
              [[[[["A1", "DE", 10, 1001], ["A2", "FR", 10, 1000]]], ["A1"]], [[[]], []],
               [[[["A", "DE", 1, 10001], ["B", "DE", 2, 6000]]], ["A", "B"]], [[[["A", "DE", 1, 10000]]], []]],
              ref("rows")),
            F("label", "Return the totals label for a language: 'Totals' for 'english', 'Totaux' for 'french', 'Totales' for 'spanish' and 'Summen' for 'german'.",
              "def solve(language: str) -> str:",
              "def solve(language):\n    return {'english': 'Totals', 'french': 'Totaux', 'spanish': 'Totales', 'german': 'Summen'}[language]\n",
              [[["english"], "Totals"], [["french"], "Totaux"], [["spanish"], "Totales"], [["german"], "Summen"]],
              ref("language")),
            F("summary", "Return '<label>: top <country>, <n> big orders: <ids>' where n is the number of ids and ids are joined by ','. Write 'none' in place of the ids if the list is empty.",
              "def solve(label: str, top: str, big: list) -> str:",
              "def solve(label, top, big):\n    return label + ': top ' + top + ', ' + str(len(big)) + ' big orders: ' + (','.join(big) if big else 'none')\n",
              [[["Totals", "DE", ["A1", "A2"]], "Totals: top DE, 2 big orders: A1,A2"], [["Summen", "none", []], "Summen: top none, 0 big orders: none"],
               [["Totaux", "FR", ["X"]], "Totaux: top FR, 1 big orders: X"], [["a", "b", []], "a: top b, 0 big orders: none"]],
              ref("label"), ref("top_country"), ref("big_orders")),
        ],
        "output": "summary",
        "gen": _gen_orders,
    },
    {
        "name": "thread_digest",
        "steps": [
            J("intent", S_INTENT, ref("opener")),
            J("tone", S_TONE, ref("closer")),
            F("counts", "Each line is '[HH:MM] Name: text'. Return an object mapping each name to its number of lines.",
              "def solve(thread: str) -> dict:",
              "import re\ndef solve(thread):\n    out = {}\n    for name in re.findall(r'^\\[\\d{2}:\\d{2}\\] ([^:]+):', thread, re.M):\n        out[name] = out.get(name, 0) + 1\n    return out\n",
              [[["[09:00] Ana: hi\n[09:01] Bram: yo\n[09:02] Ana: ok"], {"Ana": 2, "Bram": 1}], [[""], {}],
               [["[10:00] Chen: a: b"], {"Chen": 1}], [["[10:00] A: x\n[10:05] A: y"], {"A": 2}]],
              ref("thread")),
            F("most", "Given an object mapping names to counts, return the name with the largest count. On a tie return the alphabetically first. Return 'none' for an empty object.",
              "def solve(counts: dict) -> str:",
              "def solve(counts):\n    if not counts:\n        return 'none'\n    return sorted(counts, key=lambda k: (-counts[k], k))[0]\n",
              [[[{"Ana": 2, "Bram": 1}], "Ana"], [[{}], "none"], [[{"Bram": 2, "Ana": 2}], "Ana"], [[{"X": 0}], "X"]],
              ref("counts")),
            F("span", "Each line starts with a time '[HH:MM]'. Return the number of minutes from the first line's time to the last line's time. Return 0 if there are fewer than two lines.",
              "def solve(thread: str) -> int:",
              "import re\ndef solve(thread):\n    times = [int(h) * 60 + int(m) for h, m in re.findall(r'^\\[(\\d{2}):(\\d{2})\\]', thread, re.M)]\n    return times[-1] - times[0] if len(times) > 1 else 0\n",
              [[["[09:00] A: x\n[10:30] B: y"], 90], [[""], 0], [["[09:00] A: x"], 0], [["[08:55] A: x\n[09:00] B: y\n[09:10] C: z"], 15]],
              ref("thread")),
            F("priority", "Return 'urgent' if the tone is 'negative' and the intent is 'refund' or 'cancel'; 'normal' if the tone is 'negative' and the intent is anything else; otherwise 'low'.",
              "def solve(intent: str, tone: str) -> str:",
              "def solve(intent, tone):\n    if tone != 'negative':\n        return 'low'\n    return 'urgent' if intent in ('refund', 'cancel') else 'normal'\n",
              [[["refund", "negative"], "urgent"], [["cancel", "negative"], "urgent"], [["order_status", "negative"], "normal"],
               [["refund", "positive"], "low"], [["cancel", "neutral"], "low"]],
              ref("intent"), ref("tone")),
            F("digest", "Return '<priority> <intent> | led by <name> | <minutes> min'.",
              "def solve(priority: str, intent: str, name: str, minutes: int) -> str:",
              "def solve(priority, intent, name, minutes):\n    return priority + ' ' + intent + ' | led by ' + name + ' | ' + str(minutes) + ' min'\n",
              [[["urgent", "refund", "Ana", 90], "urgent refund | led by Ana | 90 min"], [["low", "cancel", "none", 0], "low cancel | led by none | 0 min"],
               [["normal", "order_status", "Bram", 5], "normal order_status | led by Bram | 5 min"], [["a", "b", "c", 1], "a b | led by c | 1 min"]],
              ref("priority"), ref("intent"), ref("most"), ref("span")),
        ],
        "output": "digest",
        "gen": _gen_thread,
    },
    {
        "name": "grade_report",
        "steps": [
            J("tone", S_TONE, ref("comment")),
            F("parsed", "Parse lines of the form 'Name: score' into a list of [name, score] with score as an integer, in order.",
              "def solve(scores: str) -> list:",
              "def solve(scores):\n    out = []\n    for line in scores.split('\\n'):\n        if line.strip():\n            name, score = line.rsplit(':', 1)\n            out.append([name.strip(), int(score)])\n    return out\n",
              [[["Ana: 90\nBram: 75"], [["Ana", 90], ["Bram", 75]]], [[""], []], [["Chen: 100"], [["Chen", 100]]],
               [["A: 0\n\nB: 5"], [["A", 0], ["B", 5]]]],
              ref("scores")),
            F("mean", "Given a list of [name, score], return the mean score rounded to the nearest whole number with halves rounded up. Return 0 for an empty list.",
              "def solve(parsed: list) -> int:",
              "def solve(parsed):\n    if not parsed:\n        return 0\n    total = sum(s for _, s in parsed)\n    return (2 * total + len(parsed)) // (2 * len(parsed))\n",
              [[[[["a", 90], ["b", 75]]], 83], [[[]], 0], [[[["a", 1], ["b", 2]]], 2], [[[["a", 50]]], 50],
               [[[["a", 1], ["b", 1], ["c", 2]]], 1]],
              ref("parsed")),
            F("median", "Given a list of [name, score], return the median score. For an even number of scores return the lower of the two middle values. Return 0 for an empty list.",
              "def solve(parsed: list) -> int:",
              "def solve(parsed):\n    s = sorted(score for _, score in parsed)\n    if not s:\n        return 0\n    return s[(len(s) - 1) // 2]\n",
              [[[[["a", 90], ["b", 75], ["c", 80]]], 80], [[[]], 0], [[[["a", 4], ["b", 1], ["c", 3], ["d", 2]]], 2], [[[["a", 7]]], 7]],
              ref("parsed")),
            F("grades", "Given a list of [name, score], return an object counting letter grades with keys 'A', 'B', 'C', 'D' and 'F', all present: A for 90 and above, B for 80 to 89, C for 70 to 79, D for 60 to 69, F below 60.",
              "def solve(parsed: list) -> dict:",
              "def solve(parsed):\n    out = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}\n    for _, s in parsed:\n        out['A' if s >= 90 else 'B' if s >= 80 else 'C' if s >= 70 else 'D' if s >= 60 else 'F'] += 1\n    return out\n",
              [[[[["a", 90], ["b", 89], ["c", 59]]], {"A": 1, "B": 1, "C": 0, "D": 0, "F": 1}], [[[]], {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}],
               [[[["a", 70], ["b", 69], ["c", 60]]], {"A": 0, "B": 0, "C": 1, "D": 2, "F": 0}], [[[["a", 100]]], {"A": 1, "B": 0, "C": 0, "D": 0, "F": 0}]],
              ref("parsed")),
            F("top", "Given a list of [name, score], return the name with the highest score. On a tie return the alphabetically first. Return 'none' for an empty list.",
              "def solve(parsed: list) -> str:",
              "def solve(parsed):\n    if not parsed:\n        return 'none'\n    return sorted(parsed, key=lambda p: (-p[1], p[0]))[0][0]\n",
              [[[[["a", 90], ["b", 95]]], "b"], [[[]], "none"], [[[["Zoe", 80], ["Amy", 80]]], "Amy"], [[[["x", 0]]], "x"]],
              ref("parsed")),
            F("report", "Return 'mean <m>, median <md>, A<a> B<b> C<c> D<d> F<f>, top <name>', followed by ' - review' if the tone is 'negative'.",
              "def solve(mean: int, median: int, grades: dict, top: str, tone: str) -> str:",
              "def solve(mean, median, grades, top, tone):\n    counts = ' '.join(k + str(grades[k]) for k in 'ABCDF')\n    text = 'mean ' + str(mean) + ', median ' + str(median) + ', ' + counts + ', top ' + top\n    return text + (' - review' if tone == 'negative' else '')\n",
              [[[80, 79, {"A": 1, "B": 2, "C": 0, "D": 0, "F": 1}, "Ana", "neutral"], "mean 80, median 79, A1 B2 C0 D0 F1, top Ana"],
               [[0, 0, {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}, "none", "negative"], "mean 0, median 0, A0 B0 C0 D0 F0, top none - review"],
               [[90, 90, {"A": 3, "B": 0, "C": 0, "D": 0, "F": 0}, "Zoe", "positive"], "mean 90, median 90, A3 B0 C0 D0 F0, top Zoe"],
               [[1, 2, {"A": 0, "B": 0, "C": 0, "D": 0, "F": 9}, "x", "negative"], "mean 1, median 2, A0 B0 C0 D0 F9, top x - review"]],
              ref("mean"), ref("median"), ref("grades"), ref("top"), ref("tone")),
        ],
        "output": "report",
        "gen": _gen_grades,
    },
    {
        "name": "stock_reorder",
        "steps": [
            J("tone", S_TONE, ref("supplier_note")),
            F("parsed", "Parse lines of the form 'item | on_hand | minimum | unit_cents' into a list of [item, on_hand, minimum, unit_cents] with the numbers as integers, in order.",
              "def solve(stock: str) -> list:",
              "def solve(stock):\n    out = []\n    for line in stock.split('\\n'):\n        if line.strip():\n            item, a, b, c = [p.strip() for p in line.split('|')]\n            out.append([item, int(a), int(b), int(c)])\n    return out\n",
              [[["bolts | 3 | 10 | 25"], [["bolts", 3, 10, 25]]], [[""], []],
               [["a | 0 | 5 | 1\nb | 9 | 5 | 2"], [["a", 0, 5, 1], ["b", 9, 5, 2]]], [["x|1|2|3"], [["x", 1, 2, 3]]]],
              ref("stock")),
            F("low", "Given [item, on_hand, minimum, unit_cents] rows, return the items, in order, whose on_hand is below their minimum.",
              "def solve(rows: list) -> list:",
              "def solve(rows):\n    return [item for item, a, m, _ in rows if a < m]\n",
              [[[[["a", 3, 10, 1], ["b", 10, 10, 1]]], ["a"]], [[[]], []], [[[["a", 0, 1, 1], ["b", 0, 2, 1]]], ["a", "b"]],
               [[[["a", 5, 4, 1]]], []]],
              ref("parsed")),
            F("reorder", "Given [item, on_hand, minimum, unit_cents] rows, return an object mapping each item whose on_hand is below its minimum to the quantity to order, which is twice the minimum minus the on_hand.",
              "def solve(rows: list) -> dict:",
              "def solve(rows):\n    return {item: 2 * m - a for item, a, m, _ in rows if a < m}\n",
              [[[[["a", 3, 10, 1], ["b", 10, 10, 1]]], {"a": 17}], [[[]], {}], [[[["a", 0, 1, 1], ["b", 1, 2, 1]]], {"a": 2, "b": 3}],
               [[[["a", 5, 4, 1]]], {}]],
              ref("parsed")),
            F("cost", "Given an object mapping items to quantities and [item, on_hand, minimum, unit_cents] rows, return the total cents of ordering those quantities at each item's unit_cents.",
              "def solve(order: dict, rows: list) -> int:",
              "def solve(order, rows):\n    price = {item: c for item, _, _, c in rows}\n    return sum(q * price[item] for item, q in order.items())\n",
              [[[{"a": 17}, [["a", 3, 10, 25], ["b", 10, 10, 1]]], 425], [[{}, []], 0],
               [[{"a": 2, "b": 3}, [["a", 0, 1, 10], ["b", 1, 2, 100]]], 320], [[{}, [["a", 1, 1, 1]]], 0]],
              ref("reorder"), ref("parsed")),
            F("expedite", "Return true if the tone is 'negative' or the cost is more than 50000; otherwise false.",
              "def solve(tone: str, cost: int) -> bool:",
              "def solve(tone, cost):\n    return tone == 'negative' or cost > 50000\n",
              [[["negative", 0], True], [["positive", 50001], True], [["neutral", 50000], False], [["positive", 1], False]],
              ref("tone"), ref("cost")),
            F("order_line", "Return '<n> items, <amount> EUR', where n is the number of low items and amount is the cost in euros with exactly two decimals, followed by ', EXPEDITE' if the flag is true.",
              "def solve(low: list, cost: int, expedite: bool) -> str:",
              EUROS + "def solve(low, cost, expedite):\n    return str(len(low)) + ' items, ' + euros(cost) + ' EUR' + (', EXPEDITE' if expedite else '')\n",
              [[[["a"], 425, False], "1 items, 4.25 EUR"], [[[], 0, True], "0 items, 0.00 EUR, EXPEDITE"],
               [[["a", "b"], 50001, True], "2 items, 500.01 EUR, EXPEDITE"], [[["x", "y", "z"], 99, False], "3 items, 0.99 EUR"]],
              ref("low"), ref("cost"), ref("expedite")),
        ],
        "output": "order_line",
        "gen": _gen_stock,
    },
    {
        "name": "meeting_actions",
        "steps": [
            J("topic", S_TOPIC, ref("summary")),
            F("actions", "Lines of the form 'ACTION @name due YYYY-MM-DD: task' are actions; ignore every other line. Return a list of [name, due date, task] for the actions, in order.",
              "def solve(minutes: str) -> list:",
              "import re\ndef solve(minutes):\n    return [list(m) for m in re.findall(r'^ACTION @(\\w+) due (\\d{4}-\\d{2}-\\d{2}): (.*)$', minutes, re.M)]\n",
              [[["ACTION @Ana due 2026-11-01: send it\nNotes."], [["Ana", "2026-11-01", "send it"]]], [["No actions."], []],
               [["ACTION @A due 2026-01-02: x\nACTION @B due 2026-01-01: y"], [["A", "2026-01-02", "x"], ["B", "2026-01-01", "y"]]],
               [["action @A due 2026-01-02: x"], []]],
              ref("minutes")),
            F("owners", "Given [name, due date, task] actions, return the distinct names sorted alphabetically.",
              "def solve(actions: list) -> list:",
              "def solve(actions):\n    return sorted({name for name, _, _ in actions})\n",
              [[[[["Bram", "d", "t"], ["Ana", "d", "t"], ["Bram", "d", "u"]]], ["Ana", "Bram"]], [[[]], []],
               [[[["X", "d", "t"]]], ["X"]], [[[["b", "d", "t"], ["a", "d", "t"]]], ["a", "b"]]],
              ref("actions")),
            F("overdue", "Given [name, due date, task] actions and today's date, return the number of actions whose due date is before today. Dates are YYYY-MM-DD.",
              "def solve(actions: list, today: str) -> int:",
              "def solve(actions, today):\n    return sum(1 for _, due, _ in actions if due < today)\n",
              [[[[["a", "2026-11-16", "t"], ["b", "2026-11-17", "t"]], "2026-11-17"], 1], [[[], "2026-11-17"], 0],
               [[[["a", "2026-10-01", "t"], ["b", "2025-12-31", "t"]], "2026-01-01"], 1], [[[["a", "2026-12-01", "t"]], "2026-11-17"], 0]],
              ref("actions"), ref("today")),
            F("next_due", "Given [name, due date, task] actions and today's date, return the earliest due date that is today or later, or 'none' if there is none.",
              "def solve(actions: list, today: str) -> str:",
              "def solve(actions, today):\n    later = sorted(due for _, due, _ in actions if due >= today)\n    return later[0] if later else 'none'\n",
              [[[[["a", "2026-11-16", "t"], ["b", "2026-11-20", "t"], ["c", "2026-11-18", "t"]], "2026-11-17"], "2026-11-18"],
               [[[], "2026-11-17"], "none"], [[[["a", "2026-11-17", "t"]], "2026-11-17"], "2026-11-17"],
               [[[["a", "2026-01-01", "t"]], "2026-11-17"], "none"]],
              ref("actions"), ref("today")),
            F("busiest", "Given [name, due date, task] actions, return the name with the most actions. On a tie return the alphabetically first. Return 'none' if there are no actions.",
              "def solve(actions: list) -> str:",
              "def solve(actions):\n    counts = {}\n    for name, _, _ in actions:\n        counts[name] = counts.get(name, 0) + 1\n    if not counts:\n        return 'none'\n    return sorted(counts, key=lambda k: (-counts[k], k))[0]\n",
              [[[[["Bram", "d", "t"], ["Ana", "d", "t"], ["Bram", "d", "u"]]], "Bram"], [[[]], "none"],
               [[[["b", "d", "t"], ["a", "d", "t"]]], "a"], [[[["x", "d", "t"]]], "x"]],
              ref("actions")),
            F("line", "Return '<topic>: <n> owners, <overdue> overdue, next <date>, busiest <name>', where n is the number of owners.",
              "def solve(topic: str, owners: list, overdue: int, next_due: str, busiest: str) -> str:",
              "def solve(topic, owners, overdue, next_due, busiest):\n    return topic + ': ' + str(len(owners)) + ' owners, ' + str(overdue) + ' overdue, next ' + next_due + ', busiest ' + busiest\n",
              [[["billing", ["a", "b"], 1, "2026-11-18", "a"], "billing: 2 owners, 1 overdue, next 2026-11-18, busiest a"],
               [["account", [], 0, "none", "none"], "account: 0 owners, 0 overdue, next none, busiest none"],
               [["t", ["x"], 3, "d", "x"], "t: 1 owners, 3 overdue, next d, busiest x"], [["a", ["b"], 0, "c", "b"], "a: 1 owners, 0 overdue, next c, busiest b"]],
              ref("topic"), ref("owners"), ref("overdue"), ref("next_due"), ref("busiest")),
        ],
        "output": "line",
        "gen": _gen_minutes,
    },
]


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH):
    return _v1.stream(shape, seed, length)


def self_verify():
    import sandbox
    import pipeline

    names = [shape["name"] for shape in SHAPES]
    assert len(names) == len(set(names)), "duplicate shape name"
    assert not set(names) & {shape["name"] for shape in _v1.SHAPES}, "overlaps V1"
    for shape in SHAPES:
        functions = [s for s in shape["steps"] if s["kind"] == "function"]
        assert len(functions) >= 5, f"{shape['name']}: fewer than five function steps"
        for step in functions:
            where = f"{shape['name']}.{step['id']}"
            assert len(step["tests"]) >= 4, f"{where}: fewer than 4 hand-written tests"
            run = sandbox.run_function(step["reference"], [args for args, _ in step["tests"]])
            assert run.ok, f"{where}: reference did not run ({run.error})"
            for result, (args, expected) in zip(run.results, step["tests"]):
                assert result["ok"] and sandbox.canonical(result["value"]) == sandbox.canonical(
                    expected
                ), f"{where}: reference disagrees with hand-written test {args}: {result}"
        instances = stream(shape)
        assert [i for i, _ in instances] == [i for i, _ in stream(shape)], "stream not reproducible"
        judgement_ids = {s["id"] for s in shape["steps"] if s["kind"] == "judgement"}
        for inputs, labels in instances:
            assert set(labels) == judgement_ids, f"{shape['name']}: labels do not match judgement steps"
            pipeline.Job.from_mapping(job_document(shape, inputs))
        gold(shape, instances)
    print(f"self_verify OK: {len(SHAPES)} job shapes, {STREAM_LENGTH} jobs each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_jobs_bench_v2_large.py sha256:", bench_sha256())
