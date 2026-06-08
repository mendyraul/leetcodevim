from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"


@dataclass
class LeetCodeSession:
    session: str
    csrf: str | None = None


@dataclass
class Problem:
    title: str
    title_slug: str
    question_id: str
    content: str
    difficulty: str
    sample_test_case: str | None
    code_snippets: list[dict[str, str]]


class LeetCodeError(RuntimeError):
    pass


def _build_headers(auth: LeetCodeSession | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com/",
        "User-Agent": "leetcode-vim-cli",
    }
    if not auth:
        return headers
    cookies = [f"LEETCODE_SESSION={auth.session}"]
    if auth.csrf:
        cookies.append(f"csrftoken={auth.csrf}")
    headers["Cookie"] = "; ".join(cookies)
    if auth.csrf:
        headers["x-csrftoken"] = auth.csrf
    return headers


def _post_graphql(query: str, variables: dict[str, str], auth: LeetCodeSession | None = None) -> dict[str, object]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(LEETCODE_GRAPHQL_URL, data=payload, method="POST")
    for key, value in _build_headers(auth).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise LeetCodeError(f"LeetCode API error: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LeetCodeError(f"LeetCode API error: {exc.reason}") from exc
    data = json.loads(raw)
    if data.get("errors"):
        raise LeetCodeError(f"LeetCode API error: {data['errors']}")
    return data


def fetch_problem(slug: str, auth: LeetCodeSession | None = None) -> Problem:
    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionId
        title
        titleSlug
        content
        difficulty
        sampleTestCase
        codeSnippets {
          lang
          langSlug
          code
        }
      }
    }
    """
    data = _post_graphql(query, {"titleSlug": slug}, auth)
    question = data.get("data", {}).get("question")
    if not question:
        raise LeetCodeError("Problem not found.")
    return Problem(
        question_id=str(question["questionId"]),
        title=question["title"],
        title_slug=question["titleSlug"],
        content=question["content"],
        difficulty=question["difficulty"],
        sample_test_case=question.get("sampleTestCase"),
        code_snippets=question.get("codeSnippets") or [],
    )


def fetch_user(auth: LeetCodeSession) -> str:
    query = """
    query userStatus {
      userStatus {
        username
        isSignedIn
      }
    }
    """
    data = _post_graphql(query, {}, auth)
    status = data.get("data", {}).get("userStatus") or {}
    if not status.get("isSignedIn"):
        raise LeetCodeError("Not signed in.")
    return status.get("username") or "unknown"


def submit_solution(
    slug: str,
    question_id: str,
    lang_slug: str,
    code: str,
    auth: LeetCodeSession,
) -> str:
    if not auth.csrf:
        raise LeetCodeError("Missing csrftoken; submission requires LEETCODE_CSRF.")
    url = f"https://leetcode.com/problems/{slug}/submit/"
    payload = json.dumps(
        {"lang": lang_slug, "question_id": question_id, "typed_code": code}
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    headers = _build_headers(auth)
    headers["Referer"] = f"https://leetcode.com/problems/{slug}/"
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise LeetCodeError(f"Submit failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LeetCodeError(f"Submit failed: {exc.reason}") from exc
    data = json.loads(raw)
    submission_id = data.get("submission_id")
    if not submission_id:
        raise LeetCodeError(f"Submit failed: {data}")
    return str(submission_id)


def poll_submission(submission_id: str, auth: LeetCodeSession) -> dict[str, object]:
    url = f"https://leetcode.com/submissions/detail/{submission_id}/check/"
    request = urllib.request.Request(url, method="GET")
    for key, value in _build_headers(auth).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise LeetCodeError(f"Poll failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LeetCodeError(f"Poll failed: {exc.reason}") from exc
    return json.loads(raw)
