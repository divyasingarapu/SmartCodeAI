
"""Static security checks for SmartCode AI.

Analyzes Python and Java source without executing the source being reviewed.
Each finding preserves the SmartCode AI schema:
type, severity, line, message, suggestion.
"""

import ast
import re

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?ix)
    \b(password|passwd|secret|api[_-]?key|access[_-]?token)
    \b\s*[:=]\s*
    (["'])
    ([^"' \t]{0,}|[^"']{1,})
    \2
    """
)

PLACEHOLDER_VALUES = {
    "",
    "your_password",
    "your_secret",
    "your_api_key",
    "your_token",
    "change_me",
    "changeme",
    "example_key",
    "replace_me",
    "replace-this",
    "placeholder",
    "password123",
    "none",
    "null",
    "your-password",
    "your-secret",
}

SQL_KEYWORDS = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|WHERE|UNION|DROP|ALTER)\b",
    re.IGNORECASE,
)


def _make_issue(rule, severity, line, message, suggestion):
    """Create a finding using the existing SmartCode AI schema."""
    return {
        "type": rule,
        "severity": severity,
        "line": line,
        "message": message,
        "suggestion": suggestion,
    }


def _call_name(node):
    """Return the dotted name of a call, such as subprocess.run."""
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr

    return ""


def _contains_dynamic_sql(node):
    """Identify common dynamic SQL expressions in an AST node."""
    if isinstance(node, (ast.BinOp, ast.JoinedStr)):
        return True

    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        if name.endswith((".format", ".format_map")):
            return True

    for child in ast.iter_child_nodes(node):
        if _contains_dynamic_sql(child):
            return True

    return False


def _python_security_checks(source_code):
    """Run AST-based security checks against Python source."""
    issues = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # Text-based checks can still run if Python syntax is incomplete.
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node.func)
        short_name = name.rsplit(".", 1)[-1]

        # Dynamic execution.
        if name in {"eval", "exec"} or (
            name.endswith(".eval") and name != "ast.eval"
        ):
            issues.append(
                _make_issue(
                    "Dangerous Dynamic Execution",
                    "high",
                    node.lineno,
                    f"Use of {short_name}() can execute dynamically "
                    "supplied code.",
                    "Avoid evaluating untrusted input. Use a restricted "
                    "parser or explicit validation where possible.",
                )
            )

        # subprocess functions using shell=True.
        subprocess_functions = {
            "run", "Popen", "call", "check_call", "check_output"
        }
        if (
            name.startswith("subprocess.")
            and short_name in subprocess_functions
            and any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
        ):
            issues.append(
                _make_issue(
                    "Shell Command Injection Risk",
                    "high",
                    node.lineno,
                    "A subprocess call enables shell=True. If command data "
                    "is influenced by untrusted input, command injection "
                    "may occur.",
                    "Prefer shell=False and pass the executable and "
                    "arguments as a list. Validate inputs.",
                )
            )

        # Unsafe pickle deserialization.
        if name in {"pickle.load", "pickle.loads"}:
            issues.append(
                _make_issue(
                    "Unsafe Deserialization",
                    "high",
                    node.lineno,
                    "Loading untrusted pickle data can execute arbitrary "
                    "code.",
                    "Never load untrusted pickle data. Prefer a non-executable "
                    "format such as JSON where suitable.",
                )
            )

        # YAML loading. SafeLoader can be positional or a keyword.
        if name == "yaml.load":
            loader = None

            if len(node.args) >= 2:
                loader = node.args[1]

            for keyword in node.keywords:
                if keyword.arg == "Loader":
                    loader = keyword.value

            safe_loader = (
                isinstance(loader, ast.Attribute)
                and loader.attr in {"SafeLoader", "CSafeLoader"}
            )

            if not safe_loader:
                issues.append(
                    _make_issue(
                        "Unsafe YAML Loading",
                        "high",
                        node.lineno,
                        "yaml.load() does not visibly specify a safe loader.",
                        "Use yaml.safe_load() for untrusted YAML, or explicitly "
                        "use yaml.SafeLoader.",
                    )
                )

        # requests calls with verify=False.
        if (
            name in {
                "requests.get", "requests.post", "requests.put",
                "requests.patch", "requests.delete", "requests.request",
            }
            and any(
                keyword.arg == "verify"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is False
                for keyword in node.keywords
            )
        ):
            issues.append(
                _make_issue(
                    "TLS Verification Disabled",
                    "high",
                    node.lineno,
                    "A requests call disables TLS certificate verification.",
                    "Keep certificate verification enabled and configure "
                    "trusted certificates correctly.",
                )
            )

        # Weak hashes: useful for legacy compatibility, not password storage.
        hash_name = None
        if name in {"hashlib.md5", "hashlib.sha1"}:
            hash_name = short_name
        elif (
            name == "hashlib.new"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.lower() in {"md5", "sha1"}
        ):
            hash_name = node.args[0].value.lower()

        if hash_name:
            issues.append(
                _make_issue(
                    "Weak Cryptographic Hash",
                    "medium",
                    node.lineno,
                    f"{hash_name.upper()} may be unsuitable for "
                    "security-sensitive hashing.",
                    "For passwords, use Argon2id, scrypt, or bcrypt. For "
                    "integrity checks, choose a modern hash appropriate "
                    "to the use case.",
                )
            )

        # SQL query passed to common execution functions.
        if short_name in {
            "execute", "executemany", "executescript",
            "prepareStatement", "createQuery",
        } and node.args:
            query_node = node.args[0]
            query_text = ast.get_source_segment(source_code, query_node) or ""

            has_sql_keyword = bool(SQL_KEYWORDS.search(query_text))
            dynamic = _contains_dynamic_sql(query_node)

            # Avoid flagging ordinary parameterized queries using placeholders.
            has_parameter_argument = (
                len(node.args) >= 2
                or any(keyword.arg in {"params", "parameters"}
                       for keyword in node.keywords)
            )

            if has_sql_keyword and dynamic and not has_parameter_argument:
                issues.append(
                    _make_issue(
                        "Possible SQL Injection",
                        "high",
                        node.lineno,
                        "SQL appears to be built dynamically. If untrusted "
                        "data is inserted into the query, SQL injection "
                        "may occur.",
                        "Use parameterized queries or prepared statements. "
                        "Do not concatenate untrusted values into SQL.",
                    )
                )

    return issues


def _line_based_checks(source_code, language):
    """Check credentials and common Java security patterns."""
    issues = []

    for line_number, line in enumerate(source_code.splitlines(), start=1):
        stripped = line.strip()

        # Ignore comments to reduce obvious false positives.
        if (
            not stripped
            or stripped.startswith(("#", "//", "*"))
        ):
            continue

        # Detect literal values assigned to credential-like names.
        match = SECRET_ASSIGNMENT_PATTERN.search(line)
        if match:
            value = match.group(3).strip()
            if value.lower() not in PLACEHOLDER_VALUES:
                issues.append(
                    _make_issue(
                        "Possible Hardcoded Secret",
                        "high",
                        line_number,
                        "A password, secret, API key, or token may contain "
                        "a literal value in source code.",
                        "Move credentials into environment variables or a "
                        "secret manager. Rotate any real exposed credentials.",
                    )
                )

        # Java command execution.
        if language == "java" and re.search(
            r"Runtime\s*\.\s*getRuntime\s*\(\s*\)\s*"
            r"\.\s*exec\s*\(",
            line,
        ):
            issues.append(
                _make_issue(
                    "Risky Java Command Execution",
                    "high",
                    line_number,
                    "Runtime.exec() executes an operating-system command. "
                    "Dynamic command data can introduce injection risks.",
                    "Avoid shell commands where possible. Validate inputs "
                    "and use fixed commands with safely separated arguments.",
                )
            )

        # Java weak hash algorithms.
        if language == "java" and re.search(
            r'MessageDigest\s*\.\s*getInstance\s*\(\s*["\']'
            r"(MD5|SHA-1?)['\"]",
            line,
            re.IGNORECASE,
        ):
            issues.append(
                _make_issue(
                    "Weak Cryptographic Hash",
                    "medium",
                    line_number,
                    "MD5 or SHA-1 may be unsuitable for security-sensitive "
                    "hashing.",
                    "Choose a modern hash or a dedicated password hashing "
                    "scheme appropriate to the purpose.",
                )
            )

    return issues


def scan_security(source_code, language="python"):
    """Return static security findings for Python or Java source."""
    if not isinstance(source_code, str):
        return []

    normalized_language = str(language).strip().lower()
    if normalized_language not in {"python", "java"}:
        return []

    issues = []

    if normalized_language == "python":
        issues.extend(_python_security_checks(source_code))

    issues.extend(_line_based_checks(source_code, normalized_language))

    # Remove exact duplicates generated by checks within this scanner.
    unique_issues = []
    seen = set()

    for issue in issues:
        key = (
            issue["type"],
            issue["line"],
            issue["message"],
        )
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues
