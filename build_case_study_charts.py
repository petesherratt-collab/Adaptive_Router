"""Build deterministic SVG charts for the Adaptive Router case study."""

import argparse
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ANALYSIS_PATH = ROOT / "routing_analysis_oos_v1.json"
OUTPUT_DIR = ROOT / "docs" / "assets"

BENCHMARK_SHA256 = (
    "6e255b2d44599f49a1cda82f989b110a015c16c55da54ea6501f4b8cb18fa295"
)

OUTPUTS = {
    "policy": "oos_policy_accuracy.svg",
    "family": "oos_family_generalization.svg",
    "frontier": "oos_accuracy_remote_frontier.svg",
}

POLICY_ORDER = (
    "always_local",
    "coarse_class",
    "fine_capability",
    "always_remote",
)

POLICY_LABELS = {
    "always_local": "Always local",
    "coarse_class": "Coarse class",
    "fine_capability": "Fine capability",
    "always_remote": "Always remote",
}

FAMILY_LABELS = {
    "structured_extraction": "Structured extraction",
    "sentiment": "Sentiment",
    "json_format": "JSON formatting",
    "priority": "Priority",
    "markdown_bullets": "Markdown bullets",
    "key_value_labels": "Key/value labels",
    "transformation": "Transformation",
}

FAMILY_ORDER = tuple(FAMILY_LABELS)

BACKGROUND = "#ffffff"
TEXT = "#172033"
MUTED = "#5f6b7a"
GRID = "#d9dee7"
LOCAL = "#386cb0"
REMOTE = "#1b9e77"
FINE = "#d95f02"
COARSE = "#7570b3"
FAIL = "#b33a3a"


def load_analysis(path=ANALYSIS_PATH):
    document = json.loads(
        Path(path).read_text(encoding="utf-8")
    )

    if document.get("analysis_id") != "oos_validation_v1_strict":
        raise ValueError("unexpected analysis_id")
    if document.get("interpretation") != "strict":
        raise ValueError("case-study charts require strict analysis")
    if document.get("benchmark_sha256") != BENCHMARK_SHA256:
        raise ValueError("benchmark SHA-256 mismatch")

    policies = document.get("policies")
    if not isinstance(policies, list):
        raise ValueError("analysis policies must be a list")

    policy_names = {row.get("policy") for row in policies}
    if policy_names != set(POLICY_ORDER):
        raise ValueError("analysis policy set mismatch")

    families = document.get("per_family")
    if not isinstance(families, dict):
        raise ValueError("per_family must be an object")
    if set(families) != set(FAMILY_ORDER):
        raise ValueError("analysis family set mismatch")

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
        (
            f'<desc id="chart-description">'
            f'{escape(description)}</desc>'
        ),
        (
            f'<rect width="{width}" height="{height}" '
            f'fill="{BACKGROUND}"/>'
        ),
        (
            "<style>"
            "text{font-family:Inter,Segoe UI,Arial,sans-serif;"
            f"fill:{TEXT}}}"
            ".title{font-size:26px;font-weight:700}"
            ".subtitle{font-size:14px;fill:#5f6b7a}"
            ".label{font-size:14px}"
            ".small{font-size:12px;fill:#5f6b7a}"
            ".value{font-size:13px;font-weight:700}"
            "</style>"
        ),
    ]


def text(lines, x, y, value, css="label", anchor="start"):
    lines.append(
        f'<text x="{x}" y="{y}" class="{css}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def line(lines, x1, y1, x2, y2, stroke=GRID, width=1, dash=None):
    dash_attribute = (
        f' stroke-dasharray="{dash}"' if dash else ""
    )
    lines.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{width}"'
        f'{dash_attribute}/>'
    )


def rect(lines, x, y, width, height, fill, radius=3):
    lines.append(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}"/>'
    )


def chart_header(lines, title, subtitle):
    text(lines, 52, 48, title, "title")
    text(lines, 52, 74, subtitle, "subtitle")


