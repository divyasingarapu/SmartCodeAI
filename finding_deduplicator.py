
"""Deduplicate overlapping findings from Ruff, Bandit, and custom checks."""

import ast
import re
from collections import OrderedDict


SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
    "informational": 1,
    "other": 0,
}


def _text(issue):
    """Combine finding fields for matching."""
    return " ".join(
        str(issue.get(key, ""))
        for key in ("type", "message", "suggestion")
    ).lower()


def _source(issue):
    """Identify the likely scanner that produced a finding."""
    finding_type = str(issue.get("type", "")).lower()
    message = str(issue.get("message", "")).lower()

    if "bandit" in finding_type or re.search(r"\bB\d{3}\b", message):
        return "Bandit"

    if "ruff" in finding_type or re.search(r"\b[EFW]\d{3,4}\b", message):
        return "Ruff"

    if any(
        token in finding_type
        for token in (
            "dangerous dynamic",
            "shell command injection",
            "possible hardcoded secret",
        )
    ):
        return "Custom security scanner"

    if "security" in finding_type:
        return "Security scanner"

    return finding_type.strip() or "Code analyzer"



def _category(issue):
    """Identify security issue categories from finding messages."""
    message = str(issue.get("message", "")).lower()
    issue_type = str(issue.get("type", "")).lower()
    combined = message + " " + issue_type

    if "eval" in combined or "exec" in combined or "dynamic code execution" in combined:
        return "dynamic_code_execution"

    if "shell=true" in combined or "command injection" in combined:
        return "shell_execution"

    if any(word in combined for word in ("hardcoded password", "hardcoded secret", "api key", "secret key")):
        return "hardcoded_secret"

    if "pickle" in combined and any(word in combined for word in ("unsafe", "deserializ")):
        return "unsafe_pickle"

    if "yaml.load" in combined or "unsafe yaml" in combined:
        return "unsafe_yaml"
    if (
         "verify=false" in combined
          or "tls verification disabled" in combined
          or "certificate verification disabled" in combined
    ):
        return "disabled_tls_verification"


    return None



def _exact_key(issue):
    """Build a key for identical findings."""
    line = issue.get("line")

    message = re.sub(
        r"\s+",
        " ",
        str(issue.get("message", "")).strip(),
    ).lower()

    finding_type = re.sub(
        r"\s+",
        " ",
        str(issue.get("type", "")).strip(),
    ).lower()

    return line, finding_type, message


def _python_shell_call_sites(source_code):
    """Find Python subprocess calls that explicitly use shell=True."""
    if not source_code:
        return []

    try:
        tree = ast.parse(source_code)
    except (SyntaxError, ValueError, TypeError):
        return []

    call_sites = []

    subprocess_functions = {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        shell_true = any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )

        if not shell_true:
            continue

        func = node.func

        # subprocess.run(..., shell=True)
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
            and func.attr in subprocess_functions
        ):
            call_sites.append(
                (node.lineno, getattr(node, "end_lineno", node.lineno))
            )

        # Directly imported function, e.g. run(..., shell=True).
        elif (
            isinstance(func, ast.Name)
            and func.id in subprocess_functions
        ):
            call_sites.append(
                (node.lineno, getattr(node, "end_lineno", node.lineno))
            )

    return sorted(set(call_sites))


def _find_shell_site(issue, call_sites):
    """Associate a finding with a unique shell call when possible."""
    try:
        issue_line = int(issue.get("line"))
    except (TypeError, ValueError):
        return None

    # First, look for a reported line inside a call's source span.
    matching_sites = [
        site
        for site in call_sites
        if site[0] <= issue_line <= site[1]
    ]

    if len(matching_sites) == 1:
        return matching_sites[0]

    if len(matching_sites) > 1:
        return None

    # A scanner may report the call's starting line, its end line, or
    # a nearby line. Only associate with one unambiguous nearest site.
    distances = [
        (min(abs(issue_line - start), abs(issue_line - end)), (start, end))
        for start, end in call_sites
    ]

    if not distances:
        return None

    nearest_distance = min(distance for distance, _ in distances)
    nearest_sites = [
        site for distance, site in distances
        if distance == nearest_distance
    ]

    if nearest_distance <= 3 and len(nearest_sites) == 1:
        return nearest_sites[0]

    return None


def _severity(issue):
    """Normalize a finding's severity."""
    return str(issue.get("severity", "other")).strip().lower()


def deduplicate_findings(findings, source_code=None, language="python"):
    """Merge likely duplicate findings and preserve useful information.

    Known security categories are merged when their reported line matches.
    Python shell=True findings may also be merged when they can be mapped
    to the same AST call site. Other findings require an exact fallback key.
    """
    if not findings:
        return []

    prepared = [
        dict(item)
        for item in findings
        if isinstance(item, dict)
    ]

    call_sites = []
    if str(language).lower() == "python":
        call_sites = _python_shell_call_sites(source_code)

    merged = OrderedDict()

    for issue in prepared:
        line = issue.get("line")
        category = _category(issue)
        source = _source(issue)

        key = None

        if category == "shell-execution" and call_sites:
            site = _find_shell_site(issue, call_sites)
            if site is not None:
                key = ("shell-source-site", site)

        if key is None:
            if category and line is not None:
                key = ("category", line, category)
            else:
                key = ("exact",) + _exact_key(issue)

        issue_sources = issue.get("sources", [source])

        if isinstance(issue_sources, str):
            issue_sources = [issue_sources]

        issue_sources = list(
            dict.fromkeys(
                str(name)
                for name in issue_sources
                if name
            )
        )

        try:
            issue_count = max(1, int(issue.get("duplicate_count", 1)))
        except (TypeError, ValueError):
            issue_count = 1

        if key not in merged:
            issue["sources"] = issue_sources
            issue["duplicate_count"] = issue_count
            merged[key] = issue
            continue

        current = merged[key]

        combined_sources = list(
            dict.fromkeys(
                current.get("sources", []) + issue_sources
            )
        )

        try:
            current_count = max(
                1,
                int(current.get("duplicate_count", 1)),
            )
        except (TypeError, ValueError):
            current_count = 1

        combined_count = current_count + issue_count

        old_severity = _severity(current)
        new_severity = _severity(issue)

        # Preserve the finding with the highest severity.
        if SEVERITY_RANK.get(new_severity, 0) > SEVERITY_RANK.get(
            old_severity, 0
        ):
            current.update(issue)

        current["sources"] = combined_sources
        current["duplicate_count"] = combined_count

        # Keep a suggestion if the selected finding lacks one.
        if not current.get("suggestion") and issue.get("suggestion"):
            current["suggestion"] = issue["suggestion"]

    return list(merged.values())
