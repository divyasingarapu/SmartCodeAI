
"""Read Python file metadata from public GitHub repositories."""

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"
MAX_FILES = 1000
MAX_FILE_SIZE = 100_000

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubServiceError(Exception):
    """Raised when a GitHub repository cannot be inspected."""


def _get_json(url):
    """Fetch JSON from the GitHub API."""

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SmartCodeAI-Local-Reviewer",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            response_data = response.read()
            return json.loads(response_data.decode("utf-8"))

    except HTTPError as error:
        if error.code == 404:
            raise GitHubServiceError(
                "Repository or file not found, or it is not public."
            ) from error

        if error.code in (403, 429):
            raise GitHubServiceError(
                "GitHub rate limit or access restriction reached. "
                "Please try again later."
            ) from error

        raise GitHubServiceError(
            f"GitHub returned HTTP {error.code}."
        ) from error

    except (URLError, TimeoutError, OSError) as error:
        raise GitHubServiceError(
            "Could not connect to GitHub. Check your internet connection."
        ) from error

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GitHubServiceError(
            "GitHub returned an invalid JSON response."
        ) from error


def _validate_repository(owner, repo):
    """Validate the repository owner and name."""

    if not isinstance(owner, str) or not NAME_PATTERN.fullmatch(owner):
        raise GitHubServiceError("Invalid GitHub owner name.")

    if not isinstance(repo, str) or not NAME_PATTERN.fullmatch(repo):
        raise GitHubServiceError("Invalid GitHub repository name.")


def list_python_files(owner, repo):
    """List small Python files in a public GitHub repository."""

    _validate_repository(owner, repo)

    owner_path = quote(owner, safe="")
    repo_path = quote(repo, safe="")

    repository_url = (
        f"{GITHUB_API}/repos/{owner_path}/{repo_path}"
    )

    metadata = _get_json(repository_url)
    branch = metadata.get("default_branch")

    if not isinstance(branch, str) or not branch:
        raise GitHubServiceError(
            "Could not determine the repository's default branch."
        )

    branch_path = quote(branch, safe="")

    tree_url = (
        f"{repository_url}/git/trees/{branch_path}?recursive=1"
    )

    tree = _get_json(tree_url)

    if tree.get("truncated"):
        raise GitHubServiceError(
            "This repository is too large to list completely. "
            "Please try a smaller repository."
        )

    entries = tree.get("tree", [])

    if not isinstance(entries, list):
        raise GitHubServiceError(
            "Unexpected GitHub file listing."
        )

    python_files = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        if entry.get("type") != "blob":
            continue

        path = entry.get("path", "")
        size = entry.get("size")

        if not isinstance(path, str) or not path.endswith(".py"):
            continue

        if not isinstance(size, int) or size < 0:
            continue

        if size > MAX_FILE_SIZE:
            continue

        python_files.append({
            "path": path,
            "size": size,
        })

        if len(python_files) >= MAX_FILES:
            break

    return {
        "repository": metadata.get(
            "full_name",
            f"{owner}/{repo}",
        ),
        "branch": branch,
        "files": python_files,
    }


def fetch_python_file(owner, repo, path):
    """Fetch a small Python source file from a public GitHub repository."""

    _validate_repository(owner, repo)

    if (
        not isinstance(path, str)
        or not path.endswith(".py")
        or path.startswith("/")
        or "\\" in path
        or any(
            part in ("", ".", "..")
            for part in path.split("/")
        )
    ):
        raise GitHubServiceError("Invalid Python file path.")

    owner_path = quote(owner, safe="")
    repo_path = quote(repo, safe="")
    file_path = quote(path, safe="/")

    repository_url = (
        f"{GITHUB_API}/repos/{owner_path}/{repo_path}"
    )

    metadata = _get_json(repository_url)
    branch = metadata.get("default_branch")

    if not isinstance(branch, str) or not branch:
        raise GitHubServiceError(
            "Could not determine the default branch."
        )

    branch_path = quote(branch, safe="")

    contents_url = (
        f"{repository_url}/contents/{file_path}"
        f"?ref={branch_path}"
    )

    file_data = _get_json(contents_url)

    if not isinstance(file_data, dict):
        raise GitHubServiceError(
            "GitHub returned an unexpected file response."
        )

    if file_data.get("type") != "file":
        raise GitHubServiceError(
            "The selected path is not a file."
        )

    if file_data.get("encoding") != "base64":
        raise GitHubServiceError(
            "GitHub did not return Base64-encoded file contents. "
            "The selected file may be too large or unsupported."
        )

    size = file_data.get("size")

    if (
        not isinstance(size, int)
        or size < 0
        or size > MAX_FILE_SIZE
    ):
        raise GitHubServiceError(
            "The selected file exceeds the 100 KB size limit."
        )

    content = file_data.get("content")

    if not isinstance(content, str):
        raise GitHubServiceError(
            "GitHub returned no file contents."
        )

    # GitHub Base64 content can contain whitespace or line breaks.
    cleaned_content = "".join(content.split())

    try:
        source_bytes = base64.b64decode(
            cleaned_content,
            validate=True,
        )
    except (ValueError, base64.binascii.Error) as error:
        raise GitHubServiceError(
            "GitHub returned invalid Base64 file contents."
        ) from error

    if len(source_bytes) > MAX_FILE_SIZE:
        raise GitHubServiceError(
            "The selected file exceeds the 100 KB size limit."
        )

    # Accept UTF-8 with or without a byte-order mark.
    try:
        source_code = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise GitHubServiceError(
            "The selected file contains invalid UTF-8 bytes "
            f"near byte position {error.start}."
        ) from error

    return source_code
