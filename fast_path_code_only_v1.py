"""Code-only reading rules for ``fast_path_planned_bench_v3.py`` (version 1).

The code-only arm stands for a programmer who writes ordinary code for the
whole job, including the reading step, with no model at all. Its mechanical
work is the benchmark's reference function (as in the ceiling arm); its
reading step is the keyword rules below.

Written from the task descriptions alone, before any of the benchmark's texts
existed: the prose was written afterwards by a model outside the race roster,
from the prompt in ``make_bench_v3_prose.py``, and this file's SHA-256
was recorded in ``BUILD_HISTORY.md`` first. The only thing known about the
texts was that they are short English messages of the kind each description
names. The rules are what a programmer would write from general knowledge:
keyword lists scored per label, ties and no match going to a stated default.
"""

from __future__ import annotations

import re


def _score(text, table, default, order=None):
    """Return the label whose patterns match most often; ``default`` on no
    match; on a tie, the label listed first in ``order`` (or the table)."""
    lowered = text.lower()
    counts = {label: sum(len(re.findall(p, lowered)) for p in patterns)
              for label, patterns in table.items()}
    best = max(counts.values())
    if best == 0:
        return default
    for label in order or table:
        if counts[label] == best:
            return label
    return default


URGENCY = {
    "urgent": [r"\burgent", r"\basap\b", r"as soon as possible", r"\bimmediately\b", r"right away",
               r"\bemergency\b", r"\bcritical\b", r"\bdown\b", r"\boutage\b", r"\bcannot\b", r"\bcan't\b",
               r"\bcan not\b", r"\bunable\b", r"not working", r"\bbroken\b", r"\bstopped\b",
               r"\bblocked\b", r"\bblocking\b", r"\bstuck\b", r"\bcrash", r"\bfailing\b", r"\bfailed\b",
               r"\bdeadline\b", r"\btoday\b", r"\bnow\b", r"\bhelp!", r"!!", r"\bsecurity\b",
               r"\bbreach\b", r"\bdata loss\b", r"\blost\b", r"\bpayroll\b", r"\bcustomers? (are|can)",
               r"\bproduction\b", r"\bhigh priority\b", r"\bserious\b", r"\bvery important\b"],
    "routine": [r"\bwhen you (have|get) (a|the) (chance|moment)", r"\bno rush\b", r"\bno hurry\b",
                r"\bwhenever\b", r"\bat your convenience\b", r"\bquestion\b", r"\bwondering\b",
                r"\bcurious\b", r"\bminor\b", r"\bsmall\b", r"\bjust\b", r"\bnot urgent\b",
                r"\blow priority\b", r"\bfyi\b", r"\bsuggest", r"\bfeature request\b", r"\bfeedback\b",
                r"\bnext week\b", r"\beventually\b", r"\bwould like to know\b", r"\bcould you\b",
                r"\bhow do i\b", r"\bupdate my\b", r"\bchange my\b"],
}


def read_urgency(text):
    lowered = text.lower()
    if re.search(r"\b(not urgent|no rush|no hurry|low priority|whenever|at your convenience)\b", lowered):
        return "routine"
    return _score(text, URGENCY, "routine", order=["urgent", "routine"])


