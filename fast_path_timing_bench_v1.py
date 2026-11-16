"""Task shapes and request streams for the fast-path timing experiment V1.

Each shape has a specification, a ``solve`` signature, a reference
implementation, hand-written tests whose expected values come from the
specification, and a seeded generator of request arguments. Gold for a
generated request is the reference implementation's output; the reference
earns that role only by passing every hand-written test.

None of these shapes appears in ``vendor/ccc_code_items.py`` or
``fast_path_gold_items_v1.py``.

Run ``python fast_path_timing_bench_v1.py`` to self-verify and print the SHA-256.
"""

from __future__ import annotations

import random

STREAM_SEED = 20261116
STREAM_LENGTH = 30

WORDS = (
    "amber basil cedar delta ember fable grove harbor island jungle kettle "
    "lantern meadow nectar orchid pebble quartz ribbon saddle timber umbra "
    "velvet willow yonder zephyr anchor breeze candle dagger engine falcon "
    "garnet hollow ivory jasper kernel ladder marble needle oyster pillar "
    "quiver rocket silver tunnel violet walnut"
).split()
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _ints(r, low, high, shortest, longest):
    return [r.randint(low, high) for _ in range(r.randint(shortest, longest))]


def _phrase(r, shortest, longest):
    return " ".join(r.sample(WORDS, r.randint(shortest, longest)))


def _mixed_case(r):
    return "".join(c.upper() if r.random() < 0.3 else c for c in _phrase(r, 1, 3))


def _mutated(r):
    word = r.choice(WORDS)
    other = "".join(r.choice(LETTERS) if r.random() < 0.4 else c for c in word)
    return [word, other]


def _maybe_sorted(r):
    items = _ints(r, 0, 30, 2, 6)
    return [sorted(items) if r.random() < 0.5 else items]


def _same_ends(r):
    word = r.choice(WORDS)
    if r.random() < 0.5:
        word += word[0].upper() if r.random() < 0.5 else word[0]
    return [word]


def _clamp(r):
    low = r.randint(-50, 50)
    return [r.randint(-100, 150), low, low + r.randint(0, 60)]


def _range(r):
    start = r.randint(-50, 100)
    return [start, start + r.randint(0, 60)]


def _char_of_phrase(r):
    text = _phrase(r, 2, 2)
    return [text, r.choice(text.replace(" ", "")) if r.random() < 0.8 else r.choice(LETTERS)]


def _zip(r):
    keys = r.sample(WORDS, r.randint(0, 4))
    return [keys, _ints(r, 0, 99, max(0, len(keys) - 1), len(keys) + 1)]


