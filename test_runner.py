
"""Run generated pytest tests in a temporary workspace.

This is for trusted local development only, not a secure sandbox.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_CODE_SIZE = 100_000
MAX_TIMEOUT_SECONDS = 10


def _result(
    success=False,
    passed=0,
    failed=0,
    skipped=0,
    errors=None,
    output="",
):
    return {
        "success": success,
        "total": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors or [],
        "output": output[-12000:],
    }


def run_generated_tests(test_code, source_code, module_name, timeout=10):
    """Run generated tests against the supplied source in a temporary folder."""

    if not test_code.strip() or not source_code.strip():
        return _result(errors=["Source code and generated tests are required."])

    if (
        len(test_code.encode("utf-8")) > MAX_CODE_SIZE
        or len(source_code.encode("utf-8")) > MAX_CODE_SIZE
    ):
        return _result(errors=["Source or test code exceeds the 100 KB limit."])

    if not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", module_name):
        return _result(errors=["Invalid Python module name."])

    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        return _result(errors=["Timeout must be between 1 and 10 seconds."])

    with tempfile.TemporaryDirectory(prefix="smartcode_tests_") as temp_dir:
        root = Path(temp_dir)

        module_parts = module_name.split(".")
        module_dir = root

        for package in module_parts[:-1]:
            module_dir = module_dir / package
            module_dir.mkdir(exist_ok=True)
            (module_dir / "__init__.py").write_text("", encoding="utf-8")

        source_file = module_dir / f"{module_parts[-1]}.py"
        test_file = root / "test_generated.py"

        source_file.write_text(source_code, encoding="utf-8")
        test_file.write_text(test_code, encoding="utf-8")

        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "--no-header",
            str(test_file),
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            output = (
                completed.stdout + "\n" + completed.stderr
            ).strip()

            counts = {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
            }

            summary = output.splitlines()

            for line in reversed(summary):
                for category in counts:
                    match = re.search(
                        rf"\b(\d+)\s+{category}\b",
                        line,
                    )
                    if match:
                        counts[category] = int(match.group(1))

                if any(
                    re.search(rf"\b\d+\s+{category}\b", line)
                    for category in counts
                ):
                    break

            errors = []

            if completed.returncode != 0:
                errors.append(
                    "Some tests failed, or pytest encountered an error. "
                    "Review the output for details."
                )

            return _result(
                success=completed.returncode == 0,
                passed=counts["passed"],
                failed=counts["failed"],
                skipped=counts["skipped"],
                errors=errors,
                output=output,
            )

        except subprocess.TimeoutExpired:
            return _result(
                errors=[f"Test execution exceeded {timeout} seconds."]
            )
        except OSError as error:
            return _result(errors=[f"Could not start pytest: {error}"])
