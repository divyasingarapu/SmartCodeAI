
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


COMMENT_MARKER = "## SmartCode AI Review"
API_VERSION = "2022-11-28"
MAX_COMMENT_LENGTH = 60000


def github_request(url, token, method="GET", payload=None):
    """Send an authenticated request to the GitHub API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }

    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        response_data = response.read().decode("utf-8")
        if response_data:
            return json.loads(response_data)
        return {}


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    pull_number = os.environ.get("PR_NUMBER")
    report_path = Path("pr-review-report.md")

    if not token or not repository or not pull_number:
        print("Missing GitHub environment variables.")
        return 1

    if not pull_number.isdigit():
        print("PR_NUMBER must be a valid positive integer.")
        return 1

    if not report_path.is_file():
        print("Review report not found.")
        return 1

    report = report_path.read_text(encoding="utf-8").strip()

    if len(report) > MAX_COMMENT_LENGTH:
        report = (
            report[:MAX_COMMENT_LENGTH]
            + "\n\n_Report truncated._"
        )

    body = f"{COMMENT_MARKER}\n\n{report}"

    comments_url = (
        f"https://api.github.com/repos/{repository}"
        f"/issues/{pull_number}/comments?per_page=100"
    )

    try:
        comments = github_request(comments_url, token)

        existing_comment = next(
            (
                comment
                for comment in comments
                if COMMENT_MARKER in comment.get("body", "")
            ),
            None,
        )

        if existing_comment:
            comment_id = existing_comment["id"]
            update_url = (
                f"https://api.github.com/repos/{repository}"
                f"/issues/comments/{comment_id}"
            )

            github_request(
                update_url,
                token,
                method="PATCH",
                payload={"body": body},
            )
            print("Existing SmartCode AI review comment updated.")
        else:
            github_request(
                comments_url.split("?")[0],
                token,
                method="POST",
                payload={"body": body},
            )
            print("New SmartCode AI review comment posted.")

    except urllib.error.HTTPError as error:
        print(f"GitHub API returned HTTP {error.code}.")
        print(error.read().decode("utf-8", errors="replace"))
        return 1
    except urllib.error.URLError as error:
        print(f"Could not connect to GitHub: {error}")
        return 1
    except (ValueError, KeyError, TypeError) as error:
        print(f"Could not process the GitHub API response: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