SHAPES = [
    {
        "name": "reverse_words",
        "spec": "Return the whitespace-separated words of the string in reverse order, joined by single spaces.",
        "signature": "def solve(s: str) -> str:",
        "reference": "def solve(s):\n    return ' '.join(reversed(s.split()))\n",
        "tests": [[["hello world"], "world hello"], [["one"], "one"], [[""], ""],
                  [["a b c"], "c b a"], [["  spaced   out  "], "out spaced"], [["x y"], "y x"]],
        "gen": lambda r: [_phrase(r, 2, 6)],
    },
    {
        "name": "sum_of_digits",
        "spec": "Return the sum of the decimal digits of a non-negative integer.",
        "signature": "def solve(n: int) -> int:",
        "reference": "def solve(n):\n    return sum(int(c) for c in str(n))\n",
        "tests": [[[0], 0], [[7], 7], [[19], 10], [[999], 27], [[1001], 2], [[12345], 15]],
        "gen": lambda r: [r.randint(0, 10 ** 7)],
    },
    {
        "name": "fizzbuzz",
        "spec": "For a positive integer n return 'FizzBuzz' if n is divisible by 15, 'Fizz' if divisible by 3, 'Buzz' if divisible by 5, otherwise n as a decimal string.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    if n % 15 == 0:\n        return 'FizzBuzz'\n"
            "    if n % 3 == 0:\n        return 'Fizz'\n"
            "    if n % 5 == 0:\n        return 'Buzz'\n"
            "    return str(n)\n"
        ),
        "tests": [[[1], "1"], [[3], "Fizz"], [[5], "Buzz"], [[15], "FizzBuzz"],
                  [[9], "Fizz"], [[10], "Buzz"], [[30], "FizzBuzz"], [[7], "7"]],
        "gen": lambda r: [r.randint(1, 400)],
    },
    {
        "name": "count_char",
        "spec": "Return how many times the single character ch occurs in the string s. The comparison is case-sensitive.",
        "signature": "def solve(s: str, ch: str) -> int:",
        "reference": "def solve(s, ch):\n    return s.count(ch)\n",
        "tests": [[["banana", "a"], 3], [["banana", "b"], 1], [["banana", "z"], 0],
                  [["", "a"], 0], [["Aa", "a"], 1], [["mississippi", "s"], 4]],
        "gen": _char_of_phrase,
    },
    {
        "name": "is_prime",
        "spec": "Return whether a positive integer is a prime number. 1 is not prime.",
        "signature": "def solve(n: int) -> bool:",
        "reference": (
            "def solve(n):\n"
            "    if n < 2:\n        return False\n"
            "    d = 2\n"
            "    while d * d <= n:\n"
            "        if n % d == 0:\n            return False\n"
            "        d += 1\n"
            "    return True\n"
        ),
        "tests": [[[2], True], [[3], True], [[4], False], [[1], False],
                  [[17], True], [[21], False], [[97], True], [[100], False]],
        "gen": lambda r: [r.randint(1, 600)],
    },
    {
        "name": "clamp",
        "spec": "Given integers x, lo and hi with lo <= hi, return x limited to the range lo to hi inclusive.",
        "signature": "def solve(x: int, lo: int, hi: int) -> int:",
        "reference": "def solve(x, lo, hi):\n    return max(lo, min(hi, x))\n",
        "tests": [[[5, 0, 10], 5], [[-3, 0, 10], 0], [[15, 0, 10], 10],
                  [[0, 0, 10], 0], [[10, 0, 10], 10], [[7, 7, 7], 7]],
        "gen": _clamp,
    },
    {
        "name": "swap_pairs",
        "spec": "Swap each pair of adjacent elements of the list: positions 0 and 1, then 2 and 3, and so on. A final unpaired element stays in place.",
        "signature": "def solve(items: list) -> list:",
        "reference": (
            "def solve(items):\n"
            "    out = list(items)\n"
            "    for i in range(0, len(out) - 1, 2):\n"
            "        out[i], out[i + 1] = out[i + 1], out[i]\n"
            "    return out\n"
        ),
        "tests": [[[[1, 2, 3, 4]], [2, 1, 4, 3]], [[[1, 2, 3]], [2, 1, 3]], [[[]], []],
                  [[[9]], [9]], [[["a", "b"]], ["b", "a"]], [[[1, 2, 3, 4, 5]], [2, 1, 4, 3, 5]]],
        "gen": lambda r: [_ints(r, 0, 99, 2, 8)],
    },
    {
        "name": "interleave",
        "spec": "Interleave two lists, taking elements alternately starting with the first list. When one list runs out, append the rest of the other.",
        "signature": "def solve(a: list, b: list) -> list:",
        "reference": (
            "def solve(a, b):\n"
            "    out = []\n"
            "    for i in range(max(len(a), len(b))):\n"
            "        if i < len(a):\n            out.append(a[i])\n"
            "        if i < len(b):\n            out.append(b[i])\n"
            "    return out\n"
        ),
        "tests": [[[[1, 2, 3], [4, 5, 6]], [1, 4, 2, 5, 3, 6]], [[[1], [2, 3, 4]], [1, 2, 3, 4]],
                  [[[1, 2, 3], [9]], [1, 9, 2, 3]], [[[], [1, 2]], [1, 2]], [[[], []], []],
                  [[["a", "b"], ["x", "y"]], ["a", "x", "b", "y"]]],
        "gen": lambda r: [_ints(r, 0, 50, 0, 5), _ints(r, 0, 50, 0, 5)],
    },
    {
        "name": "range_sum",
        "spec": "Given integers a and b with a <= b, return the sum of every integer from a to b inclusive.",
        "signature": "def solve(a: int, b: int) -> int:",
        "reference": "def solve(a, b):\n    return (a + b) * (b - a + 1) // 2\n",
        "tests": [[[1, 10], 55], [[5, 5], 5], [[-2, 2], 0], [[0, 0], 0],
                  [[3, 6], 18], [[-5, -3], -12], [[1, 100], 5050]],
        "gen": _range,
    },
    {
        "name": "repeat_each_char",
        "spec": "Return the string with each character repeated n times in place, where n is a non-negative integer.",
        "signature": "def solve(s: str, n: int) -> str:",
        "reference": "def solve(s, n):\n    return ''.join(c * n for c in s)\n",
        "tests": [[["abc", 2], "aabbcc"], [["a", 3], "aaa"], [["", 5], ""],
                  [["xy", 1], "xy"], [["xy", 0], ""], [["hi!", 2], "hhii!!"]],
        "gen": lambda r: [r.choice(WORDS), r.randint(1, 4)],
    },
    {
        "name": "max_minus_min",
        "spec": "Return the difference between the largest and smallest elements of a non-empty list of integers.",
        "signature": "def solve(nums: list) -> int:",
        "reference": "def solve(nums):\n    return max(nums) - min(nums)\n",
        "tests": [[[[1, 2, 3]], 2], [[[5]], 0], [[[-1, -5, 3]], 8],
                  [[[7, 7, 7]], 0], [[[10, 2]], 8], [[[0, 100, 50]], 100]],
        "gen": lambda r: [_ints(r, -50, 99, 1, 7)],
    },
    {
        "name": "count_evens",
        "spec": "Return how many elements of a list of integers are even.",
        "signature": "def solve(nums: list) -> int:",
        "reference": "def solve(nums):\n    return sum(1 for n in nums if n % 2 == 0)\n",
        "tests": [[[[1, 2, 3, 4]], 2], [[[]], 0], [[[1, 3, 5]], 0],
                  [[[0]], 1], [[[-2, -3, 8]], 2], [[[2, 2, 2]], 3]],
        "gen": lambda r: [_ints(r, -20, 99, 0, 8)],
    },
    {
        "name": "zero_pad",
        "spec": "Return the non-negative integer n as a decimal string, padded on the left with zeros to at least the given width. A longer number is returned unchanged.",
        "signature": "def solve(n: int, width: int) -> str:",
        "reference": "def solve(n, width):\n    s = str(n)\n    return '0' * (width - len(s)) + s\n",
        "tests": [[[5, 3], "005"], [[42, 5], "00042"], [[123, 3], "123"], [[1234, 2], "1234"],
                  [[0, 1], "0"], [[0, 4], "0000"], [[7, 1], "7"]],
        "gen": lambda r: [r.randint(0, 99999), r.randint(1, 8)],
    },
    {
        "name": "hamming_distance",
        "spec": "Given two strings of equal length, return the number of positions at which their characters differ.",
        "signature": "def solve(a: str, b: str) -> int:",
        "reference": "def solve(a, b):\n    return sum(1 for x, y in zip(a, b) if x != y)\n",
        "tests": [[["karolin", "kathrin"], 3], [["abc", "abc"], 0], [["", ""], 0],
                  [["a", "b"], 1], [["1011101", "1001001"], 2], [["abcd", "dcba"], 4]],
        "gen": _mutated,
    },
    {
        "name": "seconds_to_hms",
        "spec": "Convert a non-negative number of seconds to 'H:MM:SS', where hours are not padded and may exceed 23, and minutes and seconds always have two digits.",
        "signature": "def solve(n: int) -> str:",
        "reference": (
            "def solve(n):\n"
            "    h, rest = divmod(n, 3600)\n"
            "    m, s = divmod(rest, 60)\n"
            "    return str(h) + ':' + str(m).zfill(2) + ':' + str(s).zfill(2)\n"
        ),
        "tests": [[[0], "0:00:00"], [[59], "0:00:59"], [[60], "0:01:00"], [[3600], "1:00:00"],
                  [[3661], "1:01:01"], [[86399], "23:59:59"], [[90000], "25:00:00"]],
        "gen": lambda r: [r.randint(0, 200000)],
    },
    {
        "name": "is_sorted",
        "spec": "Return whether a list of integers is in non-decreasing order. Lists with fewer than two elements are sorted.",
        "signature": "def solve(nums: list) -> bool:",
        "reference": "def solve(nums):\n    return all(nums[i] <= nums[i + 1] for i in range(len(nums) - 1))\n",
        "tests": [[[[1, 2, 3]], True], [[[1, 1, 2]], True], [[[3, 2, 1]], False],
                  [[[]], True], [[[5]], True], [[[1, 3, 2]], False]],
        "gen": _maybe_sorted,
    },
    {
        "name": "last_word_length",
        "spec": "Return the length of the last whitespace-separated word in the string, or 0 if there is no word.",
        "signature": "def solve(s: str) -> int:",
        "reference": "def solve(s):\n    words = s.split()\n    return len(words[-1]) if words else 0\n",
        "tests": [[["hello world"], 5], [["fly me to the moon  "], 4], [[""], 0],
                  [["single"], 6], [["   "], 0], [["a bc"], 2]],
        "gen": lambda r: [_phrase(r, 1, 5) + " " * r.randint(0, 2)],
    },
    {
        "name": "abbreviate",
        "spec": "Abbreviate a word as its first letter, the count of letters between the first and last, and its last letter, so 'localization' becomes 'l10n'. Words of three letters or fewer are returned unchanged.",
        "signature": "def solve(word: str) -> str:",
        "reference": (
            "def solve(word):\n"
            "    if len(word) <= 3:\n        return word\n"
            "    return word[0] + str(len(word) - 2) + word[-1]\n"
        ),
        "tests": [[["internationalization"], "i18n"], [["localization"], "l10n"], [["cat"], "cat"],
                  [["word"], "w2d"], [["a"], "a"], [[""], ""], [["kubernetes"], "k8s"]],
        "gen": lambda r: [r.choice(WORDS)],
    },
    {
        "name": "sum_odd_indexed",
        "spec": "Return the sum of the elements at odd indices (1, 3, 5, ...) of a list of integers, using zero-based indexing.",
        "signature": "def solve(nums: list) -> int:",
        "reference": "def solve(nums):\n    return sum(nums[1::2])\n",
        "tests": [[[[1, 2, 3, 4]], 6], [[[]], 0], [[[5]], 0], [[[1, 10]], 10],
                  [[[0, 1, 0, 1, 0, 1]], 3], [[[4, -2, 7, -3]], -5]],
        "gen": lambda r: [_ints(r, -20, 60, 0, 8)],
    },
    {
        "name": "same_ends",
        "spec": "Return whether the first and last characters of the string are the same letter, ignoring case. The empty string gives false.",
        "signature": "def solve(s: str) -> bool:",
        "reference": "def solve(s):\n    return bool(s) and s[0].lower() == s[-1].lower()\n",
        "tests": [[["abca"], True], [["Abca"], True], [["abc"], False],
                  [["a"], True], [[""], False], [["xyX"], True]],
        "gen": _same_ends,
    },
    {
        "name": "digit_count",
        "spec": "Return how many times the digit d (0 to 9) appears in the decimal form of the non-negative integer n.",
        "signature": "def solve(n: int, d: int) -> int:",
        "reference": "def solve(n, d):\n    return str(n).count(str(d))\n",
        "tests": [[[1231, 1], 2], [[0, 0], 1], [[1000, 0], 3],
                  [[999, 9], 3], [[12345, 6], 0], [[7, 7], 1]],
        "gen": lambda r: [r.randint(0, 10 ** 7), r.randint(0, 9)],
    },
    {
        "name": "filter_longer",
        "spec": "Return the words whose length is strictly greater than n, in their original order.",
        "signature": "def solve(words: list, n: int) -> list:",
        "reference": "def solve(words, n):\n    return [w for w in words if len(w) > n]\n",
        "tests": [[[["a", "bb", "ccc"], 1], ["bb", "ccc"]], [[["a", "bb", "ccc"], 3], []],
                  [[[], 2], []], [[["hello", "hi"], 2], ["hello"]],
                  [[["x", "y"], 0], ["x", "y"]], [[["abc", "de", "fgh"], 2], ["abc", "fgh"]]],
        "gen": lambda r: [r.sample(WORDS, r.randint(2, 6)), r.randint(4, 6)],
    },
    {
        "name": "zip_to_object",
        "spec": "Pair keys with values by position and return them as an object. If one list is longer, its extra elements are ignored.",
        "signature": "def solve(keys: list, values: list) -> dict:",
        "reference": "def solve(keys, values):\n    return dict(zip(keys, values))\n",
        "tests": [[[["a", "b"], [1, 2]], {"a": 1, "b": 2}], [[["a", "b", "c"], [1, 2]], {"a": 1, "b": 2}],
                  [[["a"], [1, 2, 3]], {"a": 1}], [[[], []], {}],
                  [[["x"], ["y"]], {"x": "y"}], [[["k1", "k2"], [True, None]], {"k1": True, "k2": None}]],
        "gen": _zip,
    },
    {
        "name": "fibonacci",
        "spec": "Return the n-th Fibonacci number for a non-negative integer n, where F(0) = 0 and F(1) = 1.",
        "signature": "def solve(n: int) -> int:",
        "reference": "def solve(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n",
        "tests": [[[0], 0], [[1], 1], [[2], 1], [[10], 55], [[20], 6765], [[30], 832040], [[7], 13]],
        "gen": lambda r: [r.randint(0, 45)],
    },
    {
        "name": "remove_char",
        "spec": "Return the string s with every occurrence of the single character ch removed. The comparison is case-sensitive.",
        "signature": "def solve(s: str, ch: str) -> str:",
        "reference": "def solve(s, ch):\n    return s.replace(ch, '')\n",
        "tests": [[["banana", "a"], "bnn"], [["banana", "z"], "banana"], [["", "a"], ""],
                  [["aaa", "a"], ""], [["Hello", "l"], "Heo"], [["a-b-c", "-"], "abc"]],
        "gen": _char_of_phrase,
    },
    {
        "name": "absolute_differences",
        "spec": "Return the list of absolute differences between each pair of consecutive elements. A list with fewer than two elements gives an empty list.",
        "signature": "def solve(nums: list) -> list:",
        "reference": "def solve(nums):\n    return [abs(nums[i + 1] - nums[i]) for i in range(len(nums) - 1)]\n",
        "tests": [[[[1, 4, 9]], [3, 5]], [[[5]], []], [[[]], []],
                  [[[3, 3, 3]], [0, 0]], [[[10, 2, 7]], [8, 5]], [[[-1, 1]], [2]]],
        "gen": lambda r: [_ints(r, -30, 60, 2, 7)],
    },
    {
        "name": "join_with_and",
        "spec": "Join a list of words as an English list: all but the last separated by ', ' and the last joined with ' and '. One word is returned alone and an empty list gives the empty string.",
        "signature": "def solve(words: list) -> str:",
        "reference": (
            "def solve(words):\n"
            "    if not words:\n        return ''\n"
            "    if len(words) == 1:\n        return words[0]\n"
            "    return ', '.join(words[:-1]) + ' and ' + words[-1]\n"
        ),
        "tests": [[[[]], ""], [[["a"]], "a"], [[["a", "b"]], "a and b"], [[["a", "b", "c"]], "a, b and c"],
                  [[["x", "y", "z", "w"]], "x, y, z and w"], [[["tea", "milk"]], "tea and milk"]],
        "gen": lambda r: [r.sample(WORDS, r.randint(1, 5))],
    },
    {
        "name": "count_uppercase",
        "spec": "Return how many characters of the string are uppercase letters.",
        "signature": "def solve(s: str) -> int:",
        "reference": "def solve(s):\n    return sum(1 for c in s if c.isupper())\n",
        "tests": [[["Hello World"], 2], [[""], 0], [["abc"], 0], [["ABC"], 3],
                  [["a1B2c3D"], 2], [["mIxEd CaSe"], 4]],
        "gen": lambda r: [_mixed_case(r)],
    },
    {
        "name": "popcount",
        "spec": "Return the number of 1 bits in the binary representation of a non-negative integer.",
        "signature": "def solve(n: int) -> int:",
        "reference": "def solve(n):\n    return bin(n).count('1')\n",
        "tests": [[[0], 0], [[1], 1], [[2], 1], [[3], 2], [[255], 8], [[256], 1], [[1023], 10], [[10], 2]],
        "gen": lambda r: [r.randint(0, 4095)],
    },
    {
        "name": "floor_multiple",
        "spec": "Given a non-negative integer n and a positive integer m, return the largest multiple of m that is less than or equal to n.",
        "signature": "def solve(n: int, m: int) -> int:",
        "reference": "def solve(n, m):\n    return n - n % m\n",
        "tests": [[[10, 3], 9], [[9, 3], 9], [[0, 5], 0], [[4, 5], 0], [[100, 7], 98], [[17, 1], 17]],
        "gen": lambda r: [r.randint(0, 1000), r.randint(1, 25)],
    },
]


