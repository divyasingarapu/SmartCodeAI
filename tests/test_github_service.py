
from unittest.mock import patch

import pytest

from github_service import GitHubServiceError, list_python_files


def test_rejects_invalid_owner():
    with pytest.raises(GitHubServiceError, match="Invalid GitHub owner"):
        list_python_files("../invalid", "Hello-World")


def test_rejects_invalid_repository_name():
    with pytest.raises(
        GitHubServiceError,
        match="Invalid GitHub repository",
    ):
        list_python_files("octocat", "bad/repo")


@patch("github_service._get_json")
def test_lists_python_files(mock_get_json):
    mock_get_json.side_effect = [
        {"full_name": "octocat/Hello-World", "default_branch": "main"},
        {
            "truncated": False,
            "tree": [
                {"type": "blob", "path": "app.py", "size": 500},
                {"type": "blob", "path": "README.md", "size": 200},
                {"type": "tree", "path": "src", "size": 0},
                {"type": "blob", "path": "large.py", "size": 150_000},
            ],
        },
    ]

    result = list_python_files("octocat", "Hello-World")

    assert result["repository"] == "octocat/Hello-World"
    assert result["branch"] == "main"
    assert result["files"] == [{"path": "app.py", "size": 500}]
    assert mock_get_json.call_count == 2


@patch("github_service._get_json")
def test_handles_missing_repository(mock_get_json):
    mock_get_json.side_effect = GitHubServiceError(
        "Repository not found or it is not public."
    )

    with pytest.raises(GitHubServiceError, match="Repository not found"):
        list_python_files("octocat", "missing-repository")


@patch("github_service._get_json")
def test_rejects_truncated_repository_tree(mock_get_json):
    mock_get_json.side_effect = [
        {"full_name": "octocat/Hello-World", "default_branch": "main"},
        {"truncated": True, "tree": []},
    ]

    with pytest.raises(GitHubServiceError, match="too large to list"):
        list_python_files("octocat", "Hello-World")
