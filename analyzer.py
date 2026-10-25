import ast
import json
import os
import re
import subprocess
import sys
import tempfile

# ============================================================
# CREATE A STANDARD ISSUE
# ============================================================

def make_issue(issue_type, severity, line, message, suggestion):
    """Create a structured code-review finding."""
    return {
        "type": issue_type,
        "severity": severity,
        "line": line,
        "message": message,
        "suggestion": suggestion,
    }


# ============================================================
# SMART ACTIONABLE SUGGESTIONS
# ============================================================

def get_smart_suggestion(tool_name, code_name, message):
    """Return an actionable suggestion based on the finding."""
    code_name = str(code_name).upper()
    message_lower = str(message).lower()

    suggestions = {
        "I001": (
            "Sort and group your imports consistently. You can run "
            "'python -m ruff check --select I --fix your_file.py' "
            "to automatically organize imports."
        ),
        "F401": (
            "This import appears unused. Remove it if it is not needed, "
            "or use it in your code."
        ),
        "F821": (
            "Check the spelling of this name and make sure it is defined "
            "or imported before you use it."
        ),
        "F841": (
            "This local variable is assigned but never used. Use it in "
            "your logic or remove the unnecessary assignment."
        ),
        "E501": (
            "Consider splitting this long line into smaller, readable "
            "lines without changing the program's behavior."
        ),
        "E722": (
            "Avoid a bare 'except'. Catch the specific exception types "
            "your code is expected to handle."
        ),
        "B105": (
            "A possible hardcoded password or secret was detected. "
            "Do not store real credentials in source code. Use environment "
            "variables or a secrets manager, and verify whether this "
            "finding is a genuine secret or a false positive."
        ),
        "B106": (
            "Avoid passing a hardcoded password directly as a parameter. "
            "Load credentials securely from an environment variable or "
            "a secrets manager."
        ),
        "B107": (
            "Avoid using a hardcoded password as a function's default "
            "argument. Obtain the secret securely at runtime."
        ),
        "B301": (
            "Deserializing untrusted data with pickle can execute "
            "dangerous behavior. Use a safer data format, such as JSON, "
            "when it meets your requirements."
        ),
        "B404": (
            "Review why subprocess is needed. Avoid passing untrusted "
            "input to system commands, and validate inputs carefully."
        ),
        "B602": (
            "Avoid shell=True when possible. Prefer a list of command "
            "arguments with shell=False, and never pass untrusted input "
            "into a shell command."
        ),
        "B603": (
            "Validate command arguments and ensure they cannot be "
            "controlled maliciously by users. Use a trusted executable "
            "and avoid passing untrusted input to subprocess."
        ),
        "B607": (
            "Use a trusted, explicit executable path where practical. "
            "A partial executable path may resolve to an unexpected "
            "program depending on the environment."
        ),
        "B608": (
            "Possible SQL injection risk. Use parameterized SQL queries "
            "instead of building SQL statements by concatenating "
            "untrusted input."
        ),
    }

    if code_name in suggestions:
        return suggestions[code_name]

    # Additional security suggestions based on Bandit messages.
    if "sql" in message_lower and (
        "inject" in message_lower or "query" in message_lower
    ):
        return (
            "Review how SQL is constructed. Use parameterized queries "
            "and pass values separately rather than concatenating "
            "user-controlled input."
        )

    if "password" in message_lower or "secret" in message_lower:
        return (
            "Check whether this value contains a real credential. "
            "Avoid hardcoding secrets; use environment variables or "
            "a secrets manager."
        )

    if tool_name.lower() == "bandit":
        return (
            "Review this security finding, check whether it is exploitable "
            "in your application, and apply the recommended safe coding "
            "practice if the finding is valid."
        )

    if tool_name.lower() == "ruff":
        return (
            "Review this linting finding and update the code to improve "
            "correctness, readability, or consistency."
        )

    return (
        "Review this finding and correct the issue if it applies "
        "to your code."
    )


# ============================================================
# RUN RUFF OR BANDIT
# ============================================================

