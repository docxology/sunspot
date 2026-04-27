import json
from datetime import date
from pathlib import Path

import httpx

from sunspot.github import commits as gh
from sunspot.github.commits import _commit_dt, first_commit_date, iter_commits

FIX = Path(__file__).parent / "fixtures" / "github_commit.json"


def test_commit_time_from_api_sample() -> None:
    d = json.loads(FIX.read_text())
    t = _commit_dt(d)
    assert t is not None
    assert t.year == 2020
    assert t.month == 1
    assert t.day == 15


def _client_with(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(base_url="https://api.github.com", transport=transport)


def test_first_commit_date_uses_disk_cache_skips_http(tmp_path, monkeypatch) -> None:
    from sunspot.github import commit_cache as cc

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cc.save_first_commit_date("nohttp", date(2011, 6, 15))

    def boom(*_a, **_kw):
        raise RuntimeError("HTTP should not run when first_commit_date cache hits")

    monkeypatch.setattr("sunspot.github.commits.http_client", boom)
    assert first_commit_date("nohttp") == date(2011, 6, 15)


def test_first_commit_date_uses_search_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/commits"
        assert request.url.params["q"] == "author:alice"
        assert request.url.params["sort"] == "author-date"
        assert request.url.params["order"] == "asc"
        body = {
            "items": [
                {"commit": {"author": {"date": "2012-04-21T08:30:00Z"}}},
            ],
        }
        return httpx.Response(200, json=body, headers={"X-RateLimit-Remaining": "30"})

    client = _client_with(httpx.MockTransport(handler))
    try:
        assert first_commit_date("alice", client=client) == date(2012, 4, 21)
    finally:
        client.close()


def test_first_commit_date_falls_back_to_account_created_at() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search/commits":
            return httpx.Response(
                200, json={"items": []},
                headers={"X-RateLimit-Remaining": "30"},
            )
        if request.url.path == "/users/bob":
            return httpx.Response(
                200, json={"created_at": "2010-09-01T00:00:00Z"},
                headers={"X-RateLimit-Remaining": "30"},
            )
        return httpx.Response(404)

    client = _client_with(httpx.MockTransport(handler))
    try:
        assert first_commit_date("bob", client=client) == date(2010, 9, 1)
    finally:
        client.close()


def test_first_commit_date_returns_none_when_both_fail(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = _client_with(httpx.MockTransport(handler))
    try:
        assert first_commit_date("ghost", client=client) is None
    finally:
        client.close()
    assert gh.first_commit_date.__doc__ is not None


def test_iter_commits_scopes_api_to_author_and_window(tmp_path, monkeypatch) -> None:
    seen_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/alice/project/commits"
        seen_params.update(dict(request.url.params))
        body = [
            {
                "sha": "abc123",
                "commit": {"author": {"date": "2024-01-15T12:30:00Z"}},
            }
        ]
        return httpx.Response(200, json=body, headers={"X-RateLimit-Remaining": "30"})

    monkeypatch.setenv("SUNSPOT_CACHE", str(tmp_path))
    client = _client_with(httpx.MockTransport(handler))
    try:
        rows = list(
            iter_commits(
                "alice",
                "alice/project",
                "main",
                since=date(2024, 1, 1),
                until=date(2024, 1, 31),
                client=client,
            )
        )
    finally:
        client.close()

    assert len(rows) == 1
    assert rows[0][0] == "abc123"
    assert seen_params["author"] == "alice"
    assert seen_params["sha"] == "main"
    assert seen_params["since"] == "2024-01-01T00:00:00Z"
    assert seen_params["until"] == "2024-01-31T23:59:59Z"
