# Real tasks

Put each kind of job you want tested in its own JSON file in this folder. The
planned-jobs runner reads every file here except those whose name starts with
`example_`.

```json
{
  "name": "invoice_check",
  "description": "What the job is, written the way you would ask for it. Say exactly what form the answer must take, for example: Return the text '<n> lines, total <amount> EUR'.",
  "jobs": [
    {"inputs": {"invoice": "...", "note": "..."}, "answer": "3 lines, total 41.50 EUR"},
    {"inputs": {"invoice": "...", "note": "..."}, "answer": "5 lines, total 12.00 EUR"}
  ]
}
```

- `name`: letters, digits and underscores.
- `description`: the request in plain words. Name every input key in it, and
  spell out the exact form of the answer. Answers are compared exactly, so
  "12.0" and "12.00" count as different.
- `jobs`: at least 5, ideally 10 to 15. Every job has the same input keys.
  Each input is a JSON value: text, a number, a list or an object.
- `answer`: the correct result as JSON. A job without a known answer can
  still be listed with `"answer": null`; it is run but not scored.

Remove anything private first. The files are sent to the model providers when
the test runs, and they are committed to the repository.

`example_invoice_check.json` shows the format with made-up data. It is
ignored by real runs.

To check the files without calling any model:

```bash
python fast_path_real_bench.py
```

To run the test (costs provider credit):

```bash
python run_fast_path_planned_v1.py --bench fast_path_real_bench.py --output fast_path_real_v1.jsonl --label real_v1
```
