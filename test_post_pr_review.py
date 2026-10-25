
import json
from unittest.mock import MagicMock, patch

import post_pr_review


def setup_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repository")
    monkeypatch.setenv("PR_NUMBER", "12")

    report = tmp_path / "pr-review-report.md"
    report.write_text("# Review results\n\nNo issues found.", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return report


@patch("post_pr_review.github_request")
def test_posts_new_comment_when_none_exists(
    mock_request, monkeypatch, tmp_path, capsys
):
    setup_environment(monkeypatch, tmp_path)
    mock_request.return_value = []

    result = post_pr_review.main()

    assert result == 0
    assert mock_request.call_count == 2

    first_call = mock_request.call_args_list[0]
    assert first_call.args[1] == "test-token"

    second_call = mock_request.call_args_list[1]
    assert second_call.kwargs["method"] == "POST"
    assert second_call.kwargs["payload"]["body"].startswith(
        "## SmartCode AI Review"
    )
    assert "New SmartCode AI review comment posted." in capsys.readouterr().out


@patch("post_pr_review.github_request")
def test_updates_existing_comment_instead_of_posting_duplicate(
    mock_request, monkeypatch, tmp_path, capsys
):
    setup_environment(monkeypatch, tmp_path)
    mock_request.return_value = [
        {
            "id": 456,
            "body": "## SmartCode AI Review\n\nOld report",
        }
    ]

    result = post_pr_review.main()

    assert result == 0
    assert mock_request.call_count == 2

    update_call = mock_request.call_args_list[1]
    assert update_call.args[0].endswith("/issues/comments/456")
    assert update_call.kwargs["method"] == "PATCH"
    assert "No issues found." in update_call.kwargs["payload"]["body"]
    assert "Existing SmartCode AI review comment updated." in capsys.readouterr().out


def test_rejects_missing_environment_variables(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("PR_NUMBER", raising=False)

    assert post_pr_review.main() == 1


def test_rejects_invalid_pull_request_number(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repository")
    monkeypatch.setenv("PR_NUMBER", "abc")
    monkeypatch.chdir(tmp_path)

    assert post_pr_review.main() == 1
