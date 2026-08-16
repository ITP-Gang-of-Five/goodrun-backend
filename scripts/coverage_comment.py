"""Render and enforce the coverage summary that CI posts on pull requests.

Reads the output of `coverage report` and, on pull requests, the JSON report from
`diff-cover`. Writes a Markdown summary, and with --check exits non-zero when
either coverage number is below the threshold in pyproject.toml.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def read_threshold() -> int:
    """The single source of truth for both coverage gates."""
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    return int(config["tool"]["coverage"]["report"]["fail_under"])


def collapse_ranges(lines: list[int]) -> str:
    """Turn [12, 13, 14, 22, 39] into "12-14, 22, 39"."""
    if not lines:
        return ""
    ordered = sorted(lines)
    groups: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for line in ordered[1:]:
        if line == previous + 1:
            previous = line
            continue
        groups.append((start, previous))
        start = previous = line
    groups.append((start, previous))
    return ", ".join(str(lo) if lo == hi else f"{lo}-{hi}" for lo, hi in groups)


def verdict(actual: float, required: int) -> str:
    return "Pass" if actual >= required else "**FAIL**"


def build_comment(
    report_text: str,
    project_total: float,
    patch: dict[str, Any] | None,
    required: int,
) -> str:
    rows = [
        "| Check | Required | This PR | Result |",
        "| --- | --- | --- | --- |",
        f"| Project coverage | {required}% | {project_total:.0f}% "
        f"| {verdict(project_total, required)} |",
    ]
    if patch is not None:
        patch_total = patch["total_percent_covered"]
        rows.append(
            f"| Patch coverage | {required}% | {patch_total:.0f}% "
            f"| {verdict(patch_total, required)} |"
        )

    lines = ["## Coverage", "", *rows, ""]
    lines += [
        "- **Project coverage** is how much of `app/` the whole test suite runs.",
    ]
    if patch is not None:
        lines += [
            "- **Patch coverage** is how much of the code *this pull request* adds "
            "or changes that the test suite runs. This is the one that usually "
            "fails: it stops new, untested code from being merged.",
        ]
    lines.append("")

    untested = _untested_table(patch)
    if untested:
        lines += untested
    elif patch is not None and project_total >= required:
        lines += ["Every line this pull request changed is covered by a test.", ""]

    lines += [
        "<details>",
        "<summary>Full per-file breakdown</summary>",
        "",
        "```text",
        report_text.strip(),
        "```",
        "",
        "</details>",
    ]
    return "\n".join(lines) + "\n"


def _untested_table(patch: dict[str, Any] | None) -> list[str]:
    if patch is None:
        return []
    offenders = {
        name: stats
        for name, stats in patch.get("src_stats", {}).items()
        if stats.get("violation_lines")
    }
    if not offenders:
        return []

    lines = [
        "### Lines this pull request changed that no test runs",
        "",
        "| File | Covered | Untested lines |",
        "| --- | --- | --- |",
    ]
    for name, stats in sorted(offenders.items()):
        ranges = collapse_ranges(stats["violation_lines"])
        lines.append(f"| `{name}` | {stats['percent_covered']:.0f}% | {ranges} |")
    lines += [
        "",
        "Add tests under `tests/` that exercise those lines, then run `make test` "
        "locally to confirm before pushing.",
        "",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", required=True, type=Path, help="output of `coverage report`"
    )
    parser.add_argument(
        "--total", required=True, type=float, help="overall coverage percentage"
    )
    parser.add_argument(
        "--diff", type=Path, help="diff-cover JSON report; ignored if absent"
    )
    parser.add_argument("--output", type=Path, help="where to write the Markdown")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if either number is below the threshold",
    )
    args = parser.parse_args()

    required = read_threshold()
    report_text = args.report.read_text()
    patch = None
    if args.diff is not None and args.diff.exists():
        patch = json.loads(args.diff.read_text())

    if args.output is not None:
        args.output.write_text(build_comment(report_text, args.total, patch, required))

    if not args.check:
        return 0

    failures = []
    if args.total < required:
        failures.append(
            f"Project coverage is {args.total:.0f}%, below the required {required}%. "
            f"The test suite does not run enough of app/."
        )
    if patch is not None and patch["total_percent_covered"] < required:
        untested = patch["total_num_violations"]
        failures.append(
            f"Patch coverage is {patch['total_percent_covered']:.0f}%, below the "
            f"required {required}%. {untested} line(s) added or changed by this "
            f"pull request are not run by any test."
        )

    for failure in failures:
        print(f"Coverage check failed: {failure}", file=sys.stderr)
    if failures:
        print(
            "\nSee the coverage comment on the pull request for the exact lines.",
            file=sys.stderr,
        )
        return 1

    print(f"Coverage checks passed (threshold {required}%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