DEPARTMENT = {
    "sales": [r"\bsales?\b", r"\bclients?\b", r"\bcustomers?\b", r"\bprospects?\b", r"\bleads?\b",
              r"\bdeals?\b", r"\bpitch", r"\bdemo\b", r"\bquota\b", r"\bpipeline\b", r"\baccounts? manager",
              r"\bcrm\b", r"\brenewal", r"\bupsell", r"\bproposal\b", r"\bpricing\b", r"\bdiscount",
              r"\bterritory\b", r"\bcommission", r"\bbuyers?\b", r"\bpurchas"],
    "engineering": [r"\bengineer", r"\bcode\b", r"\bcodebase\b", r"\bdeploy", r"\brelease\b",
                    r"\bsprint\b", r"\bbugs?\b", r"\barchitecture\b", r"\bdesign review\b", r"\bapi\b",
                    r"\bservers?\b", r"\bdatabase\b", r"\bsoftware\b", r"\bdevelop", r"\bprototype",
                    r"\bfirmware\b", r"\bbuild\b", r"\btesting\b", r"\btechnical\b", r"\bsystem\b",
                    r"\bstand-?up\b", r"\bpull request", r"\binfrastructure\b", r"\bhardware\b",
                    r"\bschematic", r"\bdebug", r"\bbackend\b", r"\bfrontend\b"],
    "finance": [r"\bfinanc", r"\bbudget", r"\bforecast", r"\binvoices?\b", r"\bpayroll\b", r"\baudit",
                r"\baccounts? payable\b", r"\baccounts? receivable\b", r"\baccounting\b", r"\bledger\b",
                r"\bquarter(ly)? (close|results|figures|numbers)", r"\bexpenses?\b", r"\btax\b",
                r"\bcash ?flow\b", r"\breconcil", r"\bbalance sheet\b", r"\bp&l\b", r"\bprofit\b",
                r"\brevenue\b", r"\bspreadsheet", r"\bfiscal\b", r"\bcfo\b", r"\bcosts?\b",
                r"\bmonth-end\b", r"\byear-end\b", r"\bspend\b"],
    "legal": [r"\blegal\b", r"\blawyers?\b", r"\battorneys?\b", r"\bcounsel\b", r"\bcontracts?\b",
              r"\bclauses?\b", r"\blitigation\b", r"\bcompliance\b", r"\bregulat", r"\bnda\b",
              r"\bnon-disclosure\b", r"\btrademark", r"\bpatent", r"\bintellectual property\b",
              r"\bgdpr\b", r"\bprivacy\b", r"\bliabilit", r"\bdispute\b", r"\blawsuit\b", r"\bcourt\b",
              r"\bterms and conditions\b", r"\bsettlement\b", r"\bnegotiat", r"\bpolicy\b",
              r"\bsigned\b", r"\bsignature\b", r"\bdue diligence\b", r"\bsubpoena\b"],
}


def read_department(text):
    return _score(text, DEPARTMENT, "sales", order=["legal", "finance", "engineering", "sales"])


VEGAN = [r"\bvegan", r"\bplant-based\b", r"\bplant based\b", r"\bno animal products\b",
         r"\bno (meat|fish)?,? ?(or |nor )?(dairy|eggs)\b", r"\bdairy-free\b", r"\bdairy free\b",
         r"\bno dairy\b", r"\bwithout dairy\b", r"\bnothing from an animal\b",
         r"\bno animal\b", r"\blactose", r"\bdon'?t (eat|have) (any )?(dairy|cheese|milk|butter)",
         r"\bavoid (all )?(dairy|animal)"]
VEGETARIAN = [r"\bvegetarian", r"\bveggie\b", r"\bno meat\b", r"\bmeat-free\b", r"\bmeat free\b",
              r"\bdon'?t eat meat\b", r"\bdo not eat meat\b", r"\bwithout meat\b", r"\bno fish\b",
              r"\bpescatarian\b", r"\bmeatless\b", r"\bdon'?t eat (any )?(meat|fish|chicken|beef|pork)",
              r"\bavoid (meat|fish)"]
ANY = [r"\beat (anything|everything)\b", r"\bno (dietary )?restrictions\b", r"\bnot fussy\b",
       r"\bomnivore\b", r"\bno allergies\b", r"\bhappy (to eat|with) (anything|whatever)\b",
       r"\bwhatever\b", r"\bmeat lover\b", r"\bany(thing)? (is|goes) fine\b"]


