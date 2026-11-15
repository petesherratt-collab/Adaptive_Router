"""Fresh gold items for measuring the fast-path promotion gate.

Built to the Contextual Conclusion Capture code-item recipe. Each item has:

  - ``spec``      : natural-language specification;
  - ``signature`` : the ``solve`` signature;
  - ``reference`` : a correct implementation (passes every test);
  - ``buggy``     : a plausible single-bug implementation (fails >= 1 test);
  - ``bug_desc``  : one-line description of the injected fault;
  - ``tests``     : ``[args, expected]`` pairs, written by hand from the spec
                    and not derived from the reference.

Gold is mechanical: a candidate is correct when it passes every test in the
sandbox. No model decides the gold. Arguments and results are JSON values and
comparison is type-strict.

Run ``python fast_path_gold_items_v1.py`` to self-verify and print the SHA-256.
"""

from __future__ import annotations

ITEMS = [
    {
        "name": "slugify",
        "spec": "Lowercase the string, replace every maximal run of characters "
                "other than a-z and 0-9 with a single hyphen, then remove any "
                "leading or trailing hyphen.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "import re\n"
            "def solve(s):\n"
            "    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')\n"
        ),
        "buggy": (
            "import re\n"
            "def solve(s):\n"
            "    return re.sub(r'[^a-z0-9]+', '-', s.lower())\n"
        ),
        "bug_desc": "does not strip leading or trailing hyphens.",
        "tests": [
            [["Hello World"], "hello-world"],
            [["  Hello, World!  "], "hello-world"],
            [["already-slug"], "already-slug"],
            [["A  B"], "a-b"],
            [["C++ & Rust"], "c-rust"],
            [[""], ""],
            [["100% Pure"], "100-pure"],
            [["under_score"], "under-score"],
            [["Trailing!"], "trailing"],
        ],
    },
    {
        "name": "parse_duration",
        "spec": "Parse a duration written as optional hours, minutes and "
                "seconds in that order, such as '1h30m15s', '45s' or '2h5s', "
                "and return the total number of seconds. The empty string is 0.",
        "signature": "def solve(s: str) -> int:",
        "reference": (
            "import re\n"
            "def solve(s):\n"
            "    m = re.fullmatch(r'(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?', s)\n"
            "    h, mi, se = (int(x) if x else 0 for x in m.groups())\n"
            "    return h * 3600 + mi * 60 + se\n"
        ),
        "buggy": (
            "import re\n"
            "def solve(s):\n"
            "    m = re.fullmatch(r'(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?', s)\n"
            "    h, mi, se = (int(x) if x else 0 for x in m.groups())\n"
            "    return h * 60 + mi * 60 + se\n"
        ),
        "bug_desc": "counts an hour as 60 seconds.",
        "tests": [
            [["1h30m15s"], 5415],
            [["45s"], 45],
            [["2m"], 120],
            [["1h"], 3600],
            [["10m5s"], 605],
            [["2h5s"], 7205],
            [[""], 0],
            [["90m"], 5400],
            [["1h1m1s"], 3661],
        ],
    },
    {
        "name": "format_thousands",
        "spec": "Format an integer with a comma between each group of three "
                "digits counted from the right. A negative number keeps its "
                "leading minus sign.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    sign = '-' if n < 0 else ''\n"
            "    digits = str(abs(n))\n"
            "    groups = []\n"
            "    while digits:\n"
            "        groups.append(digits[-3:])\n"
            "        digits = digits[:-3]\n"
            "    return sign + ','.join(reversed(groups))\n"
        ),
        "buggy": (
            "def solve(n):\n"
            "    digits = str(n)\n"
            "    groups = []\n"
            "    while digits:\n"
            "        groups.append(digits[-3:])\n"
            "        digits = digits[:-3]\n"
            "    return ','.join(reversed(groups))\n"
        ),
        "bug_desc": "groups the minus sign as if it were a digit.",
        "tests": [
            [[0], "0"],
            [[7], "7"],
            [[999], "999"],
            [[1000], "1,000"],
            [[1234567], "1,234,567"],
            [[-1234], "-1,234"],
            [[-123], "-123"],
            [[-123456], "-123,456"],
            [[100000], "100,000"],
        ],
    },
    {
        "name": "median",
        "spec": "Return the median of a non-empty list of integers. For an odd "
                "count return the middle element of the sorted list as an "
                "integer. For an even count return the mean of the two middle "
                "elements as a float.",
        "signature": "def solve(nums: list):",
        "reference": (
            "def solve(nums):\n"
            "    s = sorted(nums)\n"
            "    mid = len(s) // 2\n"
            "    if len(s) % 2:\n"
            "        return s[mid]\n"
            "    return (s[mid - 1] + s[mid]) / 2\n"
        ),
        "buggy": (
            "def solve(nums):\n"
            "    s = nums\n"
            "    mid = len(s) // 2\n"
            "    if len(s) % 2:\n"
            "        return s[mid]\n"
            "    return (s[mid - 1] + s[mid]) / 2\n"
        ),
        "bug_desc": "does not sort the input.",
        "tests": [
            [[[1, 2, 3]], 2],
            [[[3, 1, 2]], 2],
            [[[1, 2, 3, 4]], 2.5],
            [[[4, 1, 3, 2]], 2.5],
            [[[5]], 5],
            [[[2, 2]], 2.0],
            [[[10, -2, 7]], 7],
            [[[1, 3]], 2.0],
            [[[9, 1, 5, 3, 7]], 5],
        ],
    },
    {
        "name": "merge_intervals",
        "spec": "Given a list of closed integer intervals [start, end], return "
                "the merged intervals sorted by start. Intervals that overlap "
                "or touch, such as [1, 2] and [2, 3], are merged.",
        "signature": "def solve(intervals: list) -> list:",
        "reference": (
            "def solve(intervals):\n"
            "    out = []\n"
            "    for a, b in sorted(intervals):\n"
            "        if out and a <= out[-1][1]:\n"
            "            out[-1][1] = max(out[-1][1], b)\n"
            "        else:\n"
            "            out.append([a, b])\n"
            "    return out\n"
        ),
        "buggy": (
            "def solve(intervals):\n"
            "    out = []\n"
            "    for a, b in sorted(intervals):\n"
            "        if out and a < out[-1][1]:\n"
            "            out[-1][1] = max(out[-1][1], b)\n"
            "        else:\n"
            "            out.append([a, b])\n"
            "    return out\n"
        ),
        "bug_desc": "does not merge intervals that only touch.",
        "tests": [
            [[[[1, 3], [2, 6], [8, 10]]], [[1, 6], [8, 10]]],
            [[[[1, 2], [2, 3]]], [[1, 3]]],
            [[[]], []],
            [[[[5, 7]]], [[5, 7]]],
            [[[[8, 10], [1, 3], [2, 6]]], [[1, 6], [8, 10]]],
            [[[[1, 10], [2, 3]]], [[1, 10]]],
            [[[[1, 2], [3, 4]]], [[1, 2], [3, 4]]],
            [[[[1, 4], [4, 5], [5, 9]]], [[1, 9]]],
            [[[[1, 5], [1, 5]]], [[1, 5]]],
        ],
    },
    {
        "name": "dedupe_keep_first",
        "spec": "Remove duplicate elements from a list, keeping the first "
                "occurrence of each element and preserving that order.",
        "signature": "def solve(items: list) -> list:",
        "reference": (
            "def solve(items):\n"
            "    out = []\n"
            "    for x in items:\n"
            "        if x not in out:\n"
            "            out.append(x)\n"
            "    return out\n"
        ),
        "buggy": (
            "def solve(items):\n"
            "    out = []\n"
            "    for i, x in enumerate(items):\n"
            "        if x not in items[i + 1:]:\n"
            "            out.append(x)\n"
            "    return out\n"
        ),
        "bug_desc": "keeps the last occurrence instead of the first.",
        "tests": [
            [[[1, 2, 1, 3]], [1, 2, 3]],
            [[[1, 1, 1]], [1]],
            [[[]], []],
            [[["a", "b", "a"]], ["a", "b"]],
            [[[1, 2, 3]], [1, 2, 3]],
            [[[3, 3, 4, 4]], [3, 4]],
            [[[5, 6, 5, 6]], [5, 6]],
            [[[2, 1, 2]], [2, 1]],
            [[["x"]], ["x"]],
        ],
    },
    {
        "name": "camel_to_snake",
        "spec": "Insert an underscore before every uppercase letter except one "
                "at position 0, then lowercase the whole string.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "def solve(s):\n"
            "    out = []\n"
            "    for i, ch in enumerate(s):\n"
            "        if ch.isupper():\n"
            "            if i:\n"
            "                out.append('_')\n"
            "            out.append(ch.lower())\n"
            "        else:\n"
            "            out.append(ch)\n"
            "    return ''.join(out)\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    out = []\n"
            "    for ch in s:\n"
            "        if ch.isupper():\n"
            "            out.append('_')\n"
            "            out.append(ch.lower())\n"
            "        else:\n"
            "            out.append(ch)\n"
            "    return ''.join(out)\n"
        ),
        "bug_desc": "adds a leading underscore when the first letter is uppercase.",
        "tests": [
            [["camelCase"], "camel_case"],
            [["simple"], "simple"],
            [["CamelCase"], "camel_case"],
            [["aB"], "a_b"],
            [[""], ""],
            [["getHTTP"], "get_h_t_t_p"],
            [["X"], "x"],
            [["userId2"], "user_id2"],
            [["already_snake"], "already_snake"],
        ],
    },
    {
        "name": "parse_key_values",
        "spec": "Parse segments separated by ';' into an object. Each segment "
                "is split at its first '='; whitespace around the key and "
                "around the value is removed. A segment with no '=' is "
                "ignored. A repeated key keeps its last value.",
        "signature": "def solve(s: str) -> dict:",
        "reference": (
            "def solve(s):\n"
            "    out = {}\n"
            "    for part in s.split(';'):\n"
            "        if '=' not in part:\n"
            "            continue\n"
            "        k, v = part.split('=', 1)\n"
            "        out[k.strip()] = v.strip()\n"
            "    return out\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    out = {}\n"
            "    for part in s.split(';'):\n"
            "        if '=' not in part:\n"
            "            continue\n"
            "        k, v = part.split('=', 1)\n"
            "        out[k] = v\n"
            "    return out\n"
        ),
        "bug_desc": "does not trim whitespace around keys and values.",
        "tests": [
            [["a=1;b=2"], {"a": "1", "b": "2"}],
            [["a = 1 ; b=2"], {"a": "1", "b": "2"}],
            [[""], {}],
            [["a=1;;b=2"], {"a": "1", "b": "2"}],
            [["k=v=w"], {"k": "v=w"}],
            [["x=1;x=2"], {"x": "2"}],
            [[" key=value "], {"key": "value"}],
            [["novalue;a=1"], {"a": "1"}],
            [["e="], {"e": ""}],
        ],
    },
    {
        "name": "truncate_ellipsis",
        "spec": "Given a string and a maximum length n of at least 3: if the "
                "string has at most n characters return it unchanged; "
                "otherwise return its first n - 3 characters followed by '...'.",
        "signature": "def solve(s: str, n: int) -> str:",
        "reference": (
            "def solve(s, n):\n"
            "    if len(s) <= n:\n"
            "        return s\n"
            "    return s[:n - 3] + '...'\n"
        ),
        "buggy": (
            "def solve(s, n):\n"
            "    if len(s) < n:\n"
            "        return s\n"
            "    return s[:n - 3] + '...'\n"
        ),
        "bug_desc": "truncates a string whose length equals the limit.",
        "tests": [
            [["hello world", 8], "hello..."],
            [["hello", 5], "hello"],
            [["hello", 10], "hello"],
            [["abcdef", 3], "..."],
            [["abcdef", 5], "ab..."],
            [["", 3], ""],
            [["abc", 3], "abc"],
            [["abcd", 3], "..."],
            [["truncate me", 11], "truncate me"],
        ],
    },
    {
        "name": "is_leap_year",
        "spec": "Return whether a year is a leap year in the Gregorian "
                "calendar: divisible by 4, except century years, which must be "
                "divisible by 400.",
        "signature": "def solve(year: int) -> bool:",
        "reference": (
            "def solve(year):\n"
            "    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n"
        ),
        "buggy": (
            "def solve(year):\n"
            "    return year % 4 == 0 and year % 100 != 0\n"
        ),
        "bug_desc": "omits the divisible-by-400 rule.",
        "tests": [
            [[2024], True],
            [[2023], False],
            [[1900], False],
            [[2000], True],
            [[2100], False],
            [[1996], True],
            [[1600], True],
            [[2019], False],
        ],
    },
    {
        "name": "day_of_year",
        "spec": "Given a Gregorian year, month and day, return the day's "
                "ordinal position within the year, where 1 January is 1.",
        "signature": "def solve(year: int, month: int, day: int) -> int:",
        "reference": (
            "def solve(year, month, day):\n"
            "    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]\n"
            "    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):\n"
            "        days[1] = 29\n"
            "    return sum(days[:month - 1]) + day\n"
        ),
        "buggy": (
            "def solve(year, month, day):\n"
            "    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]\n"
            "    return sum(days[:month - 1]) + day\n"
        ),
        "bug_desc": "ignores leap years.",
        "tests": [
            [[2023, 1, 1], 1],
            [[2023, 12, 31], 365],
            [[2024, 12, 31], 366],
            [[2024, 3, 1], 61],
            [[2023, 3, 1], 60],
            [[2024, 2, 29], 60],
            [[2000, 3, 1], 61],
            [[1900, 3, 1], 60],
            [[2024, 1, 31], 31],
        ],
    },
    {
        "name": "chunk_list",
        "spec": "Split a list into consecutive chunks of n elements. The final "
                "chunk may be shorter. An empty list gives an empty list.",
        "signature": "def solve(items: list, n: int) -> list:",
        "reference": (
            "def solve(items, n):\n"
            "    return [items[i:i + n] for i in range(0, len(items), n)]\n"
        ),
        "buggy": (
            "def solve(items, n):\n"
            "    return [items[i:i + n] for i in range(0, len(items) - len(items) % n, n)]\n"
        ),
        "bug_desc": "drops a final partial chunk.",
        "tests": [
            [[[1, 2, 3, 4], 2], [[1, 2], [3, 4]]],
            [[[1, 2, 3, 4, 5], 2], [[1, 2], [3, 4], [5]]],
            [[[], 3], []],
            [[[1], 3], [[1]]],
            [[[1, 2, 3], 1], [[1], [2], [3]]],
            [[[1, 2, 3], 3], [[1, 2, 3]]],
            [[[1, 2, 3, 4, 5, 6, 7], 3], [[1, 2, 3], [4, 5, 6], [7]]],
            [[["a", "b"], 5], [["a", "b"]]],
        ],
    },
    {
        "name": "rotate_right",
        "spec": "Rotate a list to the right by k positions, where k is a "
                "non-negative integer that may exceed the list length. An "
                "empty list stays empty.",
        "signature": "def solve(items: list, k: int) -> list:",
        "reference": (
            "def solve(items, k):\n"
            "    if not items:\n"
            "        return []\n"
            "    k %= len(items)\n"
            "    return items[-k:] + items[:-k] if k else list(items)\n"
        ),
        "buggy": (
            "def solve(items, k):\n"
            "    return items[-k:] + items[:-k] if k else list(items)\n"
        ),
        "bug_desc": "does not reduce k modulo the list length.",
        "tests": [
            [[[1, 2, 3, 4], 1], [4, 1, 2, 3]],
            [[[1, 2, 3, 4], 0], [1, 2, 3, 4]],
            [[[1, 2, 3], 3], [1, 2, 3]],
            [[[1, 2, 3], 4], [3, 1, 2]],
            [[[], 5], []],
            [[[1], 7], [1]],
            [[[1, 2, 3, 4, 5], 2], [4, 5, 1, 2, 3]],
            [[[1, 2], 3], [2, 1]],
            [[[1, 2, 3, 4], 6], [3, 4, 1, 2]],
        ],
    },
    {
        "name": "mask_digits",
        "spec": "Replace every digit with '*' except the last four digits in "
                "the string. Characters that are not digits stay in place and "
                "are not counted.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "def solve(s):\n"
            "    total = sum(ch.isdigit() for ch in s)\n"
            "    seen = 0\n"
            "    out = []\n"
            "    for ch in s:\n"
            "        if ch.isdigit():\n"
            "            seen += 1\n"
            "            out.append(ch if seen > total - 4 else '*')\n"
            "        else:\n"
            "            out.append(ch)\n"
            "    return ''.join(out)\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    keep = len(s) - 4\n"
            "    return ''.join(\n"
            "        '*' if ch.isdigit() and i < keep else ch\n"
            "        for i, ch in enumerate(s)\n"
            "    )\n"
        ),
        "bug_desc": "keeps the last four characters instead of the last four digits.",
        "tests": [
            [["1234567812345678"], "************5678"],
            [["1234 5678 1234 5678"], "**** **** **** 5678"],
            [["1234-5678-12-34"], "****-****-12-34"],
            [["1234"], "1234"],
            [["123"], "123"],
            [["12345"], "*2345"],
            [["12 34 5"], "*2 34 5"],
            [[""], ""],
            [["4111 1111 1111 111 1"], "**** **** **** 111 1"],
        ],
    },
    {
        "name": "count_vowels",
        "spec": "Count the letters a, e, i, o and u in a string, in either case.",
        "signature": "def solve(s: str) -> int:",
        "reference": (
            "def solve(s):\n"
            "    return sum(ch in 'aeiou' for ch in s.lower())\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    return sum(ch in 'aeiou' for ch in s)\n"
        ),
        "bug_desc": "ignores uppercase vowels.",
        "tests": [
            [["hello"], 2],
            [["HELLO"], 2],
            [[""], 0],
            [["rhythm"], 0],
            [["AeIoU"], 5],
            [["banana"], 3],
            [["Umbrella"], 3],
            [["xyz"], 0],
            [["queue"], 4],
        ],
    },
    {
        "name": "longest_common_prefix",
        "spec": "Return the longest string that is a prefix of every string in "
                "the list. An empty list gives the empty string.",
        "signature": "def solve(words: list) -> str:",
        "reference": (
            "def solve(words):\n"
            "    if not words:\n"
            "        return ''\n"
            "    lo, hi = min(words), max(words)\n"
            "    i = 0\n"
            "    while i < len(lo) and i < len(hi) and lo[i] == hi[i]:\n"
            "        i += 1\n"
            "    return lo[:i]\n"
        ),
        "buggy": (
            "def solve(words):\n"
            "    if not words:\n"
            "        return ''\n"
            "    lo, hi = words[0], words[-1]\n"
            "    i = 0\n"
            "    while i < len(lo) and i < len(hi) and lo[i] == hi[i]:\n"
            "        i += 1\n"
            "    return lo[:i]\n"
        ),
        "bug_desc": "compares only the first and last strings as given.",
        "tests": [
            [[["flower", "flow", "flight"]], "fl"],
            [[["dog", "racecar", "car"]], ""],
            [[[]], ""],
            [[["solo"]], "solo"],
            [[["ab", "abc"]], "ab"],
            [[["abc", "x", "abd"]], ""],
            [[["interview", "internet", "inter", "interval"]], "inter"],
            [[["", ""]], ""],
            [[["same", "same"]], "same"],
        ],
    },
    {
        "name": "to_base",
        "spec": "Convert a non-negative integer to its representation in a "
                "base from 2 to 16, using lowercase letters for digits above "
                "9. Zero is '0'.",
        "signature": "def solve(n: int, base: int) -> str:",
        "reference": (
            "def solve(n, base):\n"
            "    digits = '0123456789abcdef'\n"
            "    if n == 0:\n"
            "        return '0'\n"
            "    out = []\n"
            "    while n:\n"
            "        out.append(digits[n % base])\n"
            "        n //= base\n"
            "    return ''.join(reversed(out))\n"
        ),
        "buggy": (
            "def solve(n, base):\n"
            "    digits = '0123456789abcdef'\n"
            "    out = []\n"
            "    while n:\n"
            "        out.append(digits[n % base])\n"
            "        n //= base\n"
            "    return ''.join(reversed(out))\n"
        ),
        "bug_desc": "returns the empty string for zero.",
        "tests": [
            [[0, 2], "0"],
            [[5, 2], "101"],
            [[255, 16], "ff"],
            [[255, 2], "11111111"],
            [[10, 10], "10"],
            [[8, 8], "10"],
            [[0, 16], "0"],
            [[35, 6], "55"],
            [[4095, 16], "fff"],
        ],
    },
    {
        "name": "compare_versions",
        "spec": "Compare two dot-separated version strings numerically, part "
                "by part, treating missing parts as 0. Return -1, 0 or 1 when "
                "the first is lower than, equal to or higher than the second.",
        "signature": "def solve(a: str, b: str) -> int:",
        "reference": (
            "def solve(a, b):\n"
            "    x = [int(p) for p in a.split('.')]\n"
            "    y = [int(p) for p in b.split('.')]\n"
            "    n = max(len(x), len(y))\n"
            "    x += [0] * (n - len(x))\n"
            "    y += [0] * (n - len(y))\n"
            "    return (x > y) - (x < y)\n"
        ),
        "buggy": (
            "def solve(a, b):\n"
            "    x = a.split('.')\n"
            "    y = b.split('.')\n"
            "    n = max(len(x), len(y))\n"
            "    x += ['0'] * (n - len(x))\n"
            "    y += ['0'] * (n - len(y))\n"
            "    return (x > y) - (x < y)\n"
        ),
        "bug_desc": "compares parts as text, not numbers.",
        "tests": [
            [["1.0", "1.0"], 0],
            [["1.2", "1.10"], -1],
            [["2.0", "1.9"], 1],
            [["1.0.0", "1"], 0],
            [["1.2.9", "1.2.10"], -1],
            [["0.9", "1.0"], -1],
            [["1.01", "1.1"], 0],
            [["3", "3.0.1"], -1],
            [["10.0", "9.9"], 1],
        ],
    },
    {
        "name": "is_anagram",
        "spec": "Return whether two strings are anagrams of each other, "
                "ignoring letter case and spaces.",
        "signature": "def solve(a: str, b: str) -> bool:",
        "reference": (
            "def solve(a, b):\n"
            "    def key(s):\n"
            "        return sorted(s.replace(' ', '').lower())\n"
            "    return key(a) == key(b)\n"
        ),
        "buggy": (
            "def solve(a, b):\n"
            "    def key(s):\n"
            "        return sorted(s.lower())\n"
            "    return key(a) == key(b)\n"
        ),
        "bug_desc": "does not ignore spaces.",
        "tests": [
            [["listen", "silent"], True],
            [["Listen", "Silent"], True],
            [["dormitory", "dirty room"], True],
            [["abc", "abd"], False],
            [["", ""], True],
            [["a", "aa"], False],
            [["Astronomer", "Moon starer"], True],
            [["rat", "car"], False],
            [["a b", "ab"], True],
        ],
    },
    {
        "name": "percent_half_up",
        "spec": "Return part as a whole-number percentage of total, rounding "
                "halves up. Both are non-negative integers. If total is 0 "
                "return 0.",
        "signature": "def solve(part: int, total: int) -> int:",
        "reference": (
            "def solve(part, total):\n"
            "    if total == 0:\n"
            "        return 0\n"
            "    return (part * 200 + total) // (2 * total)\n"
        ),
        "buggy": (
            "def solve(part, total):\n"
            "    if total == 0:\n"
            "        return 0\n"
            "    return part * 100 // total\n"
        ),
        "bug_desc": "truncates instead of rounding.",
        "tests": [
            [[1, 2], 50],
            [[1, 3], 33],
            [[2, 3], 67],
            [[1, 8], 13],
            [[0, 5], 0],
            [[5, 5], 100],
            [[7, 0], 0],
            [[1, 6], 17],
            [[1, 4], 25],
        ],
    },
    {
        "name": "normalize_phone",
        "spec": "Keep only the digits of the input. If there are 11 digits and "
                "the first is 1, drop that first digit. If exactly 10 digits "
                "remain return them as '(AAA) BBB-CCCC'; otherwise return null.",
        "signature": "def solve(s: str):",
        "reference": (
            "def solve(s):\n"
            "    d = ''.join(ch for ch in s if ch.isdigit())\n"
            "    if len(d) == 11 and d[0] == '1':\n"
            "        d = d[1:]\n"
            "    if len(d) != 10:\n"
            "        return None\n"
            "    return '(' + d[:3] + ') ' + d[3:6] + '-' + d[6:]\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    d = ''.join(ch for ch in s if ch.isdigit())\n"
            "    if len(d) != 10:\n"
            "        return None\n"
            "    return '(' + d[:3] + ') ' + d[3:6] + '-' + d[6:]\n"
        ),
        "bug_desc": "does not accept a leading country digit 1.",
        "tests": [
            [["555-123-4567"], "(555) 123-4567"],
            [["(555) 123 4567"], "(555) 123-4567"],
            [["1-555-123-4567"], "(555) 123-4567"],
            [["+1 555 123 4567"], "(555) 123-4567"],
            [["12345"], None],
            [["5551234567"], "(555) 123-4567"],
            [["2-555-123-4567"], None],
            [[""], None],
            [["555.123.4567 ext"], "(555) 123-4567"],
        ],
    },
    {
        "name": "transpose",
        "spec": "Transpose a rectangular matrix given as a list of rows. An "
                "empty list gives an empty list.",
        "signature": "def solve(m: list) -> list:",
        "reference": (
            "def solve(m):\n"
            "    if not m:\n"
            "        return []\n"
            "    return [[row[c] for row in m] for c in range(len(m[0]))]\n"
        ),
        "buggy": (
            "def solve(m):\n"
            "    if not m:\n"
            "        return []\n"
            "    return [[row[c] for row in m] for c in range(len(m))]\n"
        ),
        "bug_desc": "assumes the matrix is square.",
        "tests": [
            [[[[1, 2], [3, 4]]], [[1, 3], [2, 4]]],
            [[[[1, 2, 3]]], [[1], [2], [3]]],
            [[[[1], [2], [3]]], [[1, 2, 3]]],
            [[[]], []],
            [[[[5]]], [[5]]],
            [[[[1, 2, 3], [4, 5, 6]]], [[1, 4], [2, 5], [3, 6]]],
            [[[[1, 2], [3, 4], [5, 6]]], [[1, 3, 5], [2, 4, 6]]],
            [[[["a", "b"], ["c", "d"]]], [["a", "c"], ["b", "d"]]],
        ],
    },
    {
        "name": "binary_search",
        "spec": "Given a list of distinct integers sorted ascending and a "
                "target, return the index of the target, or -1 if it is absent.",
        "signature": "def solve(nums: list, target: int) -> int:",
        "reference": (
            "def solve(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        if nums[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1\n"
        ),
        "buggy": (
            "def solve(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo < hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        if nums[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1\n"
        ),
        "bug_desc": "stops before examining the final remaining element.",
        "tests": [
            [[[1, 3, 5, 7, 9], 5], 2],
            [[[1, 3, 5, 7, 9], 1], 0],
            [[[1, 3, 5, 7, 9], 9], 4],
            [[[1, 3, 5, 7, 9], 4], -1],
            [[[], 1], -1],
            [[[2], 2], 0],
            [[[2], 3], -1],
            [[[1, 2], 2], 1],
            [[[1, 3, 5, 7], 7], 3],
        ],
    },
    {
        "name": "expand_ranges",
        "spec": "Expand a comma-separated list of non-negative integers and "
                "inclusive ranges such as '1-3,5,7-8' into the list of "
                "integers in the order written. Spaces around items are "
                "ignored. The empty string gives an empty list.",
        "signature": "def solve(s: str) -> list:",
        "reference": (
            "def solve(s):\n"
            "    out = []\n"
            "    for part in s.split(','):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        if '-' in part:\n"
            "            a, b = part.split('-')\n"
            "            out.extend(range(int(a), int(b) + 1))\n"
            "        else:\n"
            "            out.append(int(part))\n"
            "    return out\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    out = []\n"
            "    for part in s.split(','):\n"
            "        part = part.strip()\n"
            "        if not part:\n"
            "            continue\n"
            "        if '-' in part:\n"
            "            a, b = part.split('-')\n"
            "            out.extend(range(int(a), int(b)))\n"
            "        else:\n"
            "            out.append(int(part))\n"
            "    return out\n"
        ),
        "bug_desc": "treats the end of a range as exclusive.",
        "tests": [
            [["1-3,5,7-8"], [1, 2, 3, 5, 7, 8]],
            [["4"], [4]],
            [[""], []],
            [["1,2,3"], [1, 2, 3]],
            [["2-2"], [2]],
            [["10-12"], [10, 11, 12]],
            [["1, 3-4"], [1, 3, 4]],
            [["5,1-2"], [5, 1, 2]],
            [["7,8,9"], [7, 8, 9]],
        ],
    },
    {
        "name": "hex_to_rgb",
        "spec": "Convert a hex colour, with or without a leading '#', to a "
                "list [red, green, blue] of integers. A three-digit colour "
                "such as 'f80' is shorthand for doubling each digit: 'ff8800'.",
        "signature": "def solve(s: str) -> list:",
        "reference": (
            "def solve(s):\n"
            "    h = s.lstrip('#')\n"
            "    if len(h) == 3:\n"
            "        h = ''.join(ch * 2 for ch in h)\n"
            "    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    h = s.lstrip('#')\n"
            "    if len(h) == 3:\n"
            "        return [int(ch, 16) for ch in h]\n"
            "    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]\n"
        ),
        "bug_desc": "does not double the digits of a three-digit colour.",
        "tests": [
            [["#ff8800"], [255, 136, 0]],
            [["ff8800"], [255, 136, 0]],
            [["#000000"], [0, 0, 0]],
            [["#fff"], [255, 255, 255]],
            [["#f80"], [255, 136, 0]],
            [["000"], [0, 0, 0]],
            [["#FFFFFF"], [255, 255, 255]],
            [["#1a2b3c"], [26, 43, 60]],
            [["abc"], [170, 187, 204]],
        ],
    },
    {
        "name": "ordinal",
        "spec": "Return a positive integer followed by its English ordinal "
                "suffix: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st and so on.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    if 10 <= n % 100 <= 20:\n"
            "        suffix = 'th'\n"
            "    else:\n"
            "        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')\n"
            "    return str(n) + suffix\n"
        ),
        "buggy": (
            "def solve(n):\n"
            "    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')\n"
            "    return str(n) + suffix\n"
        ),
        "bug_desc": "has no exception for 11, 12 and 13.",
        "tests": [
            [[1], "1st"],
            [[2], "2nd"],
            [[3], "3rd"],
            [[4], "4th"],
            [[11], "11th"],
            [[12], "12th"],
            [[13], "13th"],
            [[21], "21st"],
            [[112], "112th"],
            [[100], "100th"],
            [[23], "23rd"],
        ],
    },
    {
        "name": "time_24_to_12",
        "spec": "Convert a 24-hour time 'HH:MM' to 12-hour form 'H:MM AM' or "
                "'H:MM PM' with no leading zero on the hour. Midnight is "
                "12:00 AM and noon is 12:00 PM.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "def solve(s):\n"
            "    h, m = s.split(':')\n"
            "    h = int(h)\n"
            "    suffix = 'AM' if h < 12 else 'PM'\n"
            "    h = h % 12\n"
            "    if h == 0:\n"
            "        h = 12\n"
            "    return str(h) + ':' + m + ' ' + suffix\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    h, m = s.split(':')\n"
            "    h = int(h)\n"
            "    suffix = 'AM' if h < 12 else 'PM'\n"
            "    h = h % 12\n"
            "    return str(h) + ':' + m + ' ' + suffix\n"
        ),
        "bug_desc": "shows hour 0 instead of 12 at midnight and noon.",
        "tests": [
            [["13:05"], "1:05 PM"],
            [["00:00"], "12:00 AM"],
            [["12:30"], "12:30 PM"],
            [["09:15"], "9:15 AM"],
            [["23:59"], "11:59 PM"],
            [["11:00"], "11:00 AM"],
            [["00:45"], "12:45 AM"],
            [["18:20"], "6:20 PM"],
            [["12:00"], "12:00 PM"],
        ],
    },
    {
        "name": "initials",
        "spec": "Return the uppercase first letter of each whitespace-separated "
                "word, each followed by a full stop. Extra spaces are ignored "
                "and the empty string gives the empty string.",
        "signature": "def solve(s: str) -> str:",
        "reference": (
            "def solve(s):\n"
            "    return ''.join(w[0].upper() + '.' for w in s.split())\n"
        ),
        "buggy": (
            "def solve(s):\n"
            "    return ''.join(w[0].upper() + '.' for w in s.split(' '))\n"
        ),
        "bug_desc": "fails on repeated, leading or trailing spaces and on the empty string.",
        "tests": [
            [["john ronald reuel tolkien"], "J.R.R.T."],
            [["ada lovelace"], "A.L."],
            [["  ada   lovelace "], "A.L."],
            [[""], ""],
            [["Cher"], "C."],
            [["mary-jane watson"], "M.W."],
            [["a b c"], "A.B.C."],
            [["grace  hopper"], "G.H."],
            [["alan turing"], "A.T."],
        ],
    },
]


