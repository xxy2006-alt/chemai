"""Baidu OAuth token manager 测试。

覆盖：缓存命中、过期刷新、凭据缺失、响应无 access_token、HTTP 错误。
使用 asyncio.run() 驱动 async get_token()，通过 monkeypatch 打桩 httpx 与全局缓存。
"""
import asyncio
import time

import httpx
import pytest

import app.services.baidu_auth as ba


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self._status = status

    def raise_for_status(self):
        if self._status != 200:
            raise httpx.HTTPStatusError("err", request=None, response=self)
        return None

    def json(self):
        return self._data


class _FakeClient:
    """记录请求参数，返回预设响应。"""

    def __init__(self, response, on_post=None):
        self._response = response
        self.on_post = on_post
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, params=None, **kwargs):
        self.post_calls.append({"url": url, "params": params})
        if self.on_post:
            self.on_post(params)
        return self._response


@pytest.fixture
def reset_cache():
    ba._token = ""
    ba._expires_at = 0.0
    yield
    ba._token = ""
    ba._expires_at = 0.0


@pytest.fixture
def fake_client(monkeypatch):
    def _install(response, on_post=None):
        fake = _FakeClient(response, on_post=on_post)
        monkeypatch.setattr(ba.httpx, "AsyncClient", lambda *a, **k: fake)
        return fake

    return _install


@pytest.fixture
def set_credentials(monkeypatch):
    monkeypatch.setenv("BAIDU_OCR_API_KEY", "ak")
    monkeypatch.setenv("BAIDU_OCR_SECRET_KEY", "sk")


def _run(coro):
    return asyncio.run(coro)


def test_missing_credentials_raises(reset_cache, monkeypatch):
    monkeypatch.delenv("BAIDU_OCR_API_KEY", raising=False)
    monkeypatch.delenv("BAIDU_OCR_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="must be set"):
        _run(ba.get_token())


def test_credentials_uses_env(set_credentials, reset_cache, fake_client):
    seen = {}

    def on_post(params):
        seen.update(params)

    fc = fake_client(_FakeResponse({"access_token": "tok", "expires_in": 3600}), on_post=on_post)
    token = _run(ba.get_token())
    assert token == "tok"
    assert seen.get("client_id") == "ak"
    assert seen.get("client_secret") == "sk"
    assert seen.get("grant_type") == "client_credentials"
    # 请求走 BAIDU_TOKEN_URL
    assert fc.post_calls[0]["url"] == ba.BAIDU_TOKEN_URL


def test_refreshes_and_caches(set_credentials, reset_cache, fake_client):
    fc = fake_client(_FakeResponse({"access_token": "tok1", "expires_in": 3600}))
    assert _run(ba.get_token()) == "tok1"
    assert ba._token == "tok1"
    assert ba._expires_at > time.time()

    # 第二次调用：缓存命中，不再发 HTTP
    assert _run(ba.get_token()) == "tok1"
    assert len(fc.post_calls) == 1


def test_refresh_when_expired(set_credentials, reset_cache, fake_client):
    fc = fake_client(_FakeResponse({"access_token": "tok1", "expires_in": 3600}))
    _run(ba.get_token())

    # 缓存已存在但剩余时间不足 300s → 必须刷新
    ba._expires_at = time.time() + 100

    fc = fake_client(_FakeResponse({"access_token": "tok2", "expires_in": 3600}))
    assert _run(ba.get_token()) == "tok2"
    assert len(fc.post_calls) == 1


def test_expired_early_when_no_token(set_credentials, reset_cache, fake_client):
    # _token 为空、_expires_at 为 0 → 走刷新分支
    fc = fake_client(_FakeResponse({"access_token": "tok", "expires_in": 3600}))
    assert _run(ba.get_token()) == "tok"
    assert len(fc.post_calls) == 1


def test_missing_access_token_raises(set_credentials, reset_cache, fake_client):
    fc = fake_client(_FakeResponse({"error": "invalid_client"}))
    with pytest.raises(RuntimeError, match="missing access_token"):
        _run(ba.get_token())


def test_http_error_propagates(set_credentials, reset_cache, fake_client):
    fc = fake_client(_FakeResponse({"error": "bad"}, status=500))
    with pytest.raises(httpx.HTTPStatusError):
        _run(ba.get_token())


def test_default_expires_in(set_credentials, reset_cache, fake_client):
    # 响应未给 expires_in → 默认 2592000
    fc = fake_client(_FakeResponse({"access_token": "tok"}))
    _run(ba.get_token())
    assert abs((ba._expires_at - time.time()) - 2592000) < 60