def read_diet(text):
    lowered = text.lower()
    if any(re.search(p, lowered) for p in VEGAN):
        return "vegan"
    if any(re.search(p, lowered) for p in VEGETARIAN):
        return "vegetarian"
    return "any"


ISSUE = {
    "tyres": [r"\btyres?\b", r"\btires?\b", r"\bpuncture", r"\bflat\b", r"\btread\b", r"\bpressure\b",
              r"\bwheels?\b", r"\bblow-?out\b", r"\bslow leak\b", r"\bpulls? to (the )?(left|right)\b",
              r"\bbulge\b", r"\bnail\b", r"\balignment\b"],
    "brakes": [r"\bbrak", r"\bpads?\b", r"\bdiscs?\b", r"\brotors?\b", r"\bsqueal", r"\bgrind",
               r"\bstopping\b", r"\bpedal\b", r"\bspongy\b", r"\bsoft pedal\b", r"\babs\b",
               r"\bhandbrake\b", r"\bparking brake\b", r"\btakes longer to stop\b"],
    "engine": [r"\bengine\b", r"\bmotor\b", r"\bstall", r"\bmisfir", r"\boverheat", r"\btemperature\b",
               r"\bcheck engine\b", r"\bwarning light\b", r"\bsmoke\b", r"\bexhaust\b", r"\boil\b",
               r"\bcoolant\b", r"\bknock", r"\brattl", r"\bhesitat", r"\bpower loss\b", r"\bloss of power\b",
               r"\bsputter", r"\bwon'?t start\b", r"\bstarting\b", r"\bidle\b", r"\bidling\b",
               r"\bturbo\b", r"\bfuel pump\b", r"\bspark", r"\bradiator\b", r"\brevs?\b"],
}
NO_ISSUE = [r"\bno (issues?|problems?|faults?)\b", r"\bnothing to report\b", r"\ball (good|fine|ok)\b",
            r"\bran (fine|well|smoothly)\b", r"\bruns? (fine|well|smoothly)\b", r"\bwithout (any )?(issue|problem)",
            r"\bno complaints\b", r"\bnothing (unusual|wrong)\b", r"\buneventful\b", r"\bsmooth\b"]


def read_issue(text):
    lowered = text.lower()
    label = _score(text, ISSUE, "none", order=["brakes", "tyres", "engine"])
    if label != "none" and any(re.search(p, lowered) for p in NO_ISSUE):
        # "No problems with the brakes" style reports.
        negated = re.search(r"\bno (issues?|problems?)\b.{0,30}\b(with|on)\b", lowered)
        if negated:
            return "none"
    return label


REQUEST = {
    "renew": [r"\brenew", r"\bextend", r"\bextension\b", r"\bmore time\b", r"\blonger\b",
              r"\bkeep (it|the book|them)\b", r"\banother (week|two weeks|fortnight)\b",
              r"\bhaven'?t finished\b", r"\bnot finished\b", r"\bstill reading\b", r"\bpush back\b"],
    "return": [r"\breturn", r"\bbring (it|them|the book|the books) back\b", r"\bdrop (it|them|.{0,20}) off\b",
               r"\bdrop-?off\b", r"\bbook drop\b", r"\bhand (it|them) (in|back)\b", r"\bgive (it|them) back\b",
               r"\bfinished (reading|with)\b", r"\bdone with\b", r"\bbringing back\b"],
    "reserve": [r"\breserv", r"\bhold\b", r"\bon hold\b", r"\bset aside\b", r"\bput aside\b",
                r"\bnext in line\b", r"\bwaiting list\b", r"\bwait ?list\b", r"\bqueue\b",
                r"\bwhen it (comes|is) (back|available)\b", r"\bavailable\b", r"\bborrow next\b",
                r"\bbook a copy\b", r"\bsave (it|a copy|the book) for me\b"],
    "complain": [r"\bcomplain", r"\bunacceptable\b", r"\bdisappoint", r"\bfrustrat", r"\bunfair\b",
                 r"\bannoy", r"\brude\b", r"\bridiculous\b", r"\bterrible\b", r"\bawful\b", r"\bupset\b",
                 r"\bwrong(ly)?\b", r"\bmistake\b", r"\berror\b", r"\bdamaged\b", r"\btorn\b",
                 r"\bmissing pages\b", r"\bdirty\b", r"\bnoisy\b", r"\bnoise\b", r"\bnot happy\b",
                 r"\bunhappy\b", r"\bpoor\b", r"\bshould not have\b", r"\bshouldn'?t have\b",
                 r"\bovercharg", r"\bfine (is|was) (too|unfair)\b", r"\bdispute\b"],
}


