"""Mixed multi-step jobs for the fast-path jobs experiment V1.

Each job shape is a plan of ``judgement`` and ``function`` steps. Gold is by
construction:

* a judgement step's gold label is planted by the input generator, which
  builds each text from a sentence written to carry exactly that label;
* a function step's gold is its reference implementation's output, and the
  reference is qualified by hand-written tests.

Gold for a whole job is obtained by walking the plan with planted labels and
reference outputs. No model decides any gold value.

Run ``python fast_path_jobs_bench_v1.py`` to self-verify and print the SHA-256.
"""

from __future__ import annotations

import json
import random

STREAM_SEED = 20261118
STREAM_LENGTH = 20

TONE = {
    "positive": ["Thank you, this was handled brilliantly.", "I'm really happy with the service.",
                 "Great job, everything works perfectly now.", "Wonderful support, I appreciate the quick help.",
                 "I love how easy this was.", "Fantastic experience from start to finish."],
    "negative": ["This is completely unacceptable.", "I'm very disappointed with the service.",
                 "Terrible experience, I'm furious.", "I am fed up with these constant failures.",
                 "Awful support, nobody helps me.", "I'm extremely frustrated and angry about this."],
    "neutral": ["I'm writing to ask about my request.", "Please see the details below.",
                "I'd like some information.", "This is a routine enquiry.",
                "I am following up on a previous message.", "Here is the information you asked for."],
}
TOPIC = {
    "billing": ["My invoice shows a charge I don't recognise.", "I need a copy of last month's invoice.",
                "The amount on my bill looks different from the quote.",
                "Please update the payment card used for my subscription fee.",
                "I was billed twice this month.", "Can you explain the tax line on my invoice?"],
    "technical": ["The app crashes when I open the settings page.", "The export button does nothing when I click it.",
                  "I get error code 500 when uploading a file.", "The page never finishes loading on my laptop.",
                  "Sync between my phone and tablet has stopped working.", "The software update fails at fifty percent."],
    "account": ["I can't log in because the password reset email never arrives.",
                "Please change the email address on my profile.", "I want to enable two-factor login on my profile.",
                "My username is misspelled on my profile.", "I am locked out after too many login attempts.",
                "How do I delete my user profile?"],
    "shipping": ["The parcel has not arrived yet.", "The courier left the box with a neighbour.",
                 "Tracking says the package is stuck at the depot.", "The delivery arrived with a damaged box.",
                 "I need the parcel delivered to a different address.", "When will the package be dispatched?"],
}
LANGUAGE = {
    "english": ["The meeting starts at nine tomorrow morning.", "Please send me the report before Friday.",
                "We are looking forward to your visit.", "The weather has been lovely this week.",
                "Could you call me back this afternoon?", "The train leaves from platform four."],
    "french": ["La réunion commence à neuf heures demain matin.", "Merci de m'envoyer le rapport avant vendredi.",
               "Nous attendons votre visite avec impatience.", "Il a fait très beau cette semaine.",
               "Pouvez-vous me rappeler cet après-midi ?", "Le train part du quai numéro quatre."],
    "spanish": ["La reunión empieza a las nueve mañana por la mañana.",
                "Por favor, envíeme el informe antes del viernes.", "Esperamos su visita con mucha ilusión.",
                "Ha hecho muy buen tiempo esta semana.", "¿Puede llamarme esta tarde?",
                "El tren sale del andén número cuatro."],
    "german": ["Die Besprechung beginnt morgen früh um neun Uhr.", "Bitte senden Sie mir den Bericht vor Freitag.",
               "Wir freuen uns auf Ihren Besuch.", "Das Wetter war diese Woche sehr schön.",
               "Können Sie mich heute Nachmittag zurückrufen?", "Der Zug fährt von Gleis vier ab."],
}
INTENT = {
    "refund": ["I would like my money back for this purchase.", "Please reimburse me for the faulty item.",
               "I want a refund for the duplicate payment.", "Kindly return the amount I paid.",
               "I'm requesting a refund for my last order."],
    "cancel": ["Please cancel my subscription from next month.", "I want to stop my membership.",
               "End my plan immediately, please.", "I no longer want the service, please cancel it.",
               "Kindly terminate my subscription."],
    "change_address": ["I have moved, please update my delivery address.",
                       "Please send future orders to my new address.", "My street address has changed.",
                       "I need to correct the postcode on my address.", "Update my shipping address to my office."],
    "order_status": ["Where is my order right now?", "Can you tell me when my order will arrive?",
                     "Has my order been dispatched yet?", "I'd like an update on my order.",
                     "What is the current status of my order?"],
}
CITIES = {"Lyon": "France", "Marseille": "France", "Seville": "Spain", "Valencia": "Spain",
          "Hamburg": "Germany", "Munich": "Germany", "Turin": "Italy", "Naples": "Italy",
          "Porto": "Portugal", "Lisbon": "Portugal"}
