
"""Helpers for identifying changed lines in Git diffs."""


def parse_changed_lines(diff_text):
    """Return added line numbers for each file in a unified Git diff."""
    changed_lines = {}
    current_file = None
    new_line_number = None

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()

            if path == "/dev/null":
                current_file = None
            elif path.startswith("b/"):
                current_file = path[2:]
            else:
                current_file = path

            if current_file is not None:
                changed_lines.setdefault(current_file, set())

        elif line.startswith("@@ "):
            # Example: @@ -10,3 +10,5 @@
            try:
                new_range = line.split("@@", 2)[1].strip().split()[1]
                new_range = new_range.lstrip("+")
                start, _, count = new_range.partition(",")

                new_line_number = int(start)
                if count == "":
                    count = 1
                else:
                    count = int(count)

                if current_file is not None and count == 0:
                    new_line_number = None

            except (IndexError, ValueError):
                new_line_number = None

        elif current_file is not None and new_line_number is not None:
            if line.startswith("+") and not line.startswith("+++"):
                changed_lines[current_file].add(new_line_number)
                new_line_number += 1

            elif line.startswith("-") and not line.startswith("---"):
                # Removed lines do not exist in the new file.
                continue

            elif line.startswith("\\"):
                # Diff metadata such as "No newline at end of file".
                continue

            else:
                # Context line exists in both versions.
                new_line_number += 1

    return changed_lines


def filter_findings_by_changed_lines(findings, changed_lines):
    """Keep findings whose line numbers occur in the changed-line set."""
    filtered = []

    for finding in findings:
        line = finding.get("line")

        if isinstance(line, int) and line in changed_lines:
            filtered.append(finding)

    return filtered
