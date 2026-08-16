import json
import sys
from pathlib import Path

import pytest
from scripts.coverage_comment import (
    build_comment,
    collapse_ranges,
    main,
    read_threshold,
    verdict,
)

REPORT = "Name  Stmts  Miss  Cover\nTOTAL    10     5    50%\n"


def write_diff(path: Path, *, percent: float, violations: list[int]) -> Path:
    path.write_text(
        json.dumps(
            {
                "total_percent_covered": percent,
                "total_num_violations": len(violations),
                "src_stats": {
                    "app/example.py": {
                        "percent_covered": percent,
                        "violation_lines": violations,
                    }
                },
            }
        )
    )
    return path


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ([], ""),
        ([7], "7"),
        ([1, 2, 3], "1-3"),
        ([1, 3], "1, 3"),
        ([12, 13, 14, 22, 39, 40], "12-14, 22, 39-40"),
        ([40, 12, 39, 13, 14, 22], "12-14, 22, 39-40"),
    ],
)
def test_collapse_ranges(lines: list[int], expected: str) -> None:
    assert collapse_ranges(lines) == expected


def test_verdict_passes_exactly_at_the_threshold() -> None:
    assert verdict(50, 50) == "Pass"


def test_verdict_fails_just_below_the_threshold() -> None:
    assert "FAIL" in verdict(49.9, 50)


def test_read_threshold_comes_from_pyproject() -> None:
    threshold = read_threshold()

    assert isinstance(threshold, int)
    assert 0 < threshold <= 100


def test_comment_flags_both_numbers_when_they_fail(tmp_path: Path) -> None:
    patch = json.loads(
        write_diff(tmp_path / "d.json", percent=41, violations=[12, 13]).read_text()
    )

    comment = build_comment(REPORT, 36, patch, 50)

    assert "| Project coverage | 50% | 36% | **FAIL** |" in comment
    assert "| Patch coverage | 50% | 41% | **FAIL** |" in comment
    assert "12-13" in comment
    assert "app/example.py" in comment


def test_comment_congratulates_full_patch_coverage(tmp_path: Path) -> None:
    patch = json.loads(
        write_diff(tmp_path / "d.json", percent=100, violations=[]).read_text()
    )

    comment = build_comment(REPORT, 100, patch, 50)

    assert "Every line this pull request changed is covered" in comment
    assert "**FAIL**" not in comment


def test_comment_omits_the_patch_row_outside_pull_requests() -> None:
    comment = build_comment(REPORT, 100, None, 50)

    assert "Project coverage" in comment
    assert "Patch coverage" not in comment


def test_comment_always_embeds_the_raw_report() -> None:
    assert REPORT.strip() in build_comment(REPORT, 100, None, 50)


def run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    total: str,
    diff: Path,
    *,
    check: bool = True,
) -> int:
    report = tmp_path / "report.txt"
    report.write_text(REPORT)
    argv = [
        "coverage_comment.py",
        "--report",
        str(report),
        "--total",
        total,
        "--diff",
        str(diff),
        "--output",
        str(tmp_path / "out.md"),
    ]
    if check:
        argv.append("--check")
    monkeypatch.setattr(sys, "argv", argv)
    return main()


def test_main_succeeds_when_both_numbers_clear_the_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diff = write_diff(tmp_path / "d.json", percent=100, violations=[])

    assert run_main(monkeypatch, tmp_path, "100", diff) == 0
    assert (tmp_path / "out.md").exists()


def test_main_fails_on_low_project_coverage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diff = write_diff(tmp_path / "d.json", percent=100, violations=[])

    assert run_main(monkeypatch, tmp_path, "20", diff) == 1


def test_main_fails_on_low_patch_coverage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diff = write_diff(tmp_path / "d.json", percent=10, violations=[3, 4, 5])

    assert run_main(monkeypatch, tmp_path, "100", diff) == 1


def test_main_tolerates_a_missing_diff_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert run_main(monkeypatch, tmp_path, "100", tmp_path / "absent.json") == 0


def test_main_without_check_never_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diff = write_diff(tmp_path / "d.json", percent=0, violations=[1, 2, 3])

    assert run_main(monkeypatch, tmp_path, "0", diff, check=False) == 0
