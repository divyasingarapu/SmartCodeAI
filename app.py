
"""Flask application for SmartCode AI."""

from io import BytesIO

from flask import Flask, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from analyzer import analyze_code
from finding_deduplicator import deduplicate_findings
from github_service import (
    GitHubServiceError,
    fetch_python_file,
    list_python_files,
)
from security_scanner import scan_security
from test_generator import generate_tests
from test_runner import run_generated_tests

app = Flask(__name__)

# Limit the size of incoming requests to 1 MB.
app.config["MAX_CONTENT_LENGTH"] = 1_000_000

MAX_DOWNLOAD_SIZE = 1_000_000
MAX_BATCH_FILES = 10


def run_code_analysis(code, language):
    """Run analyzers and merge overlapping findings."""
    existing_issues = analyze_code(code, language)
    security_issues = scan_security(code, language)

    return deduplicate_findings(
        existing_issues + security_issues,
        source_code=code,
        language=language,
    )


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(error):
    """Show a friendly message for oversized requests."""
    message = (
        "Request too large. Please keep your submitted code and "
        "test data within the 1 MB request limit."
    )
    return message, 413


@app.route("/", methods=["GET", "POST"])
def home():
    """Handle code review and test generation."""
    issues = []
    code = ""
    language = "python"
    action = "review"
    module_name = "your_module"
    test_result = None
    run_result = None
    error_message = ""

    if request.method == "POST":
        code = request.form.get("code", "")
        language = request.form.get("language", "python").lower()
        action = request.form.get("action", "review")

        module_name = (
            request.form.get("module_name", "your_module").strip()
            or "your_module"
        )

        if action == "generate_tests":
            if language != "python":
                test_result = {
                    "test_code": "",
                    "generated_count": 0,
                    "functions": [],
                    "warnings": [
                        "Test generation currently supports Python only."
                    ],
                }
            else:
                try:
                    test_result = generate_tests(
                        source_code=code,
                        module_name=module_name,
                        max_cases_per_function=6,
                    )
                except ValueError as error:
                    error_message = str(error)

        else:
            try:
                issues = run_code_analysis(code, language)
            except Exception:
                app.logger.exception("Code analysis failed")
                error_message = (
                    "Code analysis failed. Check the submitted code "
                    "and application terminal for details."
                )

    return render_template(
        "index.html",
        issues=issues,
        code=code,
        language=language,
        action=action,
        module_name=module_name,
        test_result=test_result,
        run_result=run_result,
        error_message=error_message,
    )


@app.route("/github", methods=["GET", "POST"])
def github_repository():
    """List Python files in a public GitHub repository."""
    owner = ""
    repo = ""
    repository = None
    files = []
    error_message = ""

    if request.method == "POST":
        owner = request.form.get("owner", "").strip()
        repo = request.form.get("repo", "").strip()

        try:
            repository = list_python_files(owner, repo)
            files = repository["files"]
        except GitHubServiceError as error:
            error_message = str(error)

    return render_template(
        "github.html",
        owner=owner,
        repo=repo,
        repository=repository,
        files=files,
        error_message=error_message,
        code="",
        selected_path="",
        issues=[],
        batch_results=[],
        batch_summary=None,
    )


@app.route("/github/review", methods=["POST"])
def review_github_file():
    """Review a selected Python file from a public GitHub repository."""
    owner = request.form.get("owner", "").strip()
    repo = request.form.get("repo", "").strip()
    path = request.form.get("path", "").strip()

    code = ""
    issues = []
    error_message = ""

    try:
        repository = list_python_files(owner, repo)
        allowed_paths = {
            item["path"] for item in repository["files"]
        }

        if path not in allowed_paths:
            error_message = (
                "Invalid file selection. Browse the repository and "
                "select a Python file from the displayed list."
            )
        else:
            code = fetch_python_file(owner, repo, path)
            issues = run_code_analysis(code, "python")

    except GitHubServiceError as error:
        error_message = str(error)
    except Exception:
        app.logger.exception("GitHub file review failed")
        error_message = "An unexpected error occurred during file review."

    return render_template(
        "github.html",
        owner=owner,
        repo=repo,
        repository=None,
        files=[],
        error_message=error_message,
        issues=issues,
        code=code,
        selected_path=path,
        batch_results=[],
        batch_summary=None,
    )