def self_verify():
    """Every reference passes all tests; every buggy variant fails at least one
    and passes at least one; both pass the sandbox's static screen."""
    import sandbox

    names = [item["name"] for item in ITEMS]
    assert len(names) == len(set(names)), "duplicate item name"
    for item in ITEMS:
        calls = [args for args, _ in item["tests"]]
        assert len(calls) >= 8, f"{item['name']}: fewer than 8 tests"
        keys = [sandbox.canonical(args) for args in calls]
        assert len(keys) == len(set(keys)), f"{item['name']}: duplicate test arguments"
        counts = {}
        for kind in ("reference", "buggy"):
            run = sandbox.run_function(item[kind], calls)
            assert run.ok, f"{item['name']}: {kind} did not run ({run.error})"
            counts[kind] = sum(
                result["ok"]
                and sandbox.canonical(result["value"]) == sandbox.canonical(expected)
                for result, (_, expected) in zip(run.results, item["tests"])
            )
        total = len(calls)
        assert counts["reference"] == total, (
            f"{item['name']}: reference failed {total - counts['reference']}/{total}"
        )
        assert 0 < counts["buggy"] < total, (
            f"{item['name']}: buggy variant passed {counts['buggy']}/{total}"
        )
    print(f"self_verify OK: {len(ITEMS)} items")


def items_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_gold_items_v1.py sha256:", items_sha256())
