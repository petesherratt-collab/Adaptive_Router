"""Code-only reading rules for ``fast_path_planned_bench_v4.py`` (version 2).

As version 1: written from the task descriptions alone, before any of the
benchmark's texts existed, and hashed in ``BUILD_HISTORY.md`` before the
texts were generated. The only thing known about the texts is that they are
short English messages of the kind each description names. Version 1's
weaknesses (negations, complaint words, place lists) were known when these
were written, so the rules try harder on negation; they were not tuned on any
text of this benchmark.
"""

from __future__ import annotations

import re

NEGATION = r"(?:no|not|never|without|don'?t|do not|didn'?t|did not|isn'?t|wasn'?t|won'?t|nothing)"


def _hits(text, patterns):
    """Count pattern matches that are not negated just before them."""
    total = 0
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            before = text[max(0, match.start() - 25):match.start()]
            if not re.search(rf"\b{NEGATION}\b[^.,;!?]*$", before):
                total += 1
    return total


def _score(text, table, default, order):
    lowered = text.lower()
    counts = {label: _hits(lowered, patterns) for label, patterns in table.items()}
    best = max(counts.values())
    if best == 0:
        return default
    return next(label for label in order if counts[label] == best)


HOTEL = {
    "late_checkout": [r"late check-?out", r"check(?:ing)? out late", r"leave (?:a bit |a little )?later",
                      r"stay (?:in the room )?(?:a bit |a little |until )?(?:later|longer)", r"until (?:1|2|3|4)\s?(?:pm|p\.m\.|o'?clock)",
                      r"\bnoon\b", r"\bafternoon\b", r"keep the room", r"extend (?:our|my) check"],
    "extra_bed": [r"extra bed", r"additional bed", r"\bcot\b", r"\bcrib\b", r"rollaway", r"roll-away",
                  r"sofa ?bed", r"camp bed", r"another bed", r"second bed", r"fold-?out", r"\bbaby\b",
                  r"\btoddler\b", r"third person", r"sleep (?:three|3|four|4)"],
    "airport_transfer": [r"airport", r"transfer", r"shuttle", r"pick(?: us| me)? up", r"pickup", r"pick-up",
                         r"\btaxi\b", r"\bcab\b", r"\bdriver\b", r"\bflight\b", r"\blanding\b", r"\barriv\w+ at",
                         r"terminal", r"\bride\b"],
}


def read_hotel(text):
    return _score(text, HOTEL, "none", ["airport_transfer", "extra_bed", "late_checkout"])


LOCKER = {
    "damaged": [r"damag", r"broken", r"crushed", r"\bdent", r"smashed", r"\btorn\b", r"ripped", r"cracked",
                r"\bwet\b", r"soaked", r"leak", r"shatter", r"squashed", r"open(?:ed)? box", r"tampered"],
    "missing": [r"missing", r"\bempty\b", r"not (?:there|in the locker)", r"wasn'?t (?:there|in)", r"stolen",
                r"\blost\b", r"\bgone\b", r"can'?t find", r"cannot find", r"nothing (?:was )?(?:in|inside)",
                r"never (?:arrived|received|got)", r"no parcel"],
    "delayed": [r"delay", r"\blate\b", r"still (?:not|hasn'?t|waiting)", r"waiting", r"hasn'?t arrived",
                r"not (?:yet )?arrived", r"\bslow\b", r"days? ago", r"overdue", r"expected (?:it )?(?:on|by|yesterday)",
                r"behind schedule", r"took (?:so )?long", r"\bweek\b"],
    "wrong_item": [r"wrong", r"not (?:what|mine|my)", r"someone else'?s", r"different (?:item|parcel|product|size|colou?r)",
                   r"\bmix-?up\b", r"mixed up", r"instead of", r"isn'?t (?:what|mine|my)", r"incorrect", r"not the (?:one|item)"],
}


def read_locker(text):
    return _score(text, LOCKER, "delayed", ["wrong_item", "damaged", "missing", "delayed"])


