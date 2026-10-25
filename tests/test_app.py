
"""Automated route tests for the SmartCode AI Flask application."""

from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client():
    """Create a Flask test client without starting the server."""
    app_module.app.config.update(
        TESTING=True,
        MAX_CONTENT_LENGTH=1_000_000,
    )

    with app_module.app.test_client() as test_client:
        yield test_client


def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"html" in response.data.lower()


@patch("app.run_code_analysis")
def test_homepage_reviews_code(mock_analysis, client):
    mock_analysis.return_value = []

    response = client.post(
        "/",
        data={
            "code": "print('Hello')",
            "language": "python",
            "action": "review",
        },
    )

    assert response.status_code == 200
    mock_analysis.assert_called_once_with("print('Hello')", "python")


@patch("app.run_code_analysis")
def test_homepage_handles_analysis_error(mock_analysis, client):
    mock_analysis.side_effect = RuntimeError("Internal test error")

    response = client.post(
        "/",
        data={
            "code": "print('Hello')",
            "language": "python",
            "action": "review",
        },
    )

    assert response.status_code == 200
    assert b"Code analysis failed" in response.data


@patch("app.generate_tests")
def test_homepage_generates_python_tests(mock_generate, client):
    mock_generate.return_value = {
        "test_code": "def test_add():\n    assert 1 + 1 == 2\n",
        "generated_count": 1,
        "functions": ["add"],
        "warnings": [],
    }

    response = client.post(
        "/",
        data={
            "code": "def add(a, b):\n    return a + b",
            "language": "python",
            "action": "generate_tests",
            "module_name": "sample",
        },
    )

    assert response.status_code == 200
    mock_generate.assert_called_once()


def test_test_generation_rejects_non_python_language(client):
    response = client.post(
        "/",
        data={
            "code": "public class Example {}",
            "language": "java",
            "action": "generate_tests",
        },
    )

    assert response.status_code == 200
    assert b"supports Python only" in response.data


@patch("app.list_python_files")
def test_github_page_lists_repository_files(mock_list, client):
    mock_list.return_value = {
        "files": [{"path": "main.py"}],
    }

    response = client.post(
        "/github",
        data={"owner": "example", "repo": "demo"},
    )

    assert response.status_code == 200
    mock_list.assert_called_once_with("example", "demo")


@patch("app.list_python_files")
def test_github_page_handles_service_error(mock_list, client):
    mock_list.side_effect = app_module.GitHubServiceError(
        "Repository not found"
    )

    response = client.post(
        "/github",
        data={"owner": "example", "repo": "missing"},
    )

    assert response.status_code == 200
    assert b"Repository not found" in response.data


@patch("app.run_code_analysis")
@patch("app.fetch_python_file")
@patch("app.list_python_files")
def test_github_reviews_selected_file(
    mock_list, mock_fetch, mock_analysis, client
):
    mock_list.return_value = {
        "files": [{"path": "main.py"}],
    }
    mock_fetch.return_value = "print('Hello')"
    mock_analysis.return_value = []

    response = client.post(
        "/github/review",
        data={
            "owner": "example",
            "repo": "demo",
            "path": "main.py",
        },
    )

    assert response.status_code == 200
    mock_fetch.assert_called_once_with(
        "example", "demo", "main.py"
    )
    mock_analysis.assert_called_once_with("print('Hello')", "python")


@patch("app.list_python_files")
def test_github_review_rejects_unlisted_file(mock_list, client):
    mock_list.return_value = {
        "files": [{"path": "main.py"}],
    }

    response = client.post(
        "/github/review",
        data={
            "owner": "example",
            "repo": "demo",
            "path": "../../secret.py",
        },
    )

    assert response.status_code == 200
    assert b"Invalid file selection" in response.data


@patch("app.run_code_analysis")
@patch("app.fetch_python_file")
@patch("app.list_python_files")
def test_batch_review_reviews_selected_files(
    mock_list, mock_fetch, mock_analysis, client
):
    mock_list.return_value = {
        "files": [
            {"path": "main.py"},
            {"path": "utils.py"},
        ],
    }
    mock_fetch.side_effect = [
        "print('main')",
        "print('utils')",
    ]
    mock_analysis.return_value = []

    response = client.post(
        "/github/review-batch",
        data={
            "owner": "example",
            "repo": "demo",
            "paths": ["main.py", "utils.py"],
        },
    )

    assert response.status_code == 200
    assert mock_fetch.call_count == 2
    assert b"main.py" in response.data


def test_batch_review_requires_selected_files(client):
    response = client.post(
        "/github/review-batch",
        data={
            "owner": "example",
            "repo": "demo",
            "paths": [],
        },
    )

    assert response.status_code == 200
    assert b"select at least one" in response.data.lower()


def test_batch_review_rejects_more_than_ten_files(client):
    response = client.post(
        "/github/review-batch",
        data={
            "owner": "example",
            "repo": "demo",
            "paths": [f"file{i}.py" for i in range(11)],
        },
    )

    assert response.status_code == 200
    assert b"no more than 10 files" in response.data.lower()


@patch("app.run_generated_tests")
def test_run_tests_returns_result(mock_run, client):
    mock_run.return_value = {
        "success": True,
        "output": "1 passed",
    }

    response = client.post(
        "/run-tests",
        data={
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): pass",
            "module_name": "sample",
        },
    )

    assert response.status_code == 200
    mock_run.assert_called_once_with(
        test_code="def test_add(): pass",
        source_code="def add(a, b): return a + b",
        module_name="sample",
    )


@patch("app.run_generated_tests")
def test_run_tests_handles_runner_exception(mock_run, client):
    mock_run.side_effect = RuntimeError("Test runner failed")

    response = client.post(
        "/run-tests",
        data={
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): pass",
            "module_name": "sample",
        },
    )

    assert response.status_code == 200
    assert b"Test execution failed" in response.data


def test_download_tests_rejects_empty_code(client):
    response = client.post(
        "/download-tests",
        data={"test_code": "   "},
    )

    assert response.status_code == 400
    assert b"No generated test code" in response.data


def test_download_tests_returns_python_file(client):
    test_code = "def test_add():\n    assert 1 + 1 == 2\n"

    response = client.post(
        "/download-tests",
        data={"test_code": test_code},
    )

    assert response.status_code == 200
    assert response.data == test_code.encode("utf-8")
    assert "attachment" in response.headers["Content-Disposition"]
    assert "generated_tests.py" in response.headers["Content-Disposition"]


def test_download_tests_rejects_oversized_file(client):
    response = client.post(
        "/download-tests",
        data={"test_code": "x" * 1_000_001},
    )

    assert response.status_code == 413


def test_oversized_request_returns_friendly_error(client):
    response = client.post(
        "/",
        data={"code": "x" * 1_100_000},
    )

    assert response.status_code == 413
    assert b"Request too large" in response.data