def stream(shape, seed=STREAM_SEED, length=STREAM_LENGTH):
    """Return ``length`` distinct argument lists for a shape, fixed by ``seed``."""
    import json

    rng = random.Random(f"{seed}:{shape['name']}")
    seen, out = set(), []
    for _ in range(length * 200):
        args = shape["gen"](rng)
        key = json.dumps(args, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(args)
            if len(out) == length:
                return out
    raise ValueError(f"{shape['name']}: generator cannot supply {length} distinct inputs")


def gold(shape, inputs):
    """Reference outputs for ``inputs``, computed in the sandbox."""
    import sandbox

    run = sandbox.run_function(shape["reference"], inputs, timeout_seconds=10.0)
    if not run.ok or not all(result["ok"] for result in run.results):
        raise ValueError(f"{shape['name']}: reference failed on a generated input")
    return [result["value"] for result in run.results]


def self_verify():
    import sandbox

    names = [shape["name"] for shape in SHAPES]
    assert len(names) == len(set(names)), "duplicate shape name"
    for shape in SHAPES:
        tests = shape["tests"]
        assert len(tests) >= 6, f"{shape['name']}: fewer than 6 hand-written tests"
        run = sandbox.run_function(shape["reference"], [args for args, _ in tests])
        assert run.ok, f"{shape['name']}: reference did not run ({run.error})"
        for result, (args, expected) in zip(run.results, tests):
            assert result["ok"] and sandbox.canonical(result["value"]) == sandbox.canonical(
                expected
            ), f"{shape['name']}: reference disagrees with hand-written test {args}"
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
    print("fast_path_timing_bench_v1.py sha256:", bench_sha256())
