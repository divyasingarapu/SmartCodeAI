
"""Review changed Python files in a pull request."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from analyzer import analyze_code
from changed_line_filter import (
    filter_findings_by_changed_lines,
    parse_changed_lines,
)
from security_scanner import scan_security

ROOT = Path.cwd()
OUTPUT_FILE = ROOT / "pr-review-report.md"
GIT_EXECUTABLE = shutil.which("git")

if GIT_EXECUTABLE is None:
    raise RuntimeError("Git executable was not found on PATH.")

BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


def get_changed_python_diff():
    """Return the unified diff for changed Python files."""
    base_ref = os.environ.get("GITHUB_BASE_REF", "")

    if base_ref and (
        not BRANCH_PATTERN.fullmatch(base_ref)
        or base_ref.startswith("-")
        or ".." in base_ref
        or base_ref.endswith("/")
        or "//" in base_ref
    ):
        raise ValueError("Invalid GitHub base branch name.")

    if base_ref:
        # nosec B603
        subprocess.run(
            [
                GIT_EXECUTABLE,
                "fetch",
                "origin",
                base_ref,
                "--depth=1",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        diff_range = f"origin/{base_ref}...HEAD"
    else:
        # Local fallback for a smoke test.
        diff_range = "HEAD~1...HEAD"

    # nosec B603
    result = subprocess.run(
        [
            GIT_EXECUTABLE,
            "diff",
            "--no-ext-diff",
            "--unified=0",
            "--diff-filter=ACMR",
            diff_range,
            "--",
            "*.py",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    return result.stdout


def get_changed_python_files(diff_text):
    """Return changed Python file paths found in the diff."""
    files = []

    for line in diff_text.splitlines():
        if not line.startswith("+++ b/"):
            continue

        relative_path = line[6:]

        # Ignore paths that could escape the repository root.
        path_parts = relative_path.split("/")
        if (
            not relative_path
            or "\\" in relative_path
            or any(part in ("", ".", "..") for part in path_parts)
        ):
            continue

        path = ROOT.joinpath(*path_parts)

        if path.suffix == ".py" and path.is_file():
            files.append(path)

    # Preserve order and remove duplicate paths.
    return list(dict.fromkeys(files))


def review_file(path):
    """Run quality and security checks on one Python file."""
    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    quality_issues = analyze_code(source, "python")
    security_issues = scan_security(source, "python")

    return quality_issues + security_issues


def format_finding(issue):
    """Format one finding for the Markdown report."""
    issue_type = issue.get("type", "Issue")
    severity = issue.get("severity", "unknown")
    line = issue.get("line", "?")
    message = issue.get("message", "No message provided")
    suggestion = issue.get("suggestion", "")

    finding_text = (
        f"- **{severity.upper()} — {issue_type}**, "
        f"line {line}: {message}"
    )

    lines = [finding_text]

    if suggestion:
        lines.append(f"  - Suggestion: {suggestion}")

    return lines


def main():
    try:
        diff_text = get_changed_python_diff()
    except (
        subprocess.CalledProcessError,
        ValueError,
        OSError,
    ) as error:
        print("Could not identify changed Python files.")

        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr or str(error))
        else:
            print(str(error))

        return 1

    changed_lines_by_file = parse_changed_lines(diff_text)
    changed_files = get_changed_python_files(diff_text)

    report = [
        "# SmartCode AI — Pull Request Review",
        "",
        f"Python files reviewed: {len(changed_files)}",
        "",
        "Findings are grouped by whether their reported line is changed.",
        "",
    ]

    total_findings = 0

    if not changed_files:
        report.extend(
            [
                "No changed Python files were found in this pull request.",
                "",
            ]
        )

    for path in changed_files:
        findings = review_file(path)
        relative_path = path.relative_to(ROOT).as_posix()
        changed_lines = changed_lines_by_file.get(
            relative_path,
            set(),
        )

        changed_findings = filter_findings_by_changed_lines(
            findings,
            changed_lines,
        )

        other_findings = [
            issue
            for issue in findings
            if not (
                isinstance(issue.get("line"), int)
                and issue.get("line") in changed_lines
            )
        ]

        total_findings += len(findings)

        report.extend(
            [
                f"## `{relative_path}`",
                "",
                f"Changed lines: {len(changed_lines)}",
                "",
                "### Findings on changed lines",
                "",
            ]
        )

        if changed_findings:
            for issue in changed_findings:
                report.extend(format_finding(issue))
                report.append("")
        else:
            report.extend(
                ["No findings reported on changed lines.", ""]
            )

        report.extend(
            ["### Other findings in this file", ""]
        )

        if other_findings:
            for issue in other_findings:
                report.extend(format_finding(issue))
                report.append("")
        else:
            report.extend(
                ["No other findings reported.", ""]
            )

    report.extend(
        [
            "---",
            f"**Total findings:** {total_findings}",
            "",
            "Generated by SmartCode AI.",
        ]
    )

    report_text = "\n".join(report) + "\n"

    OUTPUT_FILE.write_text(
        report_text,
        encoding="utf-8",
    )

    print(report_text)
    print(f"Report saved to: {OUTPUT_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
