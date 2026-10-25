
from test_runner import run_generated_tests


def test_empty_code_is_rejected():
    result = run_generated_tests(
        test_code="",
        source_code="def add(a, b):\n    return a + b\n",
        module_name="calculator",
    )

    assert result["success"] is False
    assert result["total"] == 0
    assert result["errors"]


def test_oversized_code_is_rejected():
    result = run_generated_tests(
        test_code="x" * 100_001,
        source_code="def add(a, b):\n    return a + b\n",
        module_name="calculator",
    )

    assert result["success"] is False
    assert result["errors"]