@app.route("/github/review-batch", methods=["POST"])
def review_github_batch():
    """Review multiple selected Python files from a public repository."""
    owner = request.form.get("owner", "").strip()
    repo = request.form.get("repo", "").strip()

    selected_paths = list(
        dict.fromkeys(
            path.strip()
            for path in request.form.getlist("paths")
            if path.strip()
        )
    )

    batch_results = []
    error_message = ""

    if not owner or not repo:
        error_message = "Repository owner and name are required."

    elif not selected_paths:
        error_message = "Please select at least one Python file."

    elif len(selected_paths) > MAX_BATCH_FILES:
        error_message = (
            f"Please select no more than {MAX_BATCH_FILES} files per batch."
        )

    else:
        try:
            repository = list_python_files(owner, repo)
            allowed_paths = {
                item["path"] for item in repository["files"]
            }

            if any(path not in allowed_paths for path in selected_paths):
                error_message = (
                    "Invalid file selection. Browse the repository again "
                    "and select files from the displayed list."
                )
            else:
                for path in selected_paths:
                    try:
                        source_code = fetch_python_file(
                            owner, repo, path
                        )
                        issues = run_code_analysis(
                            source_code, "python"
                        )

                        batch_results.append(
                            {
                                "path": path,
                                "issues": issues,
                                "issue_count": len(issues),
                                "error": None,
                            }
                        )

                    except GitHubServiceError as error:
                        batch_results.append(
                            {
                                "path": path,
                                "issues": [],
                                "issue_count": 0,
                                "error": str(error),
                            }
                        )

                    except Exception:
                        app.logger.exception(
                            "Failed to review GitHub file: %s", path
                        )
                        batch_results.append(
                            {
                                "path": path,
                                "issues": [],
                                "issue_count": 0,
                                "error": (
                                    "Unexpected error while reviewing "
                                    "this file."
                                ),
                            }
                        )

        except GitHubServiceError as error:
            error_message = str(error)
        except Exception:
            app.logger.exception("GitHub batch review failed")
            error_message = (
                "An unexpected error occurred while loading the repository."
            )

    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "other": 0,
    }

    reviewed_count = 0
    total_issues = 0

    for result in batch_results:
        if result["error"] is not None:
            continue

        reviewed_count += 1

        for issue in result["issues"]:
            total_issues += 1
            severity = str(
                issue.get("severity", "other")
            ).lower()

            if severity in severity_counts:
                severity_counts[severity] += 1
            else:
                severity_counts["other"] += 1

    batch_summary = {
        "selected": len(selected_paths),
        "reviewed": reviewed_count,
        "failed": len(batch_results) - reviewed_count,
        "total_issues": total_issues,
        "severity_counts": severity_counts,
    }

    return render_template(
        "github.html",
        owner=owner,
        repo=repo,
        repository=None,
        files=[],
        error_message=error_message,
        code="",
        selected_path="",
        issues=[],
        batch_results=batch_results,
        batch_summary=batch_summary,
    )


@app.route("/run-tests", methods=["POST"])
def run_tests():
    """Run generated tests against the supplied source code."""
    code = request.form.get("source_code", "")
    test_code = request.form.get("test_code", "")

    module_name = (
        request.form.get("module_name", "your_module").strip()
        or "your_module"
    )

    try:
        run_result = run_generated_tests(
            test_code=test_code,
            source_code=code,
            module_name=module_name,
        )

        test_result = {
            "test_code": test_code,
            "generated_count": test_code.count("def test_"),
            "functions": [],
            "warnings": [],
        }

        error_message = ""

    except Exception:
        app.logger.exception("Generated test execution failed")

        run_result = None
        test_result = {
            "test_code": test_code,
            "generated_count": test_code.count("def test_"),
            "functions": [],
            "warnings": [],
        }
        error_message = (
            "Test execution failed. Check the application terminal "
            "for details."
        )

    return render_template(
        "index.html",
        issues=[],
        code=code,
        language="python",
        action="run_tests",
        module_name=module_name,
        test_result=test_result,
        run_result=run_result,
        error_message=error_message,
    )


@app.route("/download-tests", methods=["POST"])
def download_tests():
    """Download generated tests as a Python file."""
    test_code = request.form.get("test_code", "")

    if not test_code.strip():
        return "No generated test code was provided.", 400

    if len(test_code.encode("utf-8")) > MAX_DOWNLOAD_SIZE:
        return "The generated test file is too large to download.", 413

    file_data = BytesIO(test_code.encode("utf-8"))

    return send_file(
        file_data,
        mimetype="text/x-python",
        as_attachment=True,
        download_name="generated_tests.py",
    )


if __name__ == "__main__":
    # Local development only. The test runner needs proper isolation
    # before this application should be exposed to other users.
    app.run(debug=False)
