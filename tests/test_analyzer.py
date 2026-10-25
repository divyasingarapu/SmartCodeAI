
from analyzer import analyze_code


def test_valid_python_code():
    result = analyze_code("print('Hello')", "python")

    assert any(
        issue["type"] == "Initial Checks"
        for issue in result
    )


def test_python_syntax_error():
    result = analyze_code('print("Hello"', "python")

    assert any(
        issue["type"] == "Syntax Error"
        and issue["line"] == 1
        for issue in result
    )


def test_eval_security_warning():
    result = analyze_code('x = eval("2 + 3")', "python")

    assert any(
        issue["type"] == "Security"
        and issue["severity"] == "high"
        and issue["line"] == 1
        for issue in result
    )


def test_exec_security_warning():
    result = analyze_code('exec("print(1)")', "python")

    assert any(
        issue["type"] == "Security"
        and "exec()" in issue["message"]
        for issue in result
    )


def test_bare_except_warning():
    code = "try:\n    x = 1\nexcept:\n    pass"
    result = analyze_code(code, "python")

    assert any(
        issue["type"] == "Code Quality"
        and issue["severity"] == "medium"
        and issue["line"] == 3
        for issue in result
    )


def test_empty_code():
    result = analyze_code("", "python")

    assert any(
        issue["type"] == "Input"
        and "Please enter some code" in issue["message"]
        for issue in result
    )


def test_simple_java_division_by_zero():
    result = analyze_code("int result = a / 0;", "java")

    assert any(
        issue["type"] == "Potential Bug"
        and issue["severity"] == "medium"
        for issue in result
    )


def test_unsupported_language():
    result = analyze_code("some code", "javascript")

    assert any(
        issue["type"] == "Input"
        and "Unsupported language" in issue["message"]
        for issue in result
    )
def test_java_division_by_zero_with_spaces():
    result = analyze_code(
        "int answer = total / 0;",
        "java",
    )

    assert any(
        issue["type"] == "Potential Bug"
        and issue["line"] == 1
        and "division by zero" in issue["message"]
        for issue in result
    )
def test_java_possible_null_dereference():
    code = (
        "String name = null;\n"
        "System.out.println(name.length());"
    )

    result = analyze_code(code, "java")

    assert any(
        issue["type"] == "Potential Bug"
        and issue["line"] == 2
        and "null dereference" in issue["message"]
        for issue in result
    )



def test_ruff_detects_undefined_name():
    result = analyze_code(
        "print(missing_variable)",
        "python",
    )

    assert any(
        issue["type"] == "Static Analysis (Ruff)"
        and issue["line"] == 1
        and "F821" in issue["message"]
        for issue in result
    )

def test_bandit_detects_hardcoded_password():
    result = analyze_code(
        'password = "hardcoded-secret-value"',
        "python",
    )

    assert any(
        issue["type"] == "Static Analysis (Bandit)"
        and issue["line"] == 1
        and "B105" in issue["message"]
        for issue in result
    )