CITY_NOTES = ["I'll be travelling to {} next week.", "Our office in {} needs the delivery.",
              "Please ship it to the warehouse in {}.", "My colleague from {} placed the order."]
KIND = {
    "animal": ["otter", "heron", "badger", "lizard", "falcon", "donkey", "weasel", "beetle", "rabbit", "parrot"],
    "tool": ["hammer", "wrench", "chisel", "pliers", "screwdriver", "handsaw", "spanner", "trowel", "mallet", "crowbar"],
    "food": ["cheese", "lentils", "bread", "yoghurt", "noodles", "carrot", "butter", "porridge", "biscuit", "mustard"],
}
NAMES = ["Priya", "Marco", "Ingrid", "Tomas", "Aisha", "Kenji", "Lucia", "Bram"]
NAME_NOTES = ["I spoke with {} yesterday about this.", "{} from your team promised a callback.",
              "Your colleague {} handled my last request."]
FILLER = ["please", "check", "thanks", "again", "soon", "update", "today", "regards"]

S_TONE = "Classify the customer's tone in the text as exactly one of 'positive', 'negative' or 'neutral'."
S_TOPIC = "Classify what the text is about as exactly one of 'billing', 'technical', 'account' or 'shipping'."
S_LANGUAGE = "Identify the language the text is written in as exactly one of 'english', 'french', 'spanish' or 'german'."
S_INTENT = "Classify what the customer wants as exactly one of 'refund', 'cancel', 'change_address' or 'order_status'."
S_CITY = "Return the name of the city mentioned in the text, exactly as written there."
S_COUNTRY = "Return the name, in English, of the country in which the given city is located."
S_KIND = "Classify the thing named by the word as exactly one of 'animal', 'tool' or 'food'."
S_NAME = "Return the first name of the staff member mentioned in the text, exactly as written there."
TEXT_SIG = "def solve(text: str) -> str:"


def _pick(r, table):
    label = r.choice(sorted(table))
    return label, r.choice(table[label])


def J(step_id, spec, *args, signature=TEXT_SIG):
    return {"id": step_id, "kind": "judgement", "spec": spec, "signature": signature, "args": list(args)}


def F(step_id, spec, signature, reference, tests, *args):
    return {"id": step_id, "kind": "function", "spec": spec, "signature": signature,
            "reference": reference, "tests": tests, "args": list(args)}


def ref(name):
    return {"ref": name}


def _gen_ticket(r):
    tone, opening = _pick(r, TONE)
    topic, body = _pick(r, TOPIC)
    refs = [f"TKT-{r.randint(1000, 9999)}" for _ in range(r.randint(0, 3))]
    if refs and r.random() < 0.3:
        refs.append(refs[0])
    notes = " ".join(f"{r.choice(FILLER)} {code}" for code in refs) or r.choice(FILLER)
    return {"opening": opening, "body": body, "notes": notes}, {"tone": tone, "topic": topic}


def _gen_language_queue(r):
    language, text = _pick(r, LANGUAGE)
    intent, request = _pick(r, INTENT)
    return {"text": text, "request": request}, {"language": language, "intent": intent}


def _gen_shipping(r):
    city = r.choice(sorted(CITIES))
    return ({"note": r.choice(CITY_NOTES).format(city), "weight_kg": r.randint(1, 40)}, {"city": city})


