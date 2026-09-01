"""Build deterministic SVG charts for the prospective contract V2 case study."""

import argparse
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ANALYSIS_PATH = ROOT / "prospective_contract_validation_v2_analysis.json"
OUTPUT_DIR = ROOT / "docs" / "assets"

PLAN_SHA256 = (
    "5eb789d210360e5ade44755cfdc3a1e54f3f67f08d95f3f11a66da33a0a62528"
)
BENCHMARK_SHA256 = (
    "9932a510ed5592801b8a2bc3ab4cc3dbbebd3042a3b434fe6d683e48daf50e27"
)
CONTRACTS_SHA256 = (
    "cfbb36c1d9c3dc2ecc755348ffc9e4ca620d56220501b0879580a0f4d6868007"
)

OUTPUTS = {
    "false_accepts": "pcv2_false_accepts_by_model.svg",
    "contract_types": "pcv2_contract_type_catch_rate.svg",
    "correctness": "pcv2_primary_correctness_by_model.svg",
    "accepted_error": "pcv2_accepted_error_share.svg",
}

MODEL_ORDER = ("gemma3:270m", "gemma3:1b", "gemma3:4b")
MODEL_LABELS = {
    "gemma3:270m": "Gemma 3 270M",
    "gemma3:1b": "Gemma 3 1B",
    "gemma3:4b": "Gemma 3 4B",
}
CONTRACT_ORDER = (
    "bullet_format",
    "label_format",
    "json_format",
    "structured_json",
)
CONTRACT_LABELS = {
    "bullet_format": "Bullet format",
    "label_format": "Label format",
    "json_format": "JSON format",
    "structured_json": "Structured JSON",
}

BACKGROUND = "#ffffff"
TEXT = "#172033"
MUTED = "#5f6b7a"
GRID = "#d9dee7"
BLUE = "#386cb0"
CYAN = "#45a7c4"
RED = "#b33a3a"
GREEN = "#1b9e77"


def load_analysis(path=ANALYSIS_PATH):
    document = json.loads(Path(path).read_text(encoding="utf-8"))

    if document.get("schema_version") != "prospective_contract_validation_v2":
        raise ValueError("unexpected schema_version")
    if document.get("suite_id") != "prospective_contract_validation_v2":
        raise ValueError("unexpected suite_id")
    if document.get("plan_sha256") != PLAN_SHA256:
        raise ValueError("plan SHA-256 mismatch")
    if document.get("benchmark_sha256") != BENCHMARK_SHA256:
        raise ValueError("benchmark SHA-256 mismatch")
    if document.get("contracts_sha256") != CONTRACTS_SHA256:
        raise ValueError("contracts SHA-256 mismatch")

    primary = document.get("primary")
    if not isinstance(primary, dict):
        raise ValueError("primary analysis missing")
    if primary.get("overall", {}).get("observation_count") != 300:
        raise ValueError("primary observation count mismatch")
    if set(primary.get("by_model", {})) != set(MODEL_ORDER):
        raise ValueError("primary model set mismatch")
    if set(primary.get("by_contract_type", {})) != set(CONTRACT_ORDER):
        raise ValueError("primary contract-type set mismatch")

    return document


def svg_start(width, height, title, description):
    return [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="chart-title chart-description">'
        ),
        f'<title id="chart-title">{escape(title)}</title>',
        f'<desc id="chart-description">{escape(description)}</desc>',
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        (
            "<style>"
            "text{font-family:Inter,Segoe UI,Arial,sans-serif;"
            f"fill:{TEXT}}}"
            ".title{font-size:26px;font-weight:700}"
            f".subtitle{{font-size:14px;fill:{MUTED}}}"
            ".label{font-size:14px}"
            f".small{{font-size:12px;fill:{MUTED}}}"
            ".value{font-size:13px;font-weight:700}"
            ".light{fill:#ffffff}"
            "</style>"
        ),
    ]


def text(lines, x, y, value, css="label", anchor="start"):
    lines.append(
        f'<text x="{x}" y="{y}" class="{css}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def line(lines, x1, y1, x2, y2, stroke=GRID, width=1):
    lines.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{width}"/>'
    )