def read_request(text):
    return _score(text, REQUEST, "renew", order=["complain", "reserve", "renew", "return"])


SITE = {
    "north": [r"\bnorth", r"\bn\. ?(site|wing|gate|block)\b", r"\bupper\b", r"\btop\b"],
    "south": [r"\bsouth", r"\bs\. ?(site|wing|gate|block)\b", r"\blower\b", r"\bbottom\b"],
    "east": [r"\beast", r"\be\. ?(site|wing|gate|block)\b", r"\bsunrise\b"],
    "west": [r"\bwest", r"\bw\. ?(site|wing|gate|block)\b", r"\bsunset\b"],
}


def read_site(text):
    lowered = text.lower()
    # A compass word naming the site wins over others; take the first one used.
    first = re.search(r"\b(north|south|east|west)(ern)?\b", lowered)
    if first:
        return first.group(1)
    return _score(text, SITE, "north", order=["north", "south", "east", "west"])


COUNTRY = {
    "UK": [r"\buk\b", r"\bu\.k\.", r"\bunited kingdom\b", r"\bbritain\b", r"\bbritish\b", r"\bengland\b",
           r"\benglish\b", r"\bscotland\b", r"\bscottish\b", r"\bwales\b", r"\bwelsh\b", r"\blondon\b",
           r"\bmanchester\b", r"\bbirmingham\b", r"\bleeds\b", r"\bglasgow\b", r"\bedinburgh\b",
           r"\bliverpool\b", r"\bbristol\b", r"\bcardiff\b", r"\bnewcastle\b", r"\bsheffield\b",
           r"\bnottingham\b", r"\boxford\b", r"\bcambridge\b", r"\bbelfast\b", r"\bpostcode\b",
           r"\bpounds?\b", r"\bsterling\b", r"\bhmrc\b", r"\bbrighton\b", r"\bsouthampton\b",
           r"\breading\b", r"\bleicester\b", r"\bcoventry\b", r"\byork\b", r"\baberdeen\b"],
    "Ireland": [r"\bireland\b", r"\birish\b", r"\beire\b", r"\bdublin\b", r"\bcork\b", r"\bgalway\b",
                r"\blimerick\b", r"\bwaterford\b", r"\bkilkenny\b", r"\bsligo\b", r"\bkerry\b",
                r"\bdonegal\b", r"\bwexford\b", r"\bathlone\b", r"\bdrogheda\b", r"\bdundalk\b",
                r"\beircode\b", r"\bkillarney\b", r"\bennis\b", r"\btralee\b", r"\bmayo\b", r"\bwicklow\b"],
    "Spain": [r"\bspain\b", r"\bspanish\b", r"\bespa[nñ]a\b", r"\bmadrid\b", r"\bbarcelona\b",
              r"\bvalencia\b", r"\bseville\b", r"\bsevilla\b", r"\bbilbao\b", r"\bmalaga\b", r"\bmálaga\b",
              r"\bzaragoza\b", r"\bgranada\b", r"\balicante\b", r"\bpalma\b", r"\bmallorca\b",
              r"\bmajorca\b", r"\bibiza\b", r"\bcanary\b", r"\bcanaries\b", r"\btenerife\b",
              r"\bsan sebasti[aá]n\b", r"\bc[oó]rdoba\b", r"\bmurcia\b", r"\bsalamanca\b",
              r"\bsantander\b", r"\bcatalonia\b", r"\bcatalu", r"\bandalusia\b", r"\bgalicia\b",
              r"\bvigo\b", r"\bpamplona\b", r"\bvalladolid\b", r"\btoledo\b"],
    "Italy": [r"\bitaly\b", r"\bitalian\b", r"\bitalia\b", r"\brome\b", r"\broma\b", r"\bmilan\b",
              r"\bmilano\b", r"\bnaples\b", r"\bnapoli\b", r"\bturin\b", r"\btorino\b", r"\bflorence\b",
              r"\bfirenze\b", r"\bvenice\b", r"\bvenezia\b", r"\bbologna\b", r"\bgenoa\b", r"\bgenova\b",
              r"\bpalermo\b", r"\bverona\b", r"\bpisa\b", r"\bsiena\b", r"\bbari\b", r"\bcatania\b",
              r"\bsicily\b", r"\bsardinia\b", r"\btuscany\b", r"\blombardy\b", r"\bpadua\b", r"\bpadova\b",
              r"\btrieste\b", r"\bparma\b", r"\bmodena\b", r"\bbergamo\b", r"\bbrescia\b", r"\blake como\b",
              r"\bcomo\b", r"\bpiedmont\b", r"\bpuglia\b", r"\bamalfi\b"],
}


