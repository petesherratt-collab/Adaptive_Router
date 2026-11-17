"""Harder task shapes for the fast-path timing experiment V2.

Same recipe as ``fast_path_timing_bench_v1.py``: a specification, a ``solve``
signature, a reference implementation qualified by hand-written tests, and a
seeded generator of request arguments. These shapes were chosen because a
plausible implementation is easy to get subtly wrong: rounding direction,
truncating division, precedence rules, quoting, calendar arithmetic and
multi-rule formatting.

No shape here appears in any earlier bank.

Run ``python fast_path_timing_bench_v2_hard.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import fast_path_timing_bench_v1 as _v1
from fast_path_timing_bench_v1 import WORDS, gold  # noqa: F401  (gold is re-exported)

STREAM_SEED = 20261117
STREAM_LENGTH = 30
SMALL_WORDS = ["a", "an", "and", "the", "of", "in", "on", "to", "for"]
ACRONYMS = ["HTTP", "ID", "URL", "XML", "API"]
PRERELEASES = ["", "", "alpha", "alpha.1", "alpha.beta", "beta", "beta.2", "beta.11",
               "rc.1", "rc.2", "1", "2.x"]
COIN_SETS = [[1, 3, 4], [1, 7, 10], [2, 5], [1, 5, 10, 25], [3, 7], [1, 6, 10], [4, 9], [1, 4, 6]]
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _date(r, first, last):
    year = r.randint(first, last)
    month = r.randint(1, 12)
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return [year, month, r.randint(1, 29 if month == 2 and leap else DAYS[month - 1])]


def _semver(r):
    def one():
        core = f"{r.choice([1, 1, 2])}.{r.choice([0, 0, 9, 10])}.{r.choice([0, 0, 3])}"
        pre = r.choice(PRERELEASES)
        return core + ("-" + pre if pre else "")
    return [one(), one()]


def _expression(r):
    def build(depth):
        if depth == 0 or r.random() < 0.3:
            return str(r.randint(0, 20))
        left, right = build(depth - 1), build(depth - 1)
        text = f"{left}{r.choice(['+', '-', '*', '/'])}{right}"
        return f"({text})" if r.random() < 0.4 else text

    def safe(text):
        try:
            eval(text.replace("/", "//"))  # noqa: S307  generator-side zero check only
        except ZeroDivisionError:
            return False
        return True

    while True:
        text = build(2)
        if r.random() < 0.2:
            text = "-" + (text if text.startswith("(") else f"({text})")
        if safe(text) and any(op in text for op in "+-*/"):
            return [text.replace("+", " + ") if r.random() < 0.3 else text]


def _csv(r):
    def field():
        kind = r.randint(0, 5)
        word, other = r.sample(WORDS, 2)
        if kind == 0:
            return f'"{word},{other}"'
        if kind == 1:
            return f'"{word} ""{other}"""'
        if kind == 2:
            return ""
        if kind == 3:
            return f" {word} "
        return word
    return [",".join(field() for _ in range(r.randint(2, 4)))]


def _title(r):
    words = [r.choice(SMALL_WORDS) if r.random() < 0.5 else r.choice(WORDS)
             for _ in range(r.randint(3, 6))]
    text = " ".join(words)
    return [text.upper() if r.random() < 0.2 else text]


def _camel(r):
    parts = [r.choice(WORDS) if r.random() < 0.8 else r.choice(ACRONYMS)]
    for _ in range(r.randint(1, 3)):
        if parts[-1].rstrip("0123456789").isupper() or r.random() < 0.6:
            part = r.choice(WORDS).capitalize()
        else:
            part = r.choice(ACRONYMS)
        if r.random() < 0.2:
            part += str(r.randint(1, 9))
        parts.append(part)
    return ["".join(parts)]


def _matrix(r):
    rows, cols = r.randint(1, 4), r.randint(1, 4)
    return [[[r.randint(0, 99) for _ in range(cols)] for _ in range(rows)]]


def _ipv4(r):
    parts = [str(r.randint(0, 255)) for _ in range(4)]
    fault = r.randint(0, 9)
    if fault == 0:
        parts[r.randint(0, 3)] = "0" + str(r.randint(1, 99))
    elif fault == 1:
        parts[r.randint(0, 3)] = str(r.randint(256, 999))
    elif fault == 2:
        parts.pop()
    elif fault == 3:
        parts.append(str(r.randint(0, 255)))
    elif fault == 4:
        parts[r.randint(0, 3)] = ""
    elif fault == 5:
        parts[r.randint(0, 3)] += "a"
    return [".".join(parts)]