EFFORT = {
    "high": [r"hard[- ]?work", r"worked (?:really |very |so )?hard", r"diligen", r"excellent effort", r"great effort",
             r"impressive", r"dedicat", r"committed", r"outstanding", r"conscientious", r"put in (?:a lot|real|huge)",
             r"above and beyond", r"motivated", r"engaged", r"enthusias", r"proud", r"tireless", r"focused",
             r"every (?:student|one)", r"keen"],
    "average": [r"average", r"\bsteady\b", r"\badequate\b", r"satisfactory", r"\bmixed\b", r"\bsome\b", r"reasonabl",
                r"\bokay\b", r"\bok\b", r"\bfair\b", r"moderate", r"\bmost\b", r"\bdecent\b", r"middling",
                r"room (?:for|to) improve", r"could (?:do|try) (?:a bit )?(?:more|better)", r"on the whole", r"inconsistent"],
    "low": [r"lazy", r"little effort", r"poor effort", r"lack(?:ed|ing)? (?:of )?(?:effort|focus|motivation)",
            r"disengaged", r"unmotivated", r"didn'?t (?:try|bother|revise|study|prepare)", r"did not (?:try|revise|study|prepare)",
            r"no effort", r"careless", r"distracted", r"disappoint", r"minimal", r"barely", r"missed (?:homework|deadlines|classes)",
            r"\bslack", r"half-?hearted", r"unprepared", r"not (?:enough )?(?:effort|work)"],
}


def read_effort(text):
    lowered = text.lower()
    low = sum(len(re.findall(p, lowered)) for p in EFFORT["low"])  # negations here are the point
    rest = {k: _hits(lowered, v) for k, v in EFFORT.items() if k != "low"}
    counts = {"low": low, **rest}
    best = max(counts.values())
    if best == 0:
        return "average"
    return next(label for label in ("low", "high", "average") if counts[label] == best)


OCCUPANCY = {
    "single": [r"\bi live alone\b", r"live (?:on my own|by myself|alone)", r"\bjust me\b", r"\bonly me\b", r"single",
               r"by myself", r"on my own", r"one-person", r"one person", r"\bsolo\b", r"\balone\b", r"bachelor", r"widow"],
    "couple": [r"\bmy (?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancée|spouse)\b", r"\btwo of us\b",
               r"\bboth of us\b", r"\bcouple\b", r"\bwe two\b", r"\bjust us\b", r"\bthe pair of us\b", r"\bme and my\b",
               r"\btwo people\b", r"\bnewlywed"],
    "family": [r"\bkids?\b", r"\bchildren\b", r"\bchild\b", r"\bfamily\b", r"\bsons?\b", r"\bdaughters?\b", r"\bbaby\b",
               r"\btoddler", r"\bteen", r"\bfour of us\b", r"\bfive of us\b", r"\bthree of us\b", r"\bsix of us\b",
               r"\bgrandparents?\b", r"\bmum and dad\b", r"\bparents\b", r"\bhousehold of (?:three|four|five|six|3|4|5|6)\b",
               r"\bschool\b", r"\bnappies\b", r"\bdiapers\b"],
}


def read_occupancy(text):
    return _score(text, OCCUPANCY, "couple", ["family", "couple", "single"])


FLIGHT = {
    "rebook": [r"rebook", r"re-book", r"next (?:available )?flight", r"later flight", r"another flight", r"different flight",
               r"alternative flight", r"earlier flight", r"\bswitch\b", r"change (?:my|our|the) (?:flight|booking|ticket)",
               r"get (?:me|us) on", r"\bput (?:me|us) on\b", r"\bconnection\b", r"\bconnecting\b", r"\btransfer (?:me|us)\b"],
    "refund": [r"refund", r"money back", r"\breimburse", r"cancel (?:my|our|the) (?:ticket|booking|trip|flight)",
               r"\bcancel\b", r"pay (?:me|us) back", r"return (?:of )?(?:my|the) (?:fare|money)", r"\brepay"],
    "compensation": [r"compensat", r"\bclaim\b", r"\bentitled\b", r"\beu ?261\b", r"\bregulation\b", r"\bdamages\b",
                     r"\bowed\b", r"\bowe (?:me|us)\b", r"make (?:it )?up for", r"\bvoucher\b", r"\bpayout\b", r"\b(?:250|400|600)\b"],
    "information": [r"\bwhen\b", r"\bwhat time\b", r"\bupdate\b", r"\bstatus\b", r"\bwhy\b", r"\binform", r"\bany news\b",
                    r"\bestimated\b", r"\bexpected\b", r"\bwhich gate\b", r"\bgate\b", r"\bhow long\b", r"\?", r"\bknow\b"],
}


def read_flight(text):
    return _score(text, FLIGHT, "information", ["compensation", "refund", "rebook", "information"])