def rect(lines, x, y, width, height, fill, radius=3):
    lines.append(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}"/>'
    )


def chart_header(lines, title, subtitle):
    text(lines, 52, 48, title, "title")
    text(lines, 52, 74, subtitle, "subtitle")


def add_percent_grid(lines, left, top, plot_width, bottom_y, maximum=100):
    step = 20 if maximum >= 80 else 10
    for tick in range(0, maximum + 1, step):
        x = left + plot_width * tick / maximum
        line(lines, x, top, x, bottom_y)
        text(lines, x, bottom_y + 28, f"{tick}%", "small", "middle")


def render_false_accepts(document):
    width, height = 960, 460
    left, right, top = 220, 70, 135
    plot_width = width - left - right
    maximum = 80

    title = "Contracts caught false accepts at every model size"
    lines = svg_start(
        width,
        height,
        title,
        "Caught and remaining primary false accepts for three Gemma 3 model sizes.",
    )
    chart_header(
        lines,
        title,
        "Counts among outputs that survived the legacy gate but were oracle-incorrect",
    )

    rect(lines, 650, 91, 16, 16, BLUE)
    text(lines, 674, 104, "Caught", "small")
    rect(lines, 750, 91, 16, 16, RED)
    text(lines, 774, 104, "Remaining", "small")

    for tick in range(0, maximum + 1, 20):
        x = left + plot_width * tick / maximum
        line(lines, x, top - 5, x, height - 62)
        text(lines, x, height - 36, tick, "small", "middle")

    by_model = document["primary"]["by_model"]
    for index, model in enumerate(MODEL_ORDER):
        row = by_model[model]
        y = top + index * 90
        caught = row["false_accepts_caught_count"]
        remaining = row["false_accepts_remaining_count"]
        caught_width = plot_width * caught / maximum
        remaining_width = plot_width * remaining / maximum

        text(lines, 52, y + 27, MODEL_LABELS[model], "label")
        rect(lines, left, y, caught_width, 38, BLUE)
        rect(lines, left + caught_width, y, remaining_width, 38, RED)

        if caught_width >= 42:
            text(
                lines,
                left + caught_width - 9,
                y + 25,
                caught,
                "value light",
                "end",
            )
        if remaining_width >= 32:
            text(
                lines,
                left + caught_width + remaining_width / 2,
                y + 25,
                remaining,
                "value light",
                "middle",
            )
        else:
            text(
                lines,
                left + caught_width + remaining_width + 8,
                y + 25,
                remaining,
                "value",
            )

        rate = row["false_accept_catch_rate"] * 100
        text(
            lines,
            left,
            y + 58,
            f"{rate:.1f}% caught",
            "small",
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_contract_types(document):
    width, height = 960, 500
    left, right, top = 240, 70, 135
    plot_width = width - left - right

    title = "Contract effectiveness depended on what was observable"
    lines = svg_start(
        width,
        height,
        title,
        "False-accept catch rate for four primary deterministic contract types.",
    )
    chart_header(
        lines,
        title,
        "Primary false-accept catch rate by frozen contract type",
    )
    add_percent_grid(lines, left, top - 5, plot_width, height - 62)

    by_type = document["primary"]["by_contract_type"]
    colors = (BLUE, BLUE, CYAN, CYAN)
    for index, contract_type in enumerate(CONTRACT_ORDER):
        row = by_type[contract_type]
        y = top + index * 72
        rate = row["false_accept_catch_rate"] * 100
        bar_width = plot_width * rate / 100

        text(
            lines,
            left - 18,
            y + 25,
            CONTRACT_LABELS[contract_type],
            "label",
            "end",
        )
        rect(lines, left, y, bar_width, 36, colors[index])
        value = (
            f"{row['false_accepts_caught_count']}/"
            f"{row['baseline_false_accept_count']} · {rate:.2f}%"
        )
        if rate >= 80:
            text(
                lines,
                left + bar_width - 10,
                y + 24,
                value,
                "value light",
                "end",
            )
        else:
            text(
                lines,
                left + bar_width + 9,
                y + 24,
                value,
                "value",
            )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_correctness(document):
    width, height = 960, 430
    left, right, top = 220, 70, 135
    plot_width = width - left - right

    title = "Model capability reduced the underlying error burden"
    lines = svg_start(
        width,
        height,
        title,
        "Primary oracle correctness for three Gemma 3 model sizes.",
    )
    chart_header(
        lines,
        title,
        "Oracle-correct primary observations; 100 observations per model",
    )
    add_percent_grid(lines, left, top - 5, plot_width, height - 62)

    by_model = document["primary"]["by_model"]
    for index, model in enumerate(MODEL_ORDER):
        row = by_model[model]
        y = top + index * 82
        rate = row["oracle_correct_count"]
        bar_width = plot_width * rate / 100

        text(lines, 52, y + 27, MODEL_LABELS[model], "label")
        rect(lines, left, y, bar_width, 38, GREEN if model == "gemma3:4b" else CYAN)
        text(
            lines,
            left + bar_width + 9,
            y + 25,
            f"{rate}/100 · {rate:.0f}%",
            "value",
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_accepted_error(document):
    width, height = 960, 400
    left, right, top = 260, 70, 135
    plot_width = width - left - right
    maximum = 70

    overall = document["primary"]["overall"]
    before = (
        overall["baseline_false_accept_count"]
        / overall["baseline_gate_survived_count"]
        * 100
    )
    after = (
        overall["counterfactual_false_accept_count"]
        / overall["counterfactual_gate_survived_count"]
        * 100
    )

    title = "The accepted-output error share fell sharply"
    lines = svg_start(
        width,
        height,
        title,
        "Wrong-answer share among accepted primary outputs before and after contracts.",
    )
    chart_header(
        lines,
        title,
        "Wrong answers as a share of outputs returned by each acceptance gate",
    )

    for tick in range(0, maximum + 1, 10):
        x = left + plot_width * tick / maximum
        line(lines, x, top - 5, x, height - 62)
        text(lines, x, height - 36, f"{tick}%", "small", "middle")

    rows = (
        ("Legacy gate", before, RED, "175 wrong / 274 accepted"),
        ("After contracts", after, BLUE, "31 wrong / 130 accepted"),
    )
    for index, (label, rate, color, detail) in enumerate(rows):
        y = top + index * 86
        bar_width = plot_width * rate / maximum
        text(lines, 52, y + 27, label, "label")
        rect(lines, left, y, bar_width, 38, color)
        text(
            lines,
            left + bar_width - 10,
            y + 25,
            f"{rate:.1f}%",
            "value light",
            "end",
        )
        text(lines, left, y + 56, detail, "small")

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def build_charts(document):
    return {
        OUTPUTS["false_accepts"]: render_false_accepts(document),
        OUTPUTS["contract_types"]: render_contract_types(document),
        OUTPUTS["correctness"]: render_correctness(document),
        OUTPUTS["accepted_error"]: render_accepted_error(document),
    }


def write_charts(charts, output_dir=OUTPUT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for filename, content in charts.items():
        path = output_dir / filename
        if path.exists():
            raise FileExistsError(f"refusing to overwrite: {path}")
        path.write_text(content, encoding="utf-8")
        paths.append(path)

    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the four deterministic SVG charts",
    )
    args = parser.parse_args(argv)

    document = load_analysis()
    charts = build_charts(document)

    print(f"Analysis: {ANALYSIS_PATH}")
    print(f"Plan SHA-256: {PLAN_SHA256}")
    print(f"Benchmark SHA-256: {BENCHMARK_SHA256}")
    print(f"Contracts SHA-256: {CONTRACTS_SHA256}")
    print(f"Charts: {len(charts)}")
    for filename in charts:
        print(f"- {OUTPUT_DIR / filename}")

    if not args.write:
        print("Dry run only; no chart files were created.")
        return

    paths = write_charts(charts)
    print(f"Wrote {len(paths)} chart files.")


if __name__ == "__main__":
    main()