def _luhn(r):
    digits = [r.randint(0, 9) for _ in range(r.randint(7, 15))]
    if r.random() < 0.5:
        total = 0
        for index, digit in enumerate(reversed(digits)):
            if index % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        digits.append((10 - total % 10) % 10)
    else:
        digits.append(r.randint(0, 9))
    text = "".join(map(str, digits))
    if r.random() < 0.4:
        text = " ".join(text[i:i + 4] for i in range(0, len(text), 4))
    return [text]


def _natural(r):
    prefix = r.choice(["file", "img", "x"])
    names = {f"{r.choice([prefix, prefix.upper()])}{r.randint(1, 120)}{r.choice(['', '', 'a'])}"
             for _ in range(r.randint(3, 5))}
    names = sorted(names)
    r.shuffle(names)
    return [names]


def _base(r):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    source, target = r.sample([2, 8, 10, 16, 36], 2)
    number, text = r.randint(0, 5000), ""
    while number:
        text = digits[number % source] + text
        number //= source
    return [text or "0", source, target]


SHAPES = [
    {
        "name": "weekday_name",
        "spec": "Given a year, month and day in the Gregorian calendar, return the English name of that day of the week, such as 'Monday'.",
        "signature": "def solve(year: int, month: int, day: int) -> str:",
        "reference": (
            "def solve(year, month, day):\n"
            "    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]\n"
            "    y = year - 1 if month < 3 else year\n"
            "    w = (y + y // 4 - y // 100 + y // 400 + t[month - 1] + day) % 7\n"
            "    return ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][w]\n"
        ),
        "tests": [[[2024, 1, 1], "Monday"], [[2000, 2, 29], "Tuesday"], [[1999, 12, 31], "Friday"],
                  [[2023, 7, 4], "Tuesday"], [[1900, 1, 1], "Monday"], [[2024, 2, 29], "Thursday"],
                  [[2021, 12, 25], "Saturday"]],
        "gen": lambda r: _date(r, 1900, 2100),
    },
    {
        "name": "column_title",
        "spec": "Convert a positive integer to its spreadsheet column title: 1 is 'A', 26 is 'Z', 27 is 'AA', 28 is 'AB', and so on.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    out = ''\n"
            "    while n > 0:\n"
            "        n -= 1\n"
            "        out = chr(65 + n % 26) + out\n"
            "        n //= 26\n"
            "    return out\n"
        ),
        "tests": [[[1], "A"], [[26], "Z"], [[27], "AA"], [[52], "AZ"], [[53], "BA"],
                  [[702], "ZZ"], [[703], "AAA"], [[18278], "ZZZ"]],
        "gen": lambda r: [r.randint(1, 20000)],
    },
    {
        "name": "round_half_away",
        "spec": "Given integers num and den with den > 0, return the integer nearest to num / den. Exact halves are rounded away from zero, so 5/2 gives 3 and -5/2 gives -3.",
        "signature": "def solve(num: int, den: int) -> int:",
        "reference": (
            "def solve(num, den):\n"
            "    sign = -1 if num < 0 else 1\n"
            "    return sign * ((2 * abs(num) + den) // (2 * den))\n"
        ),
        "tests": [[[5, 2], 3], [[-5, 2], -3], [[7, 2], 4], [[1, 3], 0], [[2, 3], 1], [[-1, 2], -1],
                  [[3, 2], 2], [[-7, 3], -2], [[0, 5], 0], [[-3, 2], -2], [[1, 2], 1]],
        "gen": lambda r: [r.randint(-200, 200), r.choice([2, 2, 2, 3, 4, 5, 6, 8])],
    },
    {
        "name": "trunc_divmod",
        "spec": "Given integers a and b with b not zero, return [q, r] where q is a / b truncated toward zero and r = a - b * q. For example -7 and 2 give [-3, -1].",
        "signature": "def solve(a: int, b: int) -> list:",
        "reference": (
            "def solve(a, b):\n"
            "    q = abs(a) // abs(b)\n"
            "    if (a < 0) != (b < 0):\n"
            "        q = -q\n"
            "    return [q, a - b * q]\n"
        ),
        "tests": [[[7, 2], [3, 1]], [[-7, 2], [-3, -1]], [[7, -2], [-3, 1]], [[-7, -2], [3, -1]],
                  [[6, 3], [2, 0]], [[0, 5], [0, 0]], [[-1, 3], [0, -1]]],
        "gen": lambda r: [r.randint(-100, 100), r.choice([-1, 1]) * r.randint(1, 12)],
    },
    {
        "name": "min_coins",
        "spec": "Given a list of distinct positive coin values and a non-negative amount, return the smallest number of coins (each value usable any number of times) that sum exactly to the amount, or -1 if it cannot be made.",
        "signature": "def solve(coins: list, amount: int) -> int:",
        "reference": (
            "def solve(coins, amount):\n"
            "    best = [0] + [None] * amount\n"
            "    for total in range(1, amount + 1):\n"
            "        options = [best[total - c] for c in coins if c <= total and best[total - c] is not None]\n"
            "        if options:\n"
            "            best[total] = min(options) + 1\n"
            "    return -1 if best[amount] is None else best[amount]\n"
        ),
        "tests": [[[[1, 3, 4], 6], 2], [[[1, 5, 10, 25], 30], 2], [[[2], 3], -1], [[[1], 0], 0],
                  [[[5, 10], 0], 0], [[[3, 7], 11], -1], [[[1, 7, 10], 14], 2], [[[2, 5], 6], 3]],
        "gen": lambda r: [r.choice(COIN_SETS), r.randint(0, 40)],
    },
    {
        "name": "number_to_words",
        "spec": "Write an integer from 0 to 9999 in English words, lowercase. Hyphenate 21 to 99 where needed ('twenty-one'). Use British style: put 'and' before the final tens-or-units part whenever something precedes it and that part is non-zero, as in 'one hundred and five', 'one thousand and five' and 'one thousand two hundred and thirty-four'. No commas.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    ones = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',\n"
            "            'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen',\n"
            "            'eighteen', 'nineteen']\n"
            "    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']\n"
            "    if n == 0:\n"
            "        return 'zero'\n"
            "    parts = []\n"
            "    if n >= 1000:\n"
            "        parts.append(ones[n // 1000] + ' thousand')\n"
            "    rest = n % 1000\n"
            "    if rest >= 100:\n"
            "        parts.append(ones[rest // 100] + ' hundred')\n"
            "    last = rest % 100\n"
            "    if last:\n"
            "        if last < 20:\n"
            "            word = ones[last]\n"
            "        else:\n"
            "            word = tens[last // 10]\n"
            "            if last % 10:\n"
            "                word += '-' + ones[last % 10]\n"
            "        if parts:\n"
            "            word = 'and ' + word\n"
            "        parts.append(word)\n"
            "    return ' '.join(parts)\n"
        ),
        "tests": [[[0], "zero"], [[7], "seven"], [[13], "thirteen"], [[21], "twenty-one"], [[40], "forty"],
                  [[100], "one hundred"], [[105], "one hundred and five"],
                  [[999], "nine hundred and ninety-nine"], [[1000], "one thousand"],
                  [[1005], "one thousand and five"],
                  [[1234], "one thousand two hundred and thirty-four"],
                  [[2100], "two thousand one hundred"], [[9019], "nine thousand and nineteen"]],
        "gen": lambda r: [r.randint(0, 9999)],
    },
    {
        "name": "semver_compare",
        "spec": "Compare two versions of the form MAJOR.MINOR.PATCH with an optional '-prerelease' made of dot-separated identifiers. Return -1, 0 or 1 when the first is lower than, equal to or higher than the second. Compare major, minor and patch numerically. If those are equal, a version with a prerelease is lower than one without. Two prereleases are compared identifier by identifier: two numeric identifiers numerically, two others as ASCII text, and a numeric identifier is lower than a non-numeric one. If all shared identifiers are equal, the prerelease with fewer identifiers is lower.",
        "signature": "def solve(a: str, b: str) -> int:",
        "reference": (
            "def solve(a, b):\n"
            "    def parse(v):\n"
            "        core, _, pre = v.partition('-')\n"
            "        return [int(x) for x in core.split('.')], (pre.split('.') if pre else [])\n"
            "    def cmp(x, y):\n"
            "        return (x > y) - (x < y)\n"
            "    na, pa = parse(a)\n"
            "    nb, pb = parse(b)\n"
            "    if na != nb:\n"
            "        return cmp(na, nb)\n"
            "    if not pa or not pb:\n"
            "        return cmp(not pa, not pb)\n"
            "    for x, y in zip(pa, pb):\n"
            "        if x == y:\n"
            "            continue\n"
            "        xd, yd = x.isdigit(), y.isdigit()\n"
            "        if xd and yd:\n"
            "            return cmp(int(x), int(y))\n"
            "        if xd != yd:\n"
            "            return -1 if xd else 1\n"
            "        return cmp(x, y)\n"
            "    return cmp(len(pa), len(pb))\n"
        ),
        "tests": [[["1.0.0", "1.0.0"], 0], [["1.0.0-alpha", "1.0.0"], -1],
                  [["1.0.0-alpha", "1.0.0-alpha.1"], -1], [["1.0.0-alpha.1", "1.0.0-alpha.beta"], -1],
                  [["1.0.0-beta.2", "1.0.0-beta.11"], -1], [["1.0.0-rc.1", "1.0.0-beta.11"], 1],
                  [["2.0.0", "1.9.9"], 1], [["1.10.0", "1.9.0"], 1],
                  [["1.0.0-beta", "1.0.0-alpha.beta"], 1], [["1.0.0-1", "1.0.0-alpha"], -1]],
        "gen": _semver,
    },
    {
        "name": "eval_expression",
        "spec": "Evaluate an arithmetic expression given as a string and return the integer result. It contains non-negative integers, the operators + - * /, parentheses and optional spaces. * and / bind tighter than + and -, and operators of equal precedence apply left to right. Division truncates toward zero. A minus sign may also appear as a negation at the very start of the expression or directly after an opening parenthesis.",
        "signature": "def solve(expression: str) -> int:",
        "reference": (
            "import re\n"
            "def solve(expression):\n"
            "    tokens = re.findall(r'\\d+|[-+*/()]', expression)\n"
            "    pos = [0]\n"
            "    def peek():\n"
            "        return tokens[pos[0]] if pos[0] < len(tokens) else None\n"
            "    def take():\n"
            "        pos[0] += 1\n"
            "        return tokens[pos[0] - 1]\n"
            "    def divide(a, b):\n"
            "        q = abs(a) // abs(b)\n"
            "        return -q if (a < 0) != (b < 0) else q\n"
            "    def atom():\n"
            "        token = take()\n"
            "        if token == '(':\n"
            "            value = expr()\n"
            "            take()\n"
            "            return value\n"
            "        return int(token)\n"
            "    def term():\n"
            "        value = atom()\n"
            "        while peek() in ('*', '/'):\n"
            "            if take() == '*':\n"
            "                value = value * atom()\n"
            "            else:\n"
            "                value = divide(value, atom())\n"
            "        return value\n"
            "    def expr():\n"
            "        negate = peek() == '-'\n"
            "        if negate:\n"
            "            take()\n"
            "        value = term()\n"
            "        if negate:\n"
            "            value = -value\n"
            "        while peek() in ('+', '-'):\n"
            "            if take() == '+':\n"
            "                value = value + term()\n"
            "            else:\n"
            "                value = value - term()\n"
            "        return value\n"
            "    return expr()\n"
        ),
        "tests": [[["1+2*3"], 7], [["(1+2)*3"], 9], [["7/2"], 3], [["-7/2"], -3], [["2*(3+4)-5"], 9],
                  [[" 10 - 4 - 3 "], 3], [["8/3/2"], 1], [["(0-7)/2"], -3], [["-(2+3)*2"], -10],
                  [["100/(2+3)"], 20], [["(-4+1)/2"], -1]],
        "gen": _expression,
    },
    {
        "name": "csv_split",
        "spec": "Split one line of CSV into its list of fields. Fields are separated by commas. A field may be wrapped in double quotes; inside quotes a comma is literal and two double quotes in a row mean one literal double quote. The wrapping quotes are not part of the field. Unquoted fields are kept exactly, including spaces. An empty line gives one empty field.",
        "signature": "def solve(line: str) -> list:",
        "reference": (
            "def solve(line):\n"
            "    fields, current, quoted, i = [], [], False, 0\n"
            "    while i < len(line):\n"
            "        ch = line[i]\n"
            "        if quoted:\n"
            "            if ch == '\"':\n"
            "                if i + 1 < len(line) and line[i + 1] == '\"':\n"
            "                    current.append('\"')\n"
            "                    i += 1\n"
            "                else:\n"
            "                    quoted = False\n"
            "            else:\n"
            "                current.append(ch)\n"
            "        elif ch == '\"':\n"
            "            quoted = True\n"
            "        elif ch == ',':\n"
            "            fields.append(''.join(current))\n"
            "            current = []\n"
            "        else:\n"
            "            current.append(ch)\n"
            "        i += 1\n"
            "    fields.append(''.join(current))\n"
            "    return fields\n"
        ),
        "tests": [[["a,b,c"], ["a", "b", "c"]], [['a,"b,c",d'], ["a", "b,c", "d"]],
                  [['"he said ""hi""",x'], ['he said "hi"', "x"]], [[""], [""]],
                  [["a,,b"], ["a", "", "b"]], [[" a , b "], [" a ", " b "]],
                  [['"",x'], ["", "x"]], [["x,"], ["x", ""]]],
        "gen": _csv,
    },
    {
        "name": "title_case_small_words",
        "spec": "Lowercase the whole string, then capitalise the first letter of each space-separated word, except that the words a, an, and, the, of, in, on, to and for stay lowercase unless they are the first or the last word.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "def solve(s):\n"
            "    small = ('a', 'an', 'and', 'the', 'of', 'in', 'on', 'to', 'for')\n"
            "    words = s.lower().split(' ')\n"
            "    out = []\n"
            "    for i, word in enumerate(words):\n"
            "        if word in small and 0 < i < len(words) - 1:\n"
            "            out.append(word)\n"
            "        else:\n"
            "            out.append(word[:1].upper() + word[1:])\n"
            "    return ' '.join(out)\n"
        ),
        "tests": [[["the lord of the rings"], "The Lord of the Rings"],
                  [["a tale of two cities"], "A Tale of Two Cities"],
                  [["of mice and men"], "Of Mice and Men"], [["WAR AND PEACE"], "War and Peace"],
                  [["what to look for"], "What to Look For"], [["in"], "In"], [[""], ""],
                  [["the end of the"], "The End of The"]],
        "gen": _title,
    },
    {
        "name": "camel_split",
        "spec": "Split a camelCase or PascalCase identifier into its words, keeping the original letter case. A new word starts at each uppercase letter that follows a lowercase letter or digit. A run of uppercase letters is one acronym word, except that when the run is followed by a lowercase letter its last uppercase letter starts the next word, so 'parseHTTPResponse' gives ['parse', 'HTTP', 'Response']. Digits stay attached to the word before them. The empty string gives an empty list.",
        "signature": "def solve(s: str) -> list:",
        "reference": (
            "import re\n"
            "def solve(s):\n"
            "    return re.findall(r'[A-Z]+(?![a-z])\\d*|[A-Z]?[a-z]+\\d*|\\d+', s)\n"
        ),
        "tests": [[["parseHTTPResponse"], ["parse", "HTTP", "Response"]], [["simpleTest"], ["simple", "Test"]],
                  [["HTMLParser"], ["HTML", "Parser"]], [["already"], ["already"]],
                  [["getID"], ["get", "ID"]], [["x"], ["x"]],
                  [["userID2Name"], ["user", "ID2", "Name"]], [[""], []],
                  [["version2Beta"], ["version2", "Beta"]]],
        "gen": _camel,
    },
    {
        "name": "spiral_order",
        "spec": "Return the elements of a rectangular matrix, given as a list of rows, in clockwise spiral order starting at the top-left and moving right first. An empty matrix gives an empty list.",
        "signature": "def solve(matrix: list) -> list:",
        "reference": (
            "def solve(matrix):\n"
            "    out = []\n"
            "    if not matrix:\n"
            "        return out\n"
            "    top, bottom, left, right = 0, len(matrix) - 1, 0, len(matrix[0]) - 1\n"
            "    while top <= bottom and left <= right:\n"
            "        for c in range(left, right + 1):\n"
            "            out.append(matrix[top][c])\n"
            "        for r in range(top + 1, bottom + 1):\n"
            "            out.append(matrix[r][right])\n"
            "        if top < bottom:\n"
            "            for c in range(right - 1, left - 1, -1):\n"
            "                out.append(matrix[bottom][c])\n"
            "        if left < right:\n"
            "            for r in range(bottom - 1, top, -1):\n"
            "                out.append(matrix[r][left])\n"
            "        top, bottom, left, right = top + 1, bottom - 1, left + 1, right - 1\n"
            "    return out\n"
        ),
        "tests": [[[[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [1, 2, 3, 6, 9, 8, 7, 4, 5]],
                  [[[[1, 2], [3, 4]]], [1, 2, 4, 3]], [[[[1, 2, 3, 4]]], [1, 2, 3, 4]],
                  [[[[1], [2], [3]]], [1, 2, 3]], [[[]], []], [[[[7]]], [7]],
                  [[[[1, 2, 3], [4, 5, 6]]], [1, 2, 3, 6, 5, 4]],
                  [[[[1, 2], [3, 4], [5, 6]]], [1, 2, 4, 6, 5, 3]]],
        "gen": _matrix,
    },
    {
        "name": "next_permutation",
        "spec": "Return the next permutation of a list of integers in lexicographic order. If the list is already the last permutation, return it sorted ascending.",
        "signature": "def solve(nums: list) -> list:",
        "reference": (
            "def solve(nums):\n"
            "    out = list(nums)\n"
            "    i = len(out) - 2\n"
            "    while i >= 0 and out[i] >= out[i + 1]:\n"
            "        i -= 1\n"
            "    if i < 0:\n"
            "        return sorted(out)\n"
            "    j = len(out) - 1\n"
            "    while out[j] <= out[i]:\n"
            "        j -= 1\n"
            "    out[i], out[j] = out[j], out[i]\n"
            "    return out[:i + 1] + out[i + 1:][::-1]\n"
        ),
        "tests": [[[[1, 2, 3]], [1, 3, 2]], [[[3, 2, 1]], [1, 2, 3]], [[[1, 1, 5]], [1, 5, 1]],
                  [[[1]], [1]], [[[1, 3, 2]], [2, 1, 3]], [[[2, 3, 1]], [3, 1, 2]], [[[]], []],
                  [[[1, 5, 1]], [5, 1, 1]]],
        "gen": lambda r: [[r.randint(1, 5) for _ in range(r.randint(2, 5))]],
    },
    {
        "name": "days_between",
        "spec": "Given two Gregorian dates as year, month, day and a second year, month, day, return the number of days from the first date to the second. The result is negative when the second date is earlier.",
        "signature": "def solve(y1: int, m1: int, d1: int, y2: int, m2: int, d2: int) -> int:",
        "reference": (
            "def solve(y1, m1, d1, y2, m2, d2):\n"
            "    def ordinal(y, m, d):\n"
            "        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]\n"
            "        if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):\n"
            "            days[1] = 29\n"
            "        p = y - 1\n"
            "        return p * 365 + p // 4 - p // 100 + p // 400 + sum(days[:m - 1]) + d\n"
            "    return ordinal(y2, m2, d2) - ordinal(y1, m1, d1)\n"
        ),
        "tests": [[[2024, 1, 1, 2024, 1, 2], 1], [[2024, 2, 28, 2024, 3, 1], 2],
                  [[2023, 2, 28, 2023, 3, 1], 1], [[2024, 1, 1, 2023, 1, 1], -365],
                  [[2000, 1, 1, 2000, 12, 31], 365], [[1999, 12, 31, 2000, 1, 1], 1],
                  [[2024, 3, 15, 2024, 3, 15], 0], [[1900, 2, 28, 1900, 3, 1], 1]],
        "gen": lambda r: _date(r, 1990, 2030) + _date(r, 1990, 2030),
    },
    {
        "name": "humanize_duration",
        "spec": "Describe a non-negative number of seconds using days, hours, minutes and seconds. Leave out units that are zero, use the singular for 1 ('1 hour') and the plural otherwise, separate units with ', ' and join the last two with ' and '. Examples: 62 gives '1 minute and 2 seconds', 3662 gives '1 hour, 1 minute and 2 seconds'. Zero gives 'now'.",
        "signature": "def solve(seconds: int) -> str:",
        "reference": (
            "def solve(seconds):\n"
            "    if seconds == 0:\n"
            "        return 'now'\n"
            "    parts = []\n"
            "    for name, size in (('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)):\n"
            "        count, seconds = divmod(seconds, size)\n"
            "        if count:\n"
            "            parts.append(str(count) + ' ' + name + ('' if count == 1 else 's'))\n"
            "    if len(parts) == 1:\n"
            "        return parts[0]\n"
            "    return ', '.join(parts[:-1]) + ' and ' + parts[-1]\n"
        ),
        "tests": [[[0], "now"], [[1], "1 second"], [[62], "1 minute and 2 seconds"], [[3600], "1 hour"],
                  [[3662], "1 hour, 1 minute and 2 seconds"], [[86400], "1 day"],
                  [[90061], "1 day, 1 hour, 1 minute and 1 second"], [[120], "2 minutes"],
                  [[172859], "2 days and 59 seconds"]],
        "gen": lambda r: [r.randint(0, 300000)],
    },
    {
        "name": "ipv4_valid",
        "spec": "Return whether a string is a valid dotted IPv4 address: exactly four parts separated by dots, each part made only of digits, with a value from 0 to 255 and no leading zero unless the part is exactly '0'. Empty parts, spaces, signs and letters make it invalid.",
        "signature": "def solve(s: str) -> bool:",
        "reference": (
            "def solve(s):\n"
            "    parts = s.split('.')\n"
            "    if len(parts) != 4:\n"
            "        return False\n"
            "    for part in parts:\n"
            "        if not part or any(ch not in '0123456789' for ch in part):\n"
            "            return False\n"
            "        if len(part) > 1 and part[0] == '0':\n"
            "            return False\n"
            "        if int(part) > 255:\n"
            "            return False\n"
            "    return True\n"
        ),
        "tests": [[["192.168.1.1"], True], [["255.255.255.255"], True], [["256.1.1.1"], False],
                  [["1.2.3"], False], [["01.2.3.4"], False], [["0.0.0.0"], True],
                  [["1.2.3.4.5"], False], [["1..3.4"], False], [["a.b.c.d"], False],
                  [[" 1.2.3.4"], False], [["1.2.3.-4"], False]],
        "gen": _ipv4,
    },
    {
        "name": "luhn_valid",
        "spec": "Return whether a string of digits passes the Luhn check. Spaces are ignored. Starting from the rightmost digit and moving left, double every second digit; if doubling gives more than 9 subtract 9; the total of all digits must be divisible by 10. A string with fewer than two digits is invalid.",
        "signature": "def solve(s: str) -> bool:",
        "reference": (
            "def solve(s):\n"
            "    digits = [int(ch) for ch in s.replace(' ', '')]\n"
            "    if len(digits) < 2:\n"
            "        return False\n"
            "    total = 0\n"
            "    for index, digit in enumerate(reversed(digits)):\n"
            "        if index % 2 == 1:\n"
            "            digit *= 2\n"
            "            if digit > 9:\n"
            "                digit -= 9\n"
            "        total += digit\n"
            "    return total % 10 == 0\n"
        ),
        "tests": [[["4539 1488 0343 6467"], True], [["8273 1232 7352 0569"], False], [["0"], False],
                  [["059"], True], [["59"], True], [["79927398713"], True], [["79927398710"], False],
                  [["18"], True], [["00"], True]],
        "gen": _luhn,
    },
    {
        "name": "natural_sort",
        "spec": "Sort a list of strings in natural order and return the sorted list. Split each string into alternating runs of digits and runs of other characters. Compare strings run by run: two digit runs by numeric value, two other runs as text ignoring letter case, and a digit run sorts before a non-digit run. If every shared run is equal the string with fewer runs comes first. Strings that compare equal keep their original relative order.",
        "signature": "def solve(items: list) -> list:",
        "reference": (
            "import re\n"
            "def solve(items):\n"
            "    def key(s):\n"
            "        return [(0, int(run), '') if run.isdigit() else (1, 0, run.lower())\n"
            "                for run in re.split(r'(\\d+)', s) if run]\n"
            "    return sorted(items, key=key)\n"
        ),
        "tests": [[[["file10", "file2", "file1"]], ["file1", "file2", "file10"]],
                  [[["b", "A", "c"]], ["A", "b", "c"]], [[["x9", "x10", "x9a"]], ["x9", "x9a", "x10"]],
                  [[[]], []], [[["a1b2", "a1b10", "a1b1"]], ["a1b1", "a1b2", "a1b10"]],
                  [[["10", "9", "1"]], ["1", "9", "10"]],
                  [[["img12.png", "img2.png"]], ["img2.png", "img12.png"]],
                  [[["File2", "file2", "FILE1"]], ["FILE1", "File2", "file2"]]],
        "gen": _natural,
    },
    {
        "name": "wrap_text",
        "spec": "Wrap text to a maximum line width and return the list of lines. Words are the whitespace-separated parts of the text. Build each line greedily: add the next word, separated by one space, while the line stays within the width. A word longer than the width goes on a line by itself, unbroken. Text with no words gives an empty list.",
        "signature": "def solve(text: str, width: int) -> list:",
        "reference": (
            "def solve(text, width):\n"
            "    lines, current = [], ''\n"
            "    for word in text.split():\n"
            "        if not current:\n"
            "            current = word\n"
            "        elif len(current) + 1 + len(word) <= width:\n"
            "            current += ' ' + word\n"
            "        else:\n"
            "            lines.append(current)\n"
            "            current = word\n"
            "    if current:\n"
            "        lines.append(current)\n"
            "    return lines\n"
        ),
        "tests": [[["the quick brown fox", 10], ["the quick", "brown fox"]], [["hello", 3], ["hello"]],
                  [["", 5], []], [["a b c", 1], ["a", "b", "c"]], [["aa bb cc", 5], ["aa bb", "cc"]],
                  [["one two", 7], ["one two"]], [["one two", 6], ["one", "two"]],
                  [["  spaced   words ", 20], ["spaced words"]]],
        "gen": lambda r: [" ".join(r.sample(WORDS, r.randint(3, 7))), r.randint(6, 16)],
    },
    {
        "name": "base_convert",
        "spec": "Given a non-negative number written in base b1 with lowercase digits 0-9 then a-z, return it written in base b2 in the same digit alphabet. Both bases are between 2 and 36. Zero is '0'.",
        "signature": "def solve(digits: str, b1: int, b2: int) -> str:",
        "reference": (
            "def solve(digits, b1, b2):\n"
            "    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'\n"
            "    n = int(digits, b1)\n"
            "    if n == 0:\n"
            "        return '0'\n"
            "    out = ''\n"
            "    while n:\n"
            "        out = alphabet[n % b2] + out\n"
            "        n //= b2\n"
            "    return out\n"
        ),
        "tests": [[["ff", 16, 2], "11111111"], [["101", 2, 10], "5"], [["0", 10, 2], "0"],
                  [["z", 36, 10], "35"], [["255", 10, 16], "ff"], [["777", 8, 2], "111111111"],
                  [["10", 36, 10], "36"], [["1000", 2, 8], "10"]],
        "gen": _base,
    },
]


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH):
    return _v1.stream(shape, seed, length)


def self_verify():
    import sandbox

    names = [shape["name"] for shape in SHAPES]
    assert len(names) == len(set(names)), "duplicate shape name"
    assert not set(names) & {shape["name"] for shape in _v1.SHAPES}, "overlaps V1"
    for shape in SHAPES:
        tests = shape["tests"]
        assert len(tests) >= 6, f"{shape['name']}: fewer than 6 hand-written tests"
        run = sandbox.run_function(shape["reference"], [args for args, _ in tests])
        assert run.ok, f"{shape['name']}: reference did not run ({run.error})"
        for result, (args, expected) in zip(run.results, tests):
            assert result["ok"] and sandbox.canonical(result["value"]) == sandbox.canonical(
                expected
            ), f"{shape['name']}: reference disagrees with hand-written test {args}: {result}"
        inputs = stream(shape)
        assert inputs == stream(shape), f"{shape['name']}: stream is not reproducible"
        gold(shape, inputs)
    print(f"self_verify OK: {len(SHAPES)} shapes, {STREAM_LENGTH} requests each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_timing_bench_v2_hard.py sha256:", bench_sha256())
