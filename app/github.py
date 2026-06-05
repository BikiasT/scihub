"""Lightweight GitHub connection for the `code` artifact.

When a publication links a GitHub repository as its code, we fetch live metadata
from the GitHub REST API and render it as a rich card. Stdlib only — no extra
dependency. Results are cached for the process lifetime to stay well under the
unauthenticated rate limit; set GITHUB_TOKEN to raise that limit.
"""
import json
import os
import re
import urllib.error
import urllib.request

_REPO_URL = re.compile(
    r"github\.com[:/]+(?P<owner>[^/]+)/(?P<repo>[^/#?]+)", re.IGNORECASE
)
_cache: dict[str, dict] = {}


def parse_repo(url: str):
    """Return (owner, repo) for a GitHub URL, or None if it isn't one."""
    if not url:
        return None
    m = _REPO_URL.search(url)
    if not m:
        return None
    owner = m.group("owner")
    repo = m.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _api(path: str):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "scihub-app",
        },
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def fetch_repo(url: str):
    """Fetch repo metadata for a GitHub URL.

    Returns a dict the template can render, or {"error": ...} when the repo
    can't be reached (offline, rate-limited, private, or not found). Never raises.
    """
    parsed = parse_repo(url)
    if not parsed:
        return None
    owner, repo = parsed
    key = f"{owner}/{repo}"
    if key in _cache:
        return _cache[key]

    try:
        data = _api(f"/repos/{owner}/{repo}")
        info = {
            "full_name": data.get("full_name", key),
            "html_url": data.get("html_url", url),
            "description": data.get("description") or "",
            "language": data.get("language") or "",
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "default_branch": data.get("default_branch", "main"),
            "pushed_at": (data.get("pushed_at") or "")[:10],
            "license": (data.get("license") or {}).get("spdx_id") or "",
            "clone_url": data.get("clone_url", f"{url}.git"),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        info = {"full_name": key, "html_url": url, "error": str(e)}

    _cache[key] = info
    return info