def run_static_tool(command, code, issue_type, tool_name):
    """Run a static-analysis tool on a temporary source file."""
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            temp_file.write(code)
            temp_path = temp_file.name

        command_args = [
            sys.executable,
            "-m",
            command,
        ]

        if command == "ruff":
            command_args.extend(
                ["check", "--output-format", "json"]
            )
        elif command == "bandit":
            command_args.extend(["-f", "json"])
        else:
            return [
                make_issue(
                    "Analyzer Tool",
                    "info",
                    None,
                    f"Unsupported analysis tool: {tool_name}.",
                    "Choose a supported analysis tool.",
                )
            ]

        command_args.append(temp_path)

        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        # Ruff and Bandit can return 1 when findings are present.
        # Other return codes may indicate a tool execution problem.
        if result.returncode not in (0, 1):
            return [
                make_issue(
                    "Analyzer Tool",
                    "info",
                    None,
                    f"{tool_name} could not complete the analysis.",
                    (
                        f"Check that {tool_name} is installed in the "
                        "active Python environment and try again."
                    ),
                )
            ]

        output = result.stdout.strip()

        if not output:
            return [
                make_issue(
                    "Analyzer Tool",
                    "info",
                    None,
                    f"{tool_name} returned no report.",
                    (
                        "Check the tool installation and try the "
                        "analysis again."
                    ),
                )
            ]

        report = json.loads(output)

        if command == "ruff":
            findings = report if isinstance(report, list) else []
        else:
            findings = report.get("results", [])

        issues = []

        for finding in findings:
            if command == "ruff":
                code_name = finding.get("code", "UNKNOWN")
                message = finding.get(
                    "message",
                    f"{tool_name} reported an issue.",
                )

                location = finding.get("location") or {}
                line = location.get("row")

                severity = (
                    "medium"
                    if code_name.startswith(("F", "E9"))
                    else "low"
                )

            else:
                code_name = finding.get("test_id", "UNKNOWN")
                message = finding.get(
                    "issue_text",
                    f"{tool_name} reported an issue.",
                )
                line = finding.get("line_number")

                severity = str(
                    finding.get("issue_severity", "LOW")
                ).lower()

                if severity not in {"low", "medium", "high"}:
                    severity = "low"

            suggestion = get_smart_suggestion(
                tool_name,
                code_name,
                message,
            )

            issues.append(
                make_issue(
                    issue_type,
                    severity,
                    line,
                    f"{code_name}: {message}",
                    suggestion,
                )
            )

        return issues

    except subprocess.TimeoutExpired:
        return [
            make_issue(
                "Analyzer Tool",
                "info",
                None,
                f"{tool_name} analysis timed out.",
                "Try a smaller code sample and run the analysis again.",
            )
        ]

    except (OSError, json.JSONDecodeError) as error:
        return [
            make_issue(
                "Analyzer Tool",
                "info",
                None,
                f"{tool_name} analysis could not be completed: {error}",
                (
                    f"Check the active Python environment and the "
                    f"{tool_name} installation, then try again."
                ),
            )
        ]

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ============================================================
# RUFF ANALYSIS
# ============================================================

def run_ruff_analysis(code):
    """Run Ruff static analysis."""
    return run_static_tool(
        "ruff",
        code,
        "Static Analysis (Ruff)",
        "Ruff",
    )


# ============================================================
# BANDIT SECURITY ANALYSIS
# ============================================================

def run_bandit_analysis(code):
    """Run Bandit security analysis."""
    return run_static_tool(
        "bandit",
        code,
        "Static Analysis (Bandit)",
        "Bandit",
    )


# ============================================================
# PYTHON AST ANALYSIS
# ============================================================