def _gen_aisle(r):
    kind = r.choice(sorted(KIND))
    return {"item": r.choice(KIND[kind]), "quantity": r.randint(1, 12)}, {"kind": kind}


def _gen_escalation(r):
    tone, opening = _pick(r, TONE)
    name = r.choice(NAMES)
    return ({"opening": opening, "mention": r.choice(NAME_NOTES).format(name),
             "amount": r.randint(0, 300)}, {"tone": tone, "agent": name})


def _gen_refund(r):
    intent, request = _pick(r, INTENT)
    euros, cents = r.randint(0, 120), r.choice([0, 5, 50, 90, 99])
    price = r.choice([f"€{euros}.{cents:02d}", f"{euros},{cents:02d} EUR", f"€ {euros},{cents:02d}",
                      f"EUR {euros}.{cents:02d}"])
    return {"request": request, "price": price}, {"intent": intent}


def _gen_greeting(r):
    language, text = _pick(r, LANGUAGE)
    words = r.sample(NAMES, r.randint(1, 2))
    name = " ".join(r.choice([w.upper(), w.lower(), w.swapcase()]) for w in words)
    return {"text": text, "name": name}, {"language": language}


def _gen_digest(r):
    topic, body = _pick(r, TOPIC)
    tags = r.sample(["late", "refund", "urgent", "vip", "bug42", "q3"], r.randint(0, 4))
    if tags and r.random() < 0.4:
        tags.append(tags[0])
    tagline = " ".join("#" + r.choice([t, t.upper(), t.capitalize()]) for t in tags) or "no tags here"
    return {"body": body, "tagline": tagline}, {"topic": topic}


def _gen_score(r):
    tone, opening = _pick(r, TONE)
    remark = " ".join(r.choice(FILLER) + "!" * r.choice([0, 0, 1, 1, 2]) for _ in range(r.randint(1, 4)))
    return {"opening": opening, "remark": remark}, {"tone": tone}


def _gen_dial(r):
    city = r.choice(sorted(CITIES))
    local = "".join(str(r.randint(0, 9)) for _ in range(r.randint(7, 9)))
    return ({"note": r.choice(CITY_NOTES).format(city), "local": local},
            {"city": city, "country": CITIES[city]})


def _gen_triple(r):
    language, text = _pick(r, LANGUAGE)
    intent, request = _pick(r, INTENT)
    tone, opening = _pick(r, TONE)
    return ({"text": text, "request": request, "opening": opening},
            {"language": language, "intent": intent, "tone": tone})


def _gen_pair(r):
    kind_a, kind_b = r.choice(sorted(KIND)), r.choice(sorted(KIND))
    first = r.choice(KIND[kind_a])
    second = r.choice([w for w in KIND[kind_b] if w != first])
    return {"first": first, "second": second}, {"kind_a": kind_a, "kind_b": kind_b}


