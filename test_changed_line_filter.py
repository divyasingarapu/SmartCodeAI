
from changed_line_filter import (
    filter_findings_by_changed_lines,
    parse_changed_lines,
)


def test_parses_added_lines_from_diff():
    diff = """diff --git a/example.py b/example.py
index 1234567..abcdef0 100644
--- a/example.py
+++ b/example.py
@@ -1,3 +1,4 @@
 first_line()
+eval(user_input)
 second_line()
 third_line()
"""

    result = parse_changed_lines(diff)

    assert result == {"example.py": {2}}


def test_parses_multiple_hunks():
    diff = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,2 +1,3 @@
 first()
+added_one()
 second()
@@ -10,2 +11,3 @@
 tenth()
+added_two()
 eleventh()
"""

    result = parse_changed_lines(diff)

    assert result == {"example.py": {2, 12}}


def test_handles_new_file():
    diff = """diff --git /dev/null b/new_file.py
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+first()
+second()
"""

    result = parse_changed_lines(diff)

    assert result == {"new_file.py": {1, 2}}


def test_filters_findings_to_changed_lines():
    findings = [
        {"type": "Security", "line": 2},
        {"type": "Code Quality", "line": 5},
        {"type": "Security", "line": None},
    ]

    result = filter_findings_by_changed_lines(findings, {2, 4})

    assert result == [{"type": "Security", "line": 2}]


def test_ignores_findings_without_numeric_line_numbers():
    findings = [
        {"type": "Input", "line": None},
        {"type": "Analyzer Tool", "line": "?"},
    ]

    assert filter_findings_by_changed_lines(findings, {1, 2}) == []
