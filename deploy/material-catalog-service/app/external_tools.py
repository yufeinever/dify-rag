from __future__ import annotations

import base64
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from .config import Settings


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3", "tr"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "tr"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = data.strip()
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned)
        self.text_parts.append(" ")

    @property
    def title(self) -> str:
        return _squash_ws(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return _squash_ws(" ".join(self.text_parts))


def _squash_ws(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value)
    return value.strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExternalResearchTools:
    """Read-only external research helpers for the MMB advisor Agent."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = max(int(settings.external_http_timeout_seconds or 15), 3)
        self.max_page_bytes = max(int(settings.external_max_page_bytes or 2_000_000), 100_000)
        self.user_agent = settings.external_user_agent or "MMBAdvisorAgent/0.1"

    def web_search(self, query: str, provider: str | None = None, limit: int = 5) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query is required")
        limit = min(max(int(limit or 5), 1), 10)
        selected = self._select_search_provider(provider)
        if not selected:
            return {
                "ok": False,
                "error": {
                    "code": "TOOL_NOT_CONFIGURED",
                    "message": "未配置外部搜索 API Key。可配置 TAVILY_API_KEY、SERPAPI_API_KEY 或 BRAVE_SEARCH_API_KEY。",
                },
                "query": query,
                "provider": None,
                "results": [],
                "count": 0,
            }
        provider_name, key = selected
        if provider_name == "tavily":
            results = self._search_tavily(query, key, limit)
        elif provider_name == "serpapi":
            results = self._search_serpapi(query, key, limit)
        elif provider_name == "brave":
            results = self._search_brave(query, key, limit)
        else:
            raise ValueError(f"unsupported search provider: {provider_name}")
        return {"ok": True, "query": query, "provider": provider_name, "results": results, "count": len(results), "fetched_at": _now_iso()}

    def read_web_page(self, url: str, max_chars: int = 12000) -> dict[str, Any]:
        url = self._validate_public_url(url)
        max_chars = min(max(int(max_chars or 12000), 500), 50000)
        body, final_url, content_type, status = self._fetch_bytes(url)
        charset = self._extract_charset(content_type) or "utf-8"
        text = body.decode(charset, errors="replace")
        title = ""
        if "html" in content_type.lower() or text.lstrip().startswith(("<!DOCTYPE", "<html", "<HTML")):
            parser = _HTMLTextExtractor()
            parser.feed(text)
            title = parser.title
            text = parser.text
        else:
            text = _squash_ws(text)
        truncated = len(text) > max_chars
        return {
            "ok": True,
            "url": url,
            "final_url": final_url,
            "status": status,
            "content_type": content_type,
            "title": title,
            "text": text[:max_chars],
            "truncated": truncated,
            "source_type": "external_web",
            "fetched_at": _now_iso(),
        }

    def summarize_web_sources(self, query: str | None = None, urls: str | None = None, limit: int = 3, max_chars_per_source: int = 2000) -> dict[str, Any]:
        limit = min(max(int(limit or 3), 1), 8)
        source_urls = self._split_urls(urls)[:limit]
        search_result: dict[str, Any] | None = None
        if not source_urls and query:
            search_result = self.web_search(query=query, limit=limit)
            source_urls = [item["url"] for item in search_result.get("results", []) if item.get("url")][:limit]
        sources: list[dict[str, Any]] = []
        for source_url in source_urls:
            try:
                page = self.read_web_page(source_url, max_chars=max_chars_per_source)
                sources.append(
                    {
                        "ok": True,
                        "url": page["final_url"],
                        "title": page.get("title") or page["final_url"],
                        "excerpt": page.get("text", "")[:max_chars_per_source],
                        "content_type": page.get("content_type"),
                        "fetched_at": page.get("fetched_at"),
                    }
                )
            except Exception as exc:
                sources.append({"ok": False, "url": source_url, "error": str(exc)})
        return {
            "ok": bool(sources),
            "query": query,
            "search": search_result,
            "sources": sources,
            "count": len(sources),
            "source_type": "external_web_summary",
        }

    def github_search_repositories(self, query: str, limit: int = 5) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query is required")
        data = self._github_get("/search/repositories", {"q": query, "per_page": min(max(int(limit or 5), 1), 10), "sort": "stars"})
        repos = []
        for item in data.get("items", []):
            repos.append(
                {
                    "full_name": item.get("full_name"),
                    "html_url": item.get("html_url"),
                    "description": item.get("description"),
                    "language": item.get("language"),
                    "stars": item.get("stargazers_count"),
                    "forks": item.get("forks_count"),
                    "updated_at": item.get("updated_at"),
                    "topics": item.get("topics") or [],
                }
            )
        return {"ok": True, "query": query, "repositories": repos, "count": len(repos), "source_type": "github"}

    def github_search_code(self, query: str, owner: str | None = None, repo: str | None = None, limit: int = 5) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query is required")
        q = query
        if owner and repo:
            q = f"{q} repo:{owner}/{repo}"
        data = self._github_get("/search/code", {"q": q, "per_page": min(max(int(limit or 5), 1), 10)})
        items = []
        for item in data.get("items", []):
            repo_info = item.get("repository") or {}
            items.append(
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "html_url": item.get("html_url"),
                    "repository": repo_info.get("full_name"),
                    "repository_url": repo_info.get("html_url"),
                }
            )
        return {"ok": True, "query": q, "code_results": items, "count": len(items), "source_type": "github"}

    def github_read_file(self, owner: str, repo: str, path: str, ref: str | None = None, max_chars: int = 20000) -> dict[str, Any]:
        owner, repo, path = self._clean_repo_args(owner, repo, path)
        params = {"ref": ref} if ref else None
        data = self._github_get(f"/repos/{quote(owner)}/{quote(repo)}/contents/{quote(path, safe='/')}", params)
        if data.get("type") != "file":
            raise ValueError("path is not a file")
        content = data.get("content") or ""
        if data.get("encoding") == "base64":
            text = base64.b64decode(content).decode("utf-8", errors="replace")
        else:
            text = str(content)
        max_chars = min(max(int(max_chars or 20000), 500), 50000)
        return {
            "ok": True,
            "repository": f"{owner}/{repo}",
            "path": path,
            "ref": ref,
            "html_url": data.get("html_url"),
            "download_url": data.get("download_url"),
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
            "source_type": "github_file",
        }

    def github_list_issues(self, owner: str, repo: str, state: str = "open", limit: int = 10) -> dict[str, Any]:
        owner, repo, _ = self._clean_repo_args(owner, repo, "README.md")
        data = self._github_get(f"/repos/{quote(owner)}/{quote(repo)}/issues", {"state": state or "open", "per_page": min(max(int(limit or 10), 1), 20)})
        issues = []
        for item in data:
            if "pull_request" in item:
                continue
            issues.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "html_url": item.get("html_url"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "user": (item.get("user") or {}).get("login"),
                }
            )
        return {"ok": True, "repository": f"{owner}/{repo}", "issues": issues, "count": len(issues), "source_type": "github"}

    def github_list_pull_requests(self, owner: str, repo: str, state: str = "open", limit: int = 10) -> dict[str, Any]:
        owner, repo, _ = self._clean_repo_args(owner, repo, "README.md")
        data = self._github_get(f"/repos/{quote(owner)}/{quote(repo)}/pulls", {"state": state or "open", "per_page": min(max(int(limit or 10), 1), 20)})
        pulls = []
        for item in data:
            pulls.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "html_url": item.get("html_url"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "user": (item.get("user") or {}).get("login"),
                }
            )
        return {"ok": True, "repository": f"{owner}/{repo}", "pull_requests": pulls, "count": len(pulls), "source_type": "github"}

    def github_list_actions_runs(self, owner: str, repo: str, branch: str | None = None, limit: int = 10) -> dict[str, Any]:
        owner, repo, _ = self._clean_repo_args(owner, repo, "README.md")
        params: dict[str, Any] = {"per_page": min(max(int(limit or 10), 1), 20)}
        if branch:
            params["branch"] = branch
        data = self._github_get(f"/repos/{quote(owner)}/{quote(repo)}/actions/runs", params)
        runs = []
        for item in data.get("workflow_runs", []):
            runs.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "head_branch": item.get("head_branch"),
                    "status": item.get("status"),
                    "conclusion": item.get("conclusion"),
                    "html_url": item.get("html_url"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )
        return {"ok": True, "repository": f"{owner}/{repo}", "runs": runs, "count": len(runs), "source_type": "github_actions"}

    def github_prepare_issue(self, owner: str, repo: str, title: str, body: str, labels: str | None = None) -> dict[str, Any]:
        owner, repo, _ = self._clean_repo_args(owner, repo, "README.md")
        title = (title or "").strip()
        body = (body or "").strip()
        if not title or not body:
            raise ValueError("title and body are required")
        label_list = [item.strip() for item in (labels or "").split(",") if item.strip()]
        draft = {
            "repository": f"{owner}/{repo}",
            "title": title,
            "body": body,
            "labels": label_list,
        }
        return {
            "ok": True,
            "action": "create_github_issue_draft",
            "draft": draft,
            "requires_confirmation": True,
            "execution_policy": "This tool does not write to GitHub. Ask for explicit confirmation or use an approved write-capable GitHub integration before creating the issue.",
            "markdown": self._issue_markdown(draft),
        }

    def _select_search_provider(self, provider: str | None) -> tuple[str, str] | None:
        requested = (provider or self.settings.web_search_provider or "auto").strip().lower()
        candidates = [requested] if requested not in {"", "auto"} else ["tavily", "serpapi", "brave"]
        for candidate in candidates:
            key = {
                "tavily": self.settings.tavily_api_key,
                "serpapi": self.settings.serpapi_api_key,
                "brave": self.settings.brave_search_api_key,
            }.get(candidate, "")
            if key:
                return candidate, key
        return None

    def _search_tavily(self, query: str, api_key: str, limit: int) -> list[dict[str, Any]]:
        data = self._json_request(
            "https://api.tavily.com/search",
            method="POST",
            body={"api_key": api_key, "query": query, "max_results": limit, "search_depth": "basic", "include_answer": False},
        )
        return [
            {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("content"), "score": item.get("score")}
            for item in data.get("results", [])[:limit]
        ]

    def _search_serpapi(self, query: str, api_key: str, limit: int) -> list[dict[str, Any]]:
        data = self._json_request("https://serpapi.com/search.json", params={"engine": "google", "q": query, "api_key": api_key, "num": limit})
        organic = data.get("organic_results") or []
        return [
            {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet"), "position": item.get("position")}
            for item in organic[:limit]
        ]

    def _search_brave(self, query: str, api_key: str, limit: int) -> list[dict[str, Any]]:
        data = self._json_request(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        )
        values = (data.get("web") or {}).get("results") or []
        return [
            {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("description")}
            for item in values[:limit]
        ]

    def _github_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        base = (self.settings.github_api_base_url or "https://api.github.com").rstrip("/")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return self._json_request(f"{base}{path}", params=params, headers=headers)

    def _json_request(self, url: str, method: str = "GET", params: dict[str, Any] | None = None, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"
        data = None
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.max_page_bytes)
        except HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"request failed for {url}: {exc.reason}") from exc
        return json.loads(raw.decode("utf-8", errors="replace"))

    def _fetch_bytes(self, url: str) -> tuple[bytes, str, str, int]:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html, text/plain;q=0.9, */*;q=0.1"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read(self.max_page_bytes)
                final_url = response.geturl()
                content_type = response.headers.get("Content-Type", "")
                status = response.status
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} from {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"request failed for {url}: {exc.reason}") from exc
        return body, final_url, content_type, status

    def _validate_public_url(self, url: str) -> str:
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url must be http or https")
        host = parsed.hostname.lower().strip("[]")
        if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
            raise ValueError("private or local URLs are not allowed")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            for item in socket.getaddrinfo(host, None):
                address = item[4][0]
                try:
                    resolved_ip = ipaddress.ip_address(address)
                except ValueError:
                    continue
                self._reject_private_ip(resolved_ip)
        else:
            self._reject_private_ip(ip)
        return parsed.geturl()

    def _reject_private_ip(self, ip: ipaddress._BaseAddress) -> None:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("private or local URLs are not allowed")

    def _extract_charset(self, content_type: str) -> str | None:
        match = re.search(r"charset=([^;]+)", content_type or "", re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _split_urls(self, urls: str | None) -> list[str]:
        if not urls:
            return []
        return [item.strip() for item in re.split(r"[\n, ]+", urls) if item.strip()]

    def _clean_repo_args(self, owner: str, repo: str, path: str) -> tuple[str, str, str]:
        owner = (owner or "").strip()
        repo = (repo or "").strip()
        path = (path or "").strip().lstrip("/")
        if not owner or not repo or not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
            raise ValueError("owner and repo are required and must be GitHub-safe names")
        if not path or ".." in path.split("/"):
            raise ValueError("path is required and cannot contain parent traversal")
        return owner, repo, path

    def _issue_markdown(self, draft: dict[str, Any]) -> str:
        labels = ", ".join(draft.get("labels") or []) or "无"
        return f"### GitHub Issue 草稿\n\n仓库：{draft['repository']}\n\n标题：{draft['title']}\n\n标签：{labels}\n\n正文：\n\n{draft['body']}\n"
