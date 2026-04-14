#!/usr/bin/env python3
"""Push nib-preview-build.html to the joshmorales-site repo at nib/preview/index.html.

Token loading order (first hit wins):
  1. $GH_TOKEN env var
  2. /sessions/fervent-kind-brown/mnt/Prompt Wrapper/.gh_token

Cloudflare Pages auto-deploys from the repo, so the push is the deploy.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

REPO_OWNER = "ajoshmorales-max"
REPO_NAME = "joshmorales-site"
BRANCH = None  # auto-detected from repo's default_branch
TARGET_PATH = "nib/preview/index.html"
SOURCE_FILE = "/sessions/fervent-kind-brown/mnt/Prompt Wrapper/nib-preview-build.html"
TOKEN_FILE = "/sessions/fervent-kind-brown/mnt/Prompt Wrapper/.gh_token"
COMMIT_MESSAGE = "Deploy Nib UX redesign preview to /nib/preview/"


def load_token() -> str:
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"].strip()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    print(f"FAIL: no GH token in $GH_TOKEN or {TOKEN_FILE}", file=sys.stderr)
    sys.exit(2)


def gh_request(url: str, token: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "nib-preview-deployer")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = e.read().decode("utf-8")
        except Exception:
            payload = ""
        return e.code, payload


def main():
    token = load_token()

    # Read the file we want to deploy
    if not os.path.exists(SOURCE_FILE):
        print(f"FAIL: source file not found at {SOURCE_FILE}", file=sys.stderr)
        sys.exit(2)
    with open(SOURCE_FILE, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")

    # Auto-detect the default branch (so we don't have to guess main vs master)
    branch = BRANCH
    if not branch:
        status, repo_info = gh_request(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}", token)
        if status == 200 and isinstance(repo_info, dict):
            branch = repo_info.get("default_branch", "main")
        else:
            print(f"FAIL: could not fetch repo info ({status}): {repo_info}", file=sys.stderr)
            sys.exit(1)

    # Get current sha if file exists (needed for update)
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TARGET_PATH}"
    status, current = gh_request(f"{api_url}?ref={branch}", token)
    sha = current["sha"] if status == 200 and isinstance(current, dict) and "sha" in current else None

    body = {
        "message": COMMIT_MESSAGE,
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    status, resp = gh_request(api_url, token, method="PUT", body=body)
    if status not in (200, 201):
        print(f"FAIL: HTTP {status}\n{resp}", file=sys.stderr)
        sys.exit(1)

    commit_sha = resp.get("commit", {}).get("sha", "?")[:12] if isinstance(resp, dict) else "?"
    print(f"OK: pushed {TARGET_PATH} (commit {commit_sha})")
    print(f"     Cloudflare Pages should auto-deploy in ~30-90s")
    print(f"     Verify at https://joshmorales.ai/nib/preview/")


if __name__ == "__main__":
    main()