def percent(value):
    return f"{value * 100:.1f}%"


def render_policy_chart(document):
    width = 960
    height = 570
    left = 190
    right = 65
    top = 145
    plot_width = width - left - right

    title = "Out-of-sample routing accuracy"
    description = (
        "Strict accuracy and remote-call rate for four routing policies "
        "over 200 paired observations."
    )
    lines = svg_start(width, height, title, description)
    chart_header(
        lines,
        title,
        "Strict accuracy and remote-call rate across 200 paired observations",
    )

    rect(lines, 610, 92, 16, 16, LOCAL)
    text(lines, 634, 105, "Strict accuracy", "small")
    rect(lines, 760, 92, 16, 16, REMOTE)
    text(lines, 784, 105, "Remote-call rate", "small")

    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        line(lines, x, top - 12, x, height - 66)
        text(lines, x, height - 42, f"{tick}%", "small", "middle")

    by_policy = {
        row["policy"]: row
        for row in document["policies"]
    }

    for index, policy in enumerate(POLICY_ORDER):
        row = by_policy[policy]
        group_y = top + index * 94
        accuracy = row["selected_pass_rate"]
        remote_rate = row["remote_call_rate"]

        text(
            lines,
            left - 18,
            group_y + 28,
            POLICY_LABELS[policy],
            "label",
            "end",
        )

        accuracy_width = plot_width * accuracy
        remote_width = plot_width * remote_rate

        rect(
            lines,
            left,
            group_y,
            accuracy_width,
            27,
            LOCAL,
        )
        rect(
            lines,
            left,
            group_y + 36,
            remote_width,
            18,
            REMOTE,
        )

        text(
            lines,
            min(left + accuracy_width + 8, width - 48),
            group_y + 19,
            percent(accuracy),
            "value",
        )
        text(
            lines,
            min(left + remote_width + 8, width - 48),
            group_y + 50,
            percent(remote_rate),
            "small",
        )

    text(
        lines,
        width / 2,
        height - 15,
        "Fine routing halved remote calls but missed the five-point accuracy tolerance.",
        "subtitle",
        "middle",
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_family_chart(document):
    width = 1060
    height = 690
    left = 230
    right = 70
    top = 142
    plot_width = width - left - right

    title = "Capability did not generalize uniformly"
    description = (
        "Local and remote strict pass rates for seven capability "
        "families in the out-of-sample validation."
    )
    lines = svg_start(width, height, title, description)
    chart_header(
        lines,
        title,
        "Local Gemma 3 270M versus remote GPT-5.6 Luna",
    )

    rect(lines, 700, 91, 16, 16, LOCAL)
    text(lines, 724, 104, "Local", "small")
    rect(lines, 790, 91, 16, 16, REMOTE)
    text(lines, 814, 104, "Remote", "small")

    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        line(lines, x, top - 10, x, height - 60)
        text(lines, x, height - 35, f"{tick}%", "small", "middle")

    families = document["per_family"]

    for index, family in enumerate(FAMILY_ORDER):
        metrics = families[family]
        y = top + index * 70
        local_rate = metrics["local_pass_rate"]
        remote_rate = metrics["remote_pass_rate"]

        text(
            lines,
            left - 18,
            y + 27,
            FAMILY_LABELS[family],
            "label",
            "end",
        )

        local_width = plot_width * local_rate
        remote_width = plot_width * remote_rate

        rect(lines, left, y, local_width, 22, LOCAL)
        rect(lines, left, y + 29, remote_width, 22, REMOTE)

        text(
            lines,
            min(left + local_width + 8, width - 48),
            y + 16,
            percent(local_rate),
            "value",
        )
        text(
            lines,
            min(left + remote_width + 8, width - 48),
            y + 45,
            percent(remote_rate),
            "value",
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_frontier_chart(document):
    width = 960
    height = 620
    left = 105
    right = 75
    top = 125
    bottom = 95
    plot_width = width - left - right
    plot_height = height - top - bottom

    title = "Measured accuracy–remote-capacity frontier"
    description = (
        "Strict routing accuracy plotted against remote-call rate for "
        "the four tested policies."
    )
    lines = svg_start(width, height, title, description)
    chart_header(
        lines,
        title,
        "Measured policies only; connecting lines do not imply untested performance",
    )

    y_min = 30
    y_max = 100

    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        line(lines, x, top, x, top + plot_height)
        text(
            lines,
            x,
            top + plot_height + 34,
            f"{tick}%",
            "small",
            "middle",
        )

    for tick in range(40, 101, 10):
        y = top + plot_height * (y_max - tick) / (y_max - y_min)
        line(lines, left, y, left + plot_width, y)
        text(lines, left - 16, y + 4, f"{tick}%", "small", "end")

    line(lines, left, top + plot_height, left + plot_width, top + plot_height, TEXT, 2)
    line(lines, left, top, left, top + plot_height, TEXT, 2)

    text(
        lines,
        left + plot_width / 2,
        height - 28,
        "Remote-call rate",
        "label",
        "middle",
    )
    lines.append(
        f'<text x="28" y="{top + plot_height / 2}" '
        f'class="label" text-anchor="middle" '
        f'transform="rotate(-90 28 {top + plot_height / 2})">'
        f'Strict accuracy</text>'
    )

    colors = {
        "always_local": LOCAL,
        "coarse_class": COARSE,
        "fine_capability": FINE,
        "always_remote": REMOTE,
    }
    offsets = {
        "always_local": (12, -13),
        "coarse_class": (-12, 27),
        "fine_capability": (12, -15),
        "always_remote": (-12, 27),
    }

    by_policy = {
        row["policy"]: row
        for row in document["policies"]
    }

    ordered_points = [
        by_policy[policy]
        for policy in POLICY_ORDER
    ]

    path_points = []
    for row in ordered_points:
        x = left + plot_width * row["remote_call_rate"]
        y = (
            top
            + plot_height
            * (y_max - row["selected_pass_rate"] * 100)
            / (y_max - y_min)
        )
        path_points.append(f"{x},{y}")

    lines.append(
        f'<polyline points="{" ".join(path_points)}" '
        f'fill="none" stroke="{MUTED}" stroke-width="2" '
        f'stroke-dasharray="6 6"/>'
    )

    for policy in POLICY_ORDER:
        row = by_policy[policy]
        x = left + plot_width * row["remote_call_rate"]
        y = (
            top
            + plot_height
            * (y_max - row["selected_pass_rate"] * 100)
            / (y_max - y_min)
        )
        lines.append(
            f'<circle cx="{x}" cy="{y}" r="9" '
            f'fill="{colors[policy]}" stroke="#ffffff" '
            f'stroke-width="3"/>'
        )

        dx, dy = offsets[policy]
        anchor = "start" if dx > 0 else "end"
        text(
            lines,
            x + dx,
            y + dy,
            (
                f"{POLICY_LABELS[policy]} "
                f"({percent(row['selected_pass_rate'])})"
            ),
            "value",
            anchor,
        )

    text(
        lines,
        width / 2,
        height - 7,
        "The next phase should estimate a fuller frontier under explicit remote budgets.",
        "subtitle",
        "middle",
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def build_charts(document):
    return {
        OUTPUTS["policy"]: render_policy_chart(document),
        OUTPUTS["family"]: render_family_chart(document),
        OUTPUTS["frontier"]: render_frontier_chart(document),
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
        help="write the three deterministic SVG charts",
    )
    args = parser.parse_args(argv)

    document = load_analysis()
    charts = build_charts(document)

    print(f"Analysis: {ANALYSIS_PATH}")
    print(f"Benchmark SHA-256: {BENCHMARK_SHA256}")
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