def analyze_python_code(code):
    """Run Python AST checks, Ruff, and Bandit."""
    issues = []

    # Check whether the submitted Python code is syntactically valid.
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return [
            make_issue(
                "Syntax Error",
                "error",
                error.lineno,
                f"Python syntax error: {error.msg}",
                (
                    "Check the reported line for missing colons, "
                    "brackets, quotation marks, or indentation errors."
                ),
            )
        ]

    # Walk through the syntax tree to identify selected patterns.
    for node in ast.walk(tree):

        # Detect eval() and exec().
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
        ):
            function_name = node.func.id

            issues.append(
                make_issue(
                    "Security",
                    "high",
                    node.lineno,
                    (
                        f"Potential security risk: {function_name}() "
                        "can execute dynamically supplied Python code."
                    ),
                    (
                        f"Avoid {function_name}() with untrusted input. "
                        "Use a safer approach for the required task."
                    ),
                )
            )

        # Detect bare except blocks.
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(
                make_issue(
                    "Code Quality",
                    "medium",
                    node.lineno,
                    (
                        "A bare except: block catches almost every "
                        "exception, including unexpected errors."
                    ),
                    (
                        "Catch the specific exceptions your code "
                        "is expected to handle."
                    ),
                )
            )

    # Run external Python static-analysis tools.
    issues.extend(run_ruff_analysis(code))
    issues.extend(run_bandit_analysis(code))

    return issues


# ============================================================
# JAVA ANALYSIS
# ============================================================

def analyze_java_code(code):
    """Run basic pattern-based checks on Java source code."""
    issues = []
    lines = code.splitlines()

    # Detect simple literal division-by-zero patterns.
    # Examples: number / 0 and number /  0
    for line_number, line in enumerate(lines, start=1):
        if re.search(r"/\s*0\b", line):
            issues.append(
                make_issue(
                    "Potential Bug",
                    "medium",
                    line_number,
                    (
                        "Possible division by zero detected by a "
                        "basic pattern check."
                    ),
                    (
                        "Check that the divisor is not zero before "
                        "performing the division."
                    ),
                )
            )

    # Detect simple assignments such as:
    # x = null;
    # String name = null;
    assignment_pattern = re.compile(
        r"\b([A-Za-z_$][\w$]*)\s*=\s*null\s*;"
    )

    null_assignments = []

    for line_number, line in enumerate(lines, start=1):
        match = assignment_pattern.search(line)

        if match:
            variable = match.group(1)
            null_assignments.append((variable, line_number))

    # Look for a later dot access of a variable assigned null.
    reported = set()

    for variable, assignment_line in null_assignments:
        for line_number in range(
            assignment_line + 1,
            len(lines) + 1,
        ):
            line = lines[line_number - 1]

            if re.search(
                rf"\b{re.escape(variable)}\s*\.",
                line,
            ):
                key = (variable, line_number)

                if key not in reported:
                    issues.append(
                        make_issue(
                            "Potential Bug",
                            "medium",
                            line_number,
                            (
                                f"Possible null dereference: '{variable}' "
                                "was assigned null earlier and is used "
                                "with dot notation."
                            ),
                            (
                                f"Check that '{variable}' is not null "
                                "before accessing its methods or fields."
                            ),
                        )
                    )
                    reported.add(key)

                break

    return issues


# ============================================================
# MAIN ANALYSIS DISPATCHER
# ============================================================

def analyze_code(code, language):
    """Analyze submitted source code and return findings."""

    if not isinstance(code, str) or not code.strip():
        return [
            make_issue(
                "Input",
                "info",
                None,
                "Please enter some code to review.",
                "Paste a Java or Python code snippet and try again.",
            )
        ]

    if not isinstance(language, str):
        return [
            make_issue(
                "Input",
                "info",
                None,
                "Unsupported language selected.",
                "Choose Python or Java.",
            )
        ]

    language = language.strip().lower()

    if language == "python":
        issues = analyze_python_code(code)

    elif language == "java":
        issues = analyze_java_code(code)

    else:
        return [
            make_issue(
                "Input",
                "info",
                None,
                "Unsupported language selected.",
                "Choose Python or Java.",
            )
        ]

    # Provide a message when no configured checks report a finding.
    if not issues:
        issues.append(
            make_issue(
                "Initial Checks",
                "info",
                None,
                "No issues detected by the available checks.",
                (
                    "This does not guarantee that the code is bug-free "
                    "or secure. Review and test it before using it."
                ),
            )
        )

    return issues