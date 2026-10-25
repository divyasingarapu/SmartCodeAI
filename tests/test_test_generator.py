
from test_generator import generate_tests


def test_generates_tests_for_add_function():
    source = """
def add(a, b):
    return a + b
"""

    result = generate_tests(source, module_name="calculator")

    assert result["generated_count"] > 0
    assert "from calculator import add" in result["test_code"]
    assert "assert add(" in result["test_code"]
    assert result["warnings"] == []


def test_generates_tests_for_string_function():
    source = """
def greet(name):
    return "Hello " + name
"""

    result = generate_tests(source, module_name="greetings")

    assert result["generated_count"] > 0
    assert "from greetings import greet" in result["test_code"]
    assert "Hello " in result["test_code"]


def test_reports_invalid_python_syntax():
    source = """
def add(a, b)
    return a + b
"""

    result = generate_tests(source)

    assert result["generated_count"] == 0
    assert result["test_code"] == ""
    assert any("syntax error" in warning for warning in result["warnings"])


def test_skips_unsupported_function_body():
    source = """
def calculate_total(numbers):
    total = 0
    for number in numbers:
        total += number
    return total
"""

    result = generate_tests(source)

    assert result["generated_count"] == 0
    assert any("Skipped 'calculate_total'" in warning
               for warning in result["warnings"])


def test_rejects_invalid_module_name():
    source = """
def add(a, b):
    return a + b
"""

    try:
        generate_tests(source, module_name="calculator; import os")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected an invalid module name to be rejected")