SHAPES = [
    {
        "name": "ticket_sla",
        "steps": [
            J("tone", S_TONE, ref("opening")),
            J("topic", S_TOPIC, ref("body")),
            F("refs", "Return every ticket reference in the text, in order of first appearance and without duplicates. A ticket reference is the letters TKT, a hyphen, then exactly four digits, such as TKT-1234.",
              "def solve(text: str) -> list:",
              "import re\ndef solve(text):\n    out = []\n    for code in re.findall(r'TKT-\\d{4}(?!\\d)', text):\n        if code not in out:\n            out.append(code)\n    return out\n",
              [[["see TKT-1234 and TKT-9999"], ["TKT-1234", "TKT-9999"]], [["nothing here"], []],
               [["TKT-1111 again TKT-1111"], ["TKT-1111"]], [["TKT-2000, TKT-1000."], ["TKT-2000", "TKT-1000"]]],
              ref("notes")),
            F("sla", "Return the response deadline in hours: 4 if the tone is 'negative' and the topic is 'billing'; 8 if the tone is 'negative' and the topic is anything else; 24 if the tone is 'neutral'; 48 if the tone is 'positive'.",
              "def solve(tone: str, topic: str) -> int:",
              "def solve(tone, topic):\n    if tone == 'negative':\n        return 4 if topic == 'billing' else 8\n    return 24 if tone == 'neutral' else 48\n",
              [[["negative", "billing"], 4], [["negative", "shipping"], 8], [["neutral", "billing"], 24],
               [["positive", "account"], 48], [["negative", "technical"], 8]],
              ref("tone"), ref("topic")),
            F("line", "Return a summary line of the form '<hours>h | <topic> | <count> refs', where count is the number of references in the list. Write 'ref' instead of 'refs' when the count is exactly 1. Example: '4h | billing | 2 refs'.",
              "def solve(hours: int, topic: str, refs: list) -> str:",
              "def solve(hours, topic, refs):\n    word = 'ref' if len(refs) == 1 else 'refs'\n    return str(hours) + 'h | ' + topic + ' | ' + str(len(refs)) + ' ' + word\n",
              [[[4, "billing", ["TKT-1", "TKT-2"]], "4h | billing | 2 refs"], [[24, "account", ["TKT-1"]], "24h | account | 1 ref"],
               [[8, "shipping", []], "8h | shipping | 0 refs"], [[48, "technical", ["a", "b", "c"]], "48h | technical | 3 refs"]],
              ref("sla"), ref("topic"), ref("refs")),
        ],
        "output": "line",
        "gen": _gen_ticket,
    },
    {
        "name": "language_queue",
        "steps": [
            J("language", S_LANGUAGE, ref("text")),
            J("intent", S_INTENT, ref("request")),
            F("queue", "Return a queue name: the language code in uppercase, a hyphen, then the intent unchanged. Language codes: english is EN, french is FR, spanish is ES, german is DE. Example: 'FR-refund'.",
              "def solve(language: str, intent: str) -> str:",
              "def solve(language, intent):\n    codes = {'english': 'EN', 'french': 'FR', 'spanish': 'ES', 'german': 'DE'}\n    return codes[language] + '-' + intent\n",
              [[["french", "refund"], "FR-refund"], [["english", "cancel"], "EN-cancel"],
               [["spanish", "order_status"], "ES-order_status"], [["german", "change_address"], "DE-change_address"]],
              ref("language"), ref("intent")),
            F("words", "Return the number of whitespace-separated words in the text.",
              "def solve(text: str) -> int:",
              "def solve(text):\n    return len(text.split())\n",
              [[["one two three"], 3], [[""], 0], [["  spaced   out "], 2], [["¿Puede llamarme esta tarde?"], 4]],
              ref("text")),
            F("ticket", "Return an object with two keys: 'queue' holding the first argument and 'words' holding the second.",
              "def solve(queue: str, words: int) -> dict:",
              "def solve(queue, words):\n    return {'queue': queue, 'words': words}\n",
              [[["FR-refund", 7], {"queue": "FR-refund", "words": 7}], [["EN-cancel", 0], {"queue": "EN-cancel", "words": 0}],
               [["a", 1], {"queue": "a", "words": 1}], [["DE-x", 12], {"queue": "DE-x", "words": 12}]],
              ref("queue"), ref("words")),
        ],
        "output": "ticket",
        "gen": _gen_language_queue,
    },
    {
        "name": "shipping_estimate",
        "steps": [
            J("city", S_CITY, ref("note")),
            F("zone", "Return the delivery zone for a city: 'A' for Lyon, Marseille, Turin and Naples; 'B' for Seville, Valencia, Porto and Lisbon; 'C' for any other city.",
              "def solve(city: str) -> str:",
              "def solve(city):\n    if city in ('Lyon', 'Marseille', 'Turin', 'Naples'):\n        return 'A'\n    if city in ('Seville', 'Valencia', 'Porto', 'Lisbon'):\n        return 'B'\n    return 'C'\n",
              [[["Lyon"], "A"], [["Porto"], "B"], [["Hamburg"], "C"], [["Naples"], "A"], [["Oslo"], "C"]],
              ref("city")),
            F("days", "Return the delivery time in days: zone 'A' takes 2, zone 'B' takes 4 and zone 'C' takes 6. Add 1 day if the weight in kilograms is greater than 20.",
              "def solve(zone: str, weight_kg: int) -> int:",
              "def solve(zone, weight_kg):\n    return {'A': 2, 'B': 4, 'C': 6}[zone] + (1 if weight_kg > 20 else 0)\n",
              [[["A", 5], 2], [["A", 21], 3], [["B", 20], 4], [["C", 40], 7], [["C", 1], 6]],
              ref("zone"), ref("weight_kg")),
            F("estimate", "Return the sentence '<city>: zone <zone>, <days> days'. Example: 'Lyon: zone A, 2 days'.",
              "def solve(city: str, zone: str, days: int) -> str:",
              "def solve(city, zone, days):\n    return city + ': zone ' + zone + ', ' + str(days) + ' days'\n",
              [[["Lyon", "A", 2], "Lyon: zone A, 2 days"], [["Porto", "B", 5], "Porto: zone B, 5 days"],
               [["Munich", "C", 7], "Munich: zone C, 7 days"], [["X", "A", 3], "X: zone A, 3 days"]],
              ref("city"), ref("zone"), ref("days")),
        ],
        "output": "estimate",
        "gen": _gen_shipping,
    },
    {
        "name": "store_aisle",
        "steps": [
            J("kind", S_KIND, ref("item"), signature="def solve(word: str) -> str:"),
            F("aisle", "Return the shop aisle for a kind of thing: 'pets' for 'animal', 'hardware' for 'tool' and 'grocery' for 'food'.",
              "def solve(kind: str) -> str:",
              "def solve(kind):\n    return {'animal': 'pets', 'tool': 'hardware', 'food': 'grocery'}[kind]\n",
              [[["animal"], "pets"], [["tool"], "hardware"], [["food"], "grocery"], [["animal"], "pets"]],
              ref("kind")),
            F("label", "Return a shelf label of the form '<quantity> x <ITEM> -> <aisle>' with the item name in uppercase. Example: '3 x OTTER -> pets'.",
              "def solve(quantity: int, item: str, aisle: str) -> str:",
              "def solve(quantity, item, aisle):\n    return str(quantity) + ' x ' + item.upper() + ' -> ' + aisle\n",
              [[[3, "otter", "pets"], "3 x OTTER -> pets"], [[1, "bread", "grocery"], "1 x BREAD -> grocery"],
               [[12, "Wrench", "hardware"], "12 x WRENCH -> hardware"], [[7, "a", "b"], "7 x A -> b"]],
              ref("quantity"), ref("item"), ref("aisle")),
        ],
        "output": "label",
        "gen": _gen_aisle,
    },
    {
        "name": "escalation",
        "steps": [
            J("tone", S_TONE, ref("opening")),
            J("agent", S_NAME, ref("mention")),
            F("tag", "Return the first letter of the name in uppercase followed by the number of letters in the name. Example: 'Priya' gives 'P5'.",
              "def solve(name: str) -> str:",
              "def solve(name):\n    return name[0].upper() + str(len(name))\n",
              [[["Priya"], "P5"], [["bram"], "B4"], [["Ingrid"], "I6"], [["Al"], "A2"]],
              ref("agent")),
            F("escalate", "Return true if the tone is 'negative' and the amount is greater than 100; otherwise return false.",
              "def solve(tone: str, amount: int) -> bool:",
              "def solve(tone, amount):\n    return tone == 'negative' and amount > 100\n",
              [[["negative", 101], True], [["negative", 100], False], [["positive", 500], False],
               [["neutral", 250], False], [["negative", 300], True]],
              ref("tone"), ref("amount")),
            F("case", "Return an object with two keys: 'agent' holding the first argument and 'escalate' holding the second.",
              "def solve(agent: str, escalate: bool) -> dict:",
              "def solve(agent, escalate):\n    return {'agent': agent, 'escalate': escalate}\n",
              [[["P5", True], {"agent": "P5", "escalate": True}], [["B4", False], {"agent": "B4", "escalate": False}],
               [["x", True], {"agent": "x", "escalate": True}], [["I6", False], {"agent": "I6", "escalate": False}]],
              ref("tag"), ref("escalate")),
        ],
        "output": "case",
        "gen": _gen_escalation,
    },
    {
        "name": "refund_decision",
        "steps": [
            J("intent", S_INTENT, ref("request")),
            F("cents", "Convert a price string to a whole number of cents. The string may contain a euro sign or the letters EUR and spaces, and a number that uses either a dot or a comma as the decimal separator with zero, one or two decimal digits. '€12.50', '12,5 EUR' and '12' give 1250, 1250 and 1200.",
              "def solve(price: str) -> int:",
              "def solve(price):\n    cleaned = ''.join(ch for ch in price if ch.isdigit() or ch in '.,').replace(',', '.')\n    whole, _, frac = cleaned.partition('.')\n    return int(whole) * 100 + int((frac + '00')[:2])\n",
              [[["€12.50"], 1250], [["12,5 EUR"], 1250], [["12"], 1200], [["0.99"], 99],
               [["EUR 7,05"], 705], [["€ 100"], 10000]],
              ref("price")),
            F("decision", "Return 'auto' if the intent is 'refund' and the amount is at most 5000 cents; 'review' if the intent is 'refund' and the amount is more than 5000 cents; otherwise 'none'.",
              "def solve(intent: str, cents: int) -> str:",
              "def solve(intent, cents):\n    if intent != 'refund':\n        return 'none'\n    return 'auto' if cents <= 5000 else 'review'\n",
              [[["refund", 5000], "auto"], [["refund", 5001], "review"], [["cancel", 100], "none"],
               [["refund", 0], "auto"], [["order_status", 9999], "none"]],
              ref("intent"), ref("cents")),
            F("outcome", "Return the decision, a colon, then the number of cents. Example: 'auto:1250'.",
              "def solve(decision: str, cents: int) -> str:",
              "def solve(decision, cents):\n    return decision + ':' + str(cents)\n",
              [[["auto", 1250], "auto:1250"], [["none", 0], "none:0"], [["review", 12000], "review:12000"],
               [["x", 5], "x:5"]],
              ref("decision"), ref("cents")),
        ],
        "output": "outcome",
        "gen": _gen_refund,
    },
    {
        "name": "greeting",
        "steps": [
            J("language", S_LANGUAGE, ref("text")),
            F("hello", "Return the greeting for a language: 'Hello' for 'english', 'Bonjour' for 'french', 'Hola' for 'spanish' and 'Guten Tag' for 'german'.",
              "def solve(language: str) -> str:",
              "def solve(language):\n    return {'english': 'Hello', 'french': 'Bonjour', 'spanish': 'Hola', 'german': 'Guten Tag'}[language]\n",
              [[["english"], "Hello"], [["french"], "Bonjour"], [["spanish"], "Hola"], [["german"], "Guten Tag"]],
              ref("language")),
            F("nice_name", "Fix the letter case of a name: in each space-separated word make the first letter uppercase and the rest lowercase.",
              "def solve(name: str) -> str:",
              "def solve(name):\n    return ' '.join(w[:1].upper() + w[1:].lower() for w in name.split(' '))\n",
              [[["mARIE dupont"], "Marie Dupont"], [["JOHN"], "John"], [["ana maria lopez"], "Ana Maria Lopez"], [["o"], "O"]],
              ref("name")),
            F("salute", "Return the greeting, a comma and a space, the name, then an exclamation mark. Example: 'Hola, Ana Lopez!'.",
              "def solve(greeting: str, name: str) -> str:",
              "def solve(greeting, name):\n    return greeting + ', ' + name + '!'\n",
              [[["Hola", "Ana Lopez"], "Hola, Ana Lopez!"], [["Guten Tag", "Bram"], "Guten Tag, Bram!"],
               [["Hello", "X"], "Hello, X!"], [["Bonjour", "Marie Dupont"], "Bonjour, Marie Dupont!"]],
              ref("hello"), ref("nice_name")),
        ],
        "output": "salute",
        "gen": _gen_greeting,
    },
    {
        "name": "topic_digest",
        "steps": [
            J("topic", S_TOPIC, ref("body")),
            F("tags", "Return the distinct hashtags in the text, lowercased, without the # sign and sorted alphabetically. A hashtag is a # followed by one or more letters or digits.",
              "def solve(text: str) -> list:",
              "import re\ndef solve(text):\n    return sorted(set(m.lower() for m in re.findall(r'#([A-Za-z0-9]+)', text)))\n",
              [[["#Late #refund #late"], ["late", "refund"]], [["no tags"], []], [["#a1 and #B2, #a1."], ["a1", "b2"]],
               [["#Zeta#alpha"], ["alpha", "zeta"]], [["# alone"], []]],
              ref("tagline")),
            F("digest", "Return the topic, a colon, then the tags joined by '|'. If there are no tags write 'none' after the colon. Examples: 'billing:late|refund' and 'account:none'.",
              "def solve(topic: str, tags: list) -> str:",
              "def solve(topic, tags):\n    return topic + ':' + ('|'.join(tags) if tags else 'none')\n",
              [[["billing", ["late", "refund"]], "billing:late|refund"], [["account", []], "account:none"],
               [["shipping", ["vip"]], "shipping:vip"], [["t", ["a", "b", "c"]], "t:a|b|c"]],
              ref("topic"), ref("tags")),
        ],
        "output": "digest",
        "gen": _gen_digest,
    },
    {
        "name": "tone_score",
        "steps": [
            J("tone", S_TONE, ref("opening")),
            F("bangs", "Return the number of exclamation marks in the text.",
              "def solve(text: str) -> int:",
              "def solve(text):\n    return text.count('!')\n",
              [[["wow! ok!"], 2], [["calm"], 0], [["!!!"], 3], [["a!b"], 1]],
              ref("remark")),
            F("score", "Return a score. Start from 2 for tone 'positive', 0 for 'neutral' and -2 for 'negative'. For 'positive' add the count; for 'negative' subtract the count; for 'neutral' ignore the count. Then limit the result to the range -5 to 5.",
              "def solve(tone: str, count: int) -> int:",
              "def solve(tone, count):\n    if tone == 'positive':\n        value = 2 + count\n    elif tone == 'negative':\n        value = -2 - count\n    else:\n        value = 0\n    return max(-5, min(5, value))\n",
              [[["positive", 0], 2], [["positive", 5], 5], [["negative", 1], -3], [["negative", 9], -5],
               [["neutral", 4], 0], [["positive", 3], 5]],
              ref("tone"), ref("bangs")),
        ],
        "output": "score",
        "gen": _gen_score,
    },
    {
        "name": "dial_code",
        "steps": [
            J("city", S_CITY, ref("note")),
            J("country", S_COUNTRY, ref("city"), signature="def solve(city: str) -> str:"),
            F("dial", "Return the telephone country code for a country: '+33' for France, '+34' for Spain, '+49' for Germany, '+39' for Italy, '+351' for Portugal, and '+00' for any other country.",
              "def solve(country: str) -> str:",
              "def solve(country):\n    return {'France': '+33', 'Spain': '+34', 'Germany': '+49', 'Italy': '+39', 'Portugal': '+351'}.get(country, '+00')\n",
              [[["France"], "+33"], [["Portugal"], "+351"], [["Germany"], "+49"], [["Norway"], "+00"], [["Italy"], "+39"]],
              ref("country")),
            F("phone", "Return the dial code, a space, then the local digits split into groups of three separated by single spaces. The last group may be shorter. Example: '+33' and '612345678' give '+33 612 345 678'.",
              "def solve(dial: str, local: str) -> str:",
              "def solve(dial, local):\n    return dial + ' ' + ' '.join(local[i:i + 3] for i in range(0, len(local), 3))\n",
              [[["+33", "612345678"], "+33 612 345 678"], [["+351", "91234567"], "+351 912 345 67"],
               [["+49", "1"], "+49 1"], [["+34", "123456"], "+34 123 456"]],
              ref("dial"), ref("local")),
        ],
        "output": "phone",
        "gen": _gen_dial,
    },
    {
        "name": "triple_code",
        "steps": [
            J("language", S_LANGUAGE, ref("text")),
            J("intent", S_INTENT, ref("request")),
            J("tone", S_TONE, ref("opening")),
            F("code", "Return a code made of the first two letters of the language, a hyphen, the first three letters of the intent, a hyphen and the first letter of the tone, all in uppercase. Example: 'french', 'refund' and 'negative' give 'FR-REF-N'.",
              "def solve(language: str, intent: str, tone: str) -> str:",
              "def solve(language, intent, tone):\n    return (language[:2] + '-' + intent[:3] + '-' + tone[:1]).upper()\n",
              [[["french", "refund", "negative"], "FR-REF-N"], [["english", "cancel", "positive"], "EN-CAN-P"],
               [["spanish", "change_address", "neutral"], "SP-CHA-N"], [["german", "order_status", "negative"], "GE-ORD-N"]],
              ref("language"), ref("intent"), ref("tone")),
        ],
        "output": "code",
        "gen": _gen_triple,
    },
    {
        "name": "item_pair",
        "steps": [
            J("kind_a", S_KIND, ref("first"), signature="def solve(word: str) -> str:"),
            J("kind_b", S_KIND, ref("second"), signature="def solve(word: str) -> str:"),
            F("same", "Return true if the two kinds are equal, otherwise false.",
              "def solve(kind_a: str, kind_b: str) -> bool:",
              "def solve(kind_a, kind_b):\n    return kind_a == kind_b\n",
              [[["animal", "animal"], True], [["animal", "tool"], False], [["food", "food"], True], [["tool", "food"], False]],
              ref("kind_a"), ref("kind_b")),
            F("advice", "Return '<first> and <second> go together' if the flag is true, otherwise '<first> and <second> are kept apart'.",
              "def solve(first: str, second: str, together: bool) -> str:",
              "def solve(first, second, together):\n    return first + ' and ' + second + (' go together' if together else ' are kept apart')\n",
              [[["otter", "heron", True], "otter and heron go together"], [["otter", "bread", False], "otter and bread are kept apart"],
               [["a", "b", True], "a and b go together"], [["x", "y", False], "x and y are kept apart"]],
              ref("first"), ref("second"), ref("same")),
        ],
        "output": "advice",
        "gen": _gen_pair,
    },
]


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH):
    """Return ``length`` distinct ``(inputs, labels)`` pairs fixed by ``seed``."""
    rng = random.Random(f"{seed}:{shape['name']}")
    seen, out = set(), []
    for _ in range(length * 400):
        inputs, labels = shape["gen"](rng)
        key = json.dumps(inputs, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append((inputs, labels))
            if len(out) == length:
                return out
    raise ValueError(f"{shape['name']}: generator cannot supply {length} distinct inputs")


def job_document(shape, inputs):
    """The ``fast_path_job_v1`` document for one request of a shape."""
    return {
        "schema_version": "fast_path_job_v1",
        "inputs": inputs,
        "steps": [
            {"id": s["id"], "kind": s["kind"],
             "task": {"spec": s["spec"], "signature": s["signature"]}, "args": s["args"]}
            for s in shape["steps"]
        ],
        "output": shape["output"],
    }


def gold(shape, instances):
    """Gold value of every step for each ``(inputs, labels)`` instance.

    Judgement steps take their planted label. Function steps take the
    reference output, computed in the sandbox one step at a time.
    """
    import sandbox

    values = [dict(inputs) for inputs, _ in instances]
    for step in shape["steps"]:
        if step["kind"] == "judgement":
            for value, (_, labels) in zip(values, instances):
                value[step["id"]] = labels[step["id"]]
            continue
        calls = [[v[a["ref"]] if "ref" in a else a["value"] for a in step["args"]] for v in values]
        run = sandbox.run_function(step["reference"], calls, timeout_seconds=10.0)
        if not run.ok or not all(r["ok"] for r in run.results):
            raise ValueError(f"{shape['name']}.{step['id']}: reference failed on a generated input")
        for value, result in zip(values, run.results):
            value[step["id"]] = result["value"]
    return values


def self_verify():
    import sandbox
    import pipeline

    names = [shape["name"] for shape in SHAPES]
    assert len(names) == len(set(names)), "duplicate shape name"
    for shape in SHAPES:
        for step in shape["steps"]:
            if step["kind"] != "function":
                continue
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
    print("fast_path_jobs_bench_v1.py sha256:", bench_sha256())
