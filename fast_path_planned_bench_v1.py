"""Plain-language tasks for the planned-jobs experiment V1.

The jobs, inputs and gold are those of ``fast_path_jobs_bench_v2_large.py``.
What changes is what the router is given: instead of a step plan, one
plain-language description per job shape, written to state the same rules as
the reference plan without saying how to break the work into steps. Gold is
the reference plan's output, so a description that disagreed with its
reference plan would show as wrong answers in every arm alike.

Run ``python fast_path_planned_bench_v1.py`` to self-verify and print the
SHA-256.
"""

from __future__ import annotations

import fast_path_jobs_bench_v2_large as _large
from fast_path_jobs_bench_v2_large import STREAM_LENGTH, STREAM_SEED, gold, stream  # noqa: F401

DESCRIPTIONS = {
    "invoice_audit": (
        "Audit an invoice. The lines input holds one invoice line per line, of the form "
        "'SKU-dddd xQ @ E.CC': a sku, a quantity Q and a unit price in euros and cents. The subtotal is "
        "the sum over all lines of quantity times unit price. The top sku is the sku of the line with the "
        "largest quantity times unit price, the earliest such line on a tie, or 'none' if there are no "
        "lines. Also count the distinct skus. Read the customer's tone in the note as exactly one of "
        "'positive', 'negative' or 'neutral'. The discount is 10 percent of the subtotal if the tone is "
        "negative and the subtotal is more than 200.00 euros, 5 percent if the tone is negative otherwise, "
        "and nothing for any other tone, rounded down to whole cents. Return the text "
        "'total <amount> | top <sku> | <n> skus', where amount is the subtotal minus the discount in euros "
        "with exactly two decimals and n is the number of distinct skus."
    ),
    "log_triage": (
        "Summarise a log. Each line of the log input has the form 'HH:MM:SS LEVEL service: message'. "
        "Classify what the incident text is about as exactly one of 'billing', 'technical', 'account' or "
        "'shipping'. Count the non-empty lines and the lines whose level is ERROR. The rate is the ERROR "
        "count as a percentage of the line count, rounded to the nearest whole number with halves rounded "
        "up, or 0 if there are no lines. The worst service is the service with the most ERROR lines, the "
        "alphabetically first on a tie, or 'none' if there are no ERROR lines. The first error is the "
        "timestamp of the first ERROR line, or 'none'. Return the text "
        "'<topic>: <errors> errors (<rate>%), worst <service>, first at <timestamp>'."
    ),
    "order_batch": (
        "Summarise a batch of orders. The csv input is CSV text with the header 'id,country,qty,unit_cents' "
        "and one order per row. Identify the language of the note as exactly one of 'english', 'french', "
        "'spanish' or 'german'; the label for those is 'Totals', 'Totaux', 'Totales' and 'Summen' "
        "respectively. For each country, total qty times unit_cents over its rows. The top country has the "
        "largest total, the alphabetically first on a tie, or 'none' if there are no rows. The big orders "
        "are the ids, in row order, of rows whose qty times unit_cents is more than 10000. Return the text "
        "'<label>: top <country>, <n> big orders: <ids>', where n is the number of big orders and ids are "
        "joined by ',' with no spaces, or the word 'none' if there are none."
    ),
    "thread_digest": (
        "Digest a support thread. The thread input holds lines of the form '[HH:MM] Name: text'. Classify "
        "what the customer wants in the opener as exactly one of 'refund', 'cancel', 'change_address' or "
        "'order_status', and the customer's tone in the closer as exactly one of 'positive', 'negative' or "
        "'neutral'. The priority is 'urgent' if the tone is negative and the intent is refund or cancel, "
        "'normal' if the tone is negative otherwise, and 'low' for any other tone. The leader is the name "
        "with the most lines in the thread, the alphabetically first on a tie, or 'none'. The span is the "
        "number of minutes from the first line's time to the last line's time, or 0 if there are fewer "
        "than two lines. Return the text '<priority> <intent> | led by <leader> | <span> min'."
    ),
    "grade_report": (
        "Report on a class's scores. The scores input holds lines of the form 'Name: score'. Classify the "
        "tone of the comment as exactly one of 'positive', 'negative' or 'neutral'. The mean is the average "
        "score rounded to the nearest whole number with halves rounded up, or 0 if there are no scores. The "
        "median is the middle value of the sorted scores, the lower of the two middle values for an even "
        "count, or 0 if there are none. Count letter grades: A for 90 and above, B for 80 to 89, C for 70 "
        "to 79, D for 60 to 69 and F below 60. The top student has the highest score, the alphabetically "
        "first on a tie, or 'none'. Return the text "
        "'mean <mean>, median <median>, A<a> B<b> C<c> D<d> F<f>, top <name>', with the five grade counts "
        "in that order, followed by ' - review' if the tone is negative."
    ),
    "stock_reorder": (
        "Prepare a stock reorder. The stock input holds lines of the form "
        "'item | on_hand | minimum | unit_cents'. Classify the tone of the supplier_note input as exactly one of "
        "'positive', 'negative' or 'neutral'. An item is low when its on_hand is below its minimum; for each "
        "low item, order twice its minimum minus its on_hand. The cost is the total of those order "
        "quantities times each item's unit_cents. Expedite if the tone is negative or the cost is more "
        "than 50000 cents. Return the text '<n> items, <amount> EUR', where n is the number of low items "
        "and amount is the cost in euros with exactly two decimals, followed by ', EXPEDITE' if expediting."
    ),
    "meeting_actions": (
        "Summarise the actions from meeting minutes. In the minutes input, lines of the form "
        "'ACTION @name due YYYY-MM-DD: task' are actions, and every other line is ignored. Classify what "
        "the summary is about as exactly one of 'billing', 'technical', 'account' or 'shipping'. Count the "
        "distinct owner names. An action is overdue if its due date is before the today input. The next due "
        "date is the earliest due date that is today or later, or 'none'. The busiest owner has the most "
        "actions, the alphabetically first on a tie, or 'none'. Return the text "
        "'<topic>: <n> owners, <overdue> overdue, next <date>, busiest <name>', where n is the number of "
        "distinct owners."
    ),
}

SHAPES = [{**shape, "description": DESCRIPTIONS[shape["name"]]} for shape in _large.SHAPES]


def self_verify():
    names = [shape["name"] for shape in SHAPES]
    assert set(names) == set(DESCRIPTIONS), "every shape needs exactly one description"
    for shape in SHAPES:
        assert len(shape["description"]) > 200, f"{shape['name']}: description too short"
        inputs = {name for inputs, _ in stream(shape) for name in inputs}
        for name in inputs:
            assert name in shape["description"], (
                f"{shape['name']}: description never names input '{name}'"
            )
        gold(shape, stream(shape))
    print(f"self_verify OK: {len(SHAPES)} job shapes, {STREAM_LENGTH} jobs each")


def bench_sha256():
    import hashlib

    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


if __name__ == "__main__":
    self_verify()
    print("fast_path_planned_bench_v1.py sha256:", bench_sha256())
