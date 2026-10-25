
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    pull_number = os.environ.get("PR_NUMBER")
    report_path = Path("pr-review-report.md")

    if not token or not repository or not pull_number:
        print("Missing GitHub environment variables.")
        return 1

    if not report_path.is_file():
        print("Review report not found.")
        return 1

    report = report_path.read_text(encoding="utf-8").strip()

    # Keep the comment within a reasonable size.
    max_length = 60000
    if len(report) > max_length:
        report = report[:max_length] + "\n\n_Report truncated._"

    payload = (
        '{"body": '
        + __import__("json").dumps(
            "## SmartCode AI Review\n\n" + report
        )
        + "}"
    )

    url = (
        f"https://api.github.com/repos/{repository}"
        f"/issues/{pull_number}/comments"
    )

    request = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"Pull request comment posted (HTTP {response.status}).")
    except urllib.error.HTTPError as error:
        print(f"GitHub API returned HTTP {error.code}.")
        print(error.read().decode("utf-8", errors="replace"))
        return 1
    except urllib.error.URLError as error:
        print(f"Could not connect to GitHub: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