WEATHER = {
    "sunny": [r"\bsun", r"\bsunshine\b", r"\bclear\b", r"\bbright\b", r"\bwarm\b", r"\bhot\b", r"blue sk", r"sunglasses",
              r"sunscreen", r"\bglorious\b", r"\blovely day\b", r"\bbeautiful day\b", r"\bheat\b", r"\bdry\b", r"cloudless"],
    "rainy": [r"\brain", r"\bwet\b", r"\bdrizzl", r"\bpour", r"\bshower", r"\bpuddle", r"\bsoak", r"\bdrench",
              r"\bumbrella\b", r"\bdownpour\b", r"\bstorm\b", r"\bsplash", r"\bwaterproof", r"\bmuddy\b"],
    "windy": [r"\bwind", r"\bgust", r"\bbreez", r"\bblustery\b", r"\bheadwind\b", r"\btailwind\b", r"\bgale\b",
              r"\bblown\b", r"\bblowing\b", r"\bcrosswind\b"],
    "snowy": [r"\bsnow", r"\bice\b", r"\bicy\b", r"\bfrost", r"\bfreez", r"\bsleet\b", r"\bslush", r"\bblizzard\b",
              r"\bwhite-?out\b", r"\bflurr", r"\bgritted\b", r"\bslippery\b"],
}


def read_weather(text):
    return _score(text, WEATHER, "sunny", ["snowy", "rainy", "windy", "sunny"])


EVENT = {
    "fundraiser": [r"fundrais", r"raise (?:money|funds)", r"raising (?:money|funds)", r"donation", r"\bcharity\b",
                   r"\bbake sale\b", r"\braffle\b", r"\bauction\b", r"\bsponsor", r"\bticket", r"\bgala\b", r"\bappeal\b",
                   r"\bstall\b", r"\btarget\b", r"\bcollection buckets?\b"],
    "cleanup": [r"clean-?up", r"clean up", r"\blitter\b", r"\brubbish\b", r"\btrash\b", r"\bbin bags?\b", r"\bgloves\b",
                r"\bbeach\b", r"\bpark\b", r"\briver\b", r"\bpick(?:ing)? up\b", r"\bgraffiti\b", r"\bweeding\b",
                r"\bclear(?:ing)?\b", r"\btidy", r"\bskip\b", r"\blitter-?pick"],
    "food_bank": [r"food ?bank", r"\bfood\b", r"\bparcels?\b", r"\btins?\b", r"\bcans?\b", r"\bgrocer", r"\bpantry\b",
                  r"\bhampers?\b", r"\bmeals?\b", r"\bsorting donations\b", r"\bshelves\b", r"\bhunger\b", r"\bsoup\b",
                  r"\bfood drive\b", r"\bdistribution\b"],
    "tutoring": [r"tutor", r"\bhomework\b", r"\bstudents?\b", r"\bpupils?\b", r"\breading\b", r"\bmaths?\b", r"\bmath\b",
                 r"\blessons?\b", r"\bteach", r"\bliteracy\b", r"\bexams?\b", r"\bschool\b", r"\bspelling\b", r"\bkids\b",
                 r"\blearn", r"\bmentor"],
}


def read_event(text):
    return _score(text, EVENT, "cleanup", ["food_bank", "tutoring", "fundraiser", "cleanup"])


OCCASION = {
    "wedding": [r"wedding", r"\bbride\b", r"\bgroom\b", r"reception", r"\bnuptial", r"getting married", r"\bmarry\b",
                r"\bmarriage\b", r"\bbig day\b", r"\btoast(?:s|ing)? the couple\b", r"\bbest man\b", r"\bbridal\b",
                r"\bvows\b", r"\bhoneymoon\b"],
    "birthday": [r"birthday", r"\bturning \d+", r"\b\d+(?:st|nd|rd|th)\b", r"\bbday\b", r"\bb-day\b", r"\bcandles\b",
                 r"\bcake\b", r"\bparty for (?:my|her|his)\b", r"\bmilestone\b", r"\bsurprise party\b", r"\bbirthday"],
    "corporate": [r"corporate", r"\bcompany\b", r"\boffice\b", r"\bclient", r"\bconference\b", r"\bstaff\b",
                  r"\bemployees?\b", r"\bteam\b", r"\bbusiness\b", r"\binvoice\b", r"\bboard\b", r"\bfirm\b",
                  r"\bcolleagues?\b", r"\bagm\b", r"\bsummit\b", r"\bpurchase order\b", r"\bquarterly\b", r"\bltd\b"],
}


def read_occasion(text):
    return _score(text, OCCASION, "none", ["wedding", "birthday", "corporate"])


RULES = {
    "hotel_stays": read_hotel,
    "parcel_lockers": read_locker,
    "exam_marks": read_effort,
    "energy_meter": read_occupancy,
    "flight_delays": read_flight,
    "bike_rentals": read_weather,
    "volunteer_rota": read_event,
    "wine_orders": read_occasion,
}