def read_country(text):
    return _score(text, COUNTRY, "UK", order=["Ireland", "Spain", "Italy", "UK"])


FORMALITY = {
    "formal": [r"\bblack tie\b", r"\bformal\b", r"\bgala\b", r"\bdinner\b", r"\bbanquet\b",
               r"\bceremony\b", r"\breception\b", r"\brequest the (pleasure|honour|honor)\b",
               r"\bcordially\b", r"\bhonou?r\b", r"\brsvp\b", r"\bawards?\b", r"\bball\b",
               r"\beveningwear\b", r"\bevening wear\b", r"\bgown", r"\btuxedo", r"\bdinner jacket\b",
               r"\bannual\b", r"\bdistinguished\b", r"\bchampagne\b", r"\bsoir[eé]e\b", r"\bdignitar",
               r"\bboard\b", r"\bkindly\b", r"\bpresence\b", r"\besteemed\b", r"\bwe are pleased\b",
               r"\bdelighted to invite\b"],
    "casual": [r"\bcasual\b", r"\brelaxed\b", r"\binformal\b", r"\bbbq\b", r"\bbarbecue\b",
               r"\bbarbeque\b", r"\bpicnic\b", r"\bpotluck\b", r"\bpot luck\b", r"\bdrinks\b",
               r"\bpub\b", r"\bpizza\b", r"\bjeans\b", r"\bhang ?out\b", r"\bchill\b", r"\bfun\b",
               r"\bcome as you are\b", r"\bbring a\b", r"\bbyo\b", r"\bgames?\b", r"\bbackyard\b",
               r"\bgarden\b", r"\bbeach\b", r"\bgrab\b", r"\bhey\b", r"\bguys\b", r"\bfolks\b",
               r"\bno need to dress up\b", r"\bkick back\b", r"\bsnacks\b", r"\btacos?\b", r"!"],
}


def read_formality(text):
    lowered = text.lower()
    if re.search(r"\b(no need to dress up|come as you are|dress (is )?casual|casual dress)\b", lowered):
        return "casual"
    return _score(text, FORMALITY, "casual", order=["formal", "casual"])


RULES = {
    "ticket_queue": read_urgency,
    "room_bookings": read_department,
    "recipe_scaling": read_diet,
    "fleet_fuel": read_issue,
    "library_loans": read_request,
    "sensor_alerts": read_site,
    "invoice_vat": read_country,
    "event_rsvps": read_formality,
}
