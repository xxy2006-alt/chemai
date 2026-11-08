"""DeepSeek Provider — 供 tools.py 中需要自己调 LLM 的 skill 使用"""
import os
import asyncio
import random
from dataclasses import dataclass, field
from typing import AsyncIterator
from dotenv import load_dotenv

load_dotenv()

# ── LLM 请求级重试策略（2026-08，DSH llm-retry 同款）──
# 只重试可重试错误（限流/服务端/超时/传输），4xx 语义错误立即抛出
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
_RETRY_MAX = 2          # 最多重试 2 次（共 3 次尝试）
_RETRY_BASE_MS = 500    # 首次退避
_RETRY_MAX_MS = 10_000  # 退避封顶
_RETRY_JITTER = 0.1     # ±10% 抖动


def _is_retryable(status: int | None, exc: BaseException | None = None) -> bool:
    if status is not None and status in _RETRYABLE_STATUS:
        return True
    if exc is not None:
        import httpx
        return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))
    return False


def _retry_delay(attempt: int) -> float:
    """attempt=1 → 500ms；指数退避封顶 10s；±10% 抖动（秒）。"""
    exp = min(_RETRY_BASE_MS * (2 ** (attempt - 1)), _RETRY_MAX_MS)
    jitter = 1 - _RETRY_JITTER + 2 * _RETRY_JITTER * random.random()
    return (exp * jitter) / 1000.0


@dataclass
class ChatResult:
    content: str
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""


class DeepSeekProvider:
    def __init__(self, model: str = "deepseek-chat"):
        import httpx

        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/beta"
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None,
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(1, _RETRY_MAX + 2):  # 1..3
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    return ChatResult(
                        content=choice["message"].get("content", ""),
                        tool_calls=choice["message"].get("tool_calls", []),
                        usage=data.get("usage", {}),
                        model=data.get("model", ""),
                    )
                if not _is_retryable(resp.status_code):
                    raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")
                last_err = Exception(f"API error {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                if not _is_retryable(None, e):
                    raise
                last_err = e
            if attempt <= _RETRY_MAX:
                await asyncio.sleep(_retry_delay(attempt))
        # 重试耗尽：显式抛错（不再静默返回空结果——空结果会被误当成成功）
        raise last_err  # noqa: BLE001

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        # 流式重试只覆盖"首块之前"的失败（建连/HTTP 状态错误）；一旦开始出块，
        # 中途断流直接抛出（重试会产生重复前缀，交给上层处理）
        attempt = 1
        while True:
            started = False
            try:
                async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
                    if resp.status_code != 200:
                        if _is_retryable(resp.status_code) and attempt <= _RETRY_MAX:
                            await asyncio.sleep(_retry_delay(attempt))
                            attempt += 1
                            continue
                        raise Exception(f"API error {resp.status_code}")
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            started = True
                            yield line[6:]
                return
            except Exception as e:
                if started or attempt > _RETRY_MAX or not _is_retryable(None, e):
                    raise
                await asyncio.sleep(_retry_delay(attempt))
                attempt += 1

    async def close(self):
        await self._client.aclose()

    @property
    def model_name(self) -> str:
        return f"deepseek/{self.model}"


# Module-level singleton for the intent classifier (shared connection pool)
classifier_provider: DeepSeekProvider | None = None


def get_classifier_provider() -> DeepSeekProvider:
    """Return or create the shared classifier provider singleton."""
    global classifier_provider
    if classifier_provider is None:
        classifier_provider = DeepSeekProvider()
    return classifier_provider
