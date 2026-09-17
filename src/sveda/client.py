from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import quote

import httpx

from sveda.exceptions import (
    APIError,
    AuthenticationError,
    TransportError,
    UnserializableResponse,
)
from sveda.streaming import StreamEvent, iter_sse_lines
from sveda.types import EmbedToken, Message

ACCEPT_JSON = "application/json"
ACCEPT_STREAM = "application/vnd.sveda.stream+json"


class SvedaClient:
    def __init__(
        self,
        base_url: str,
        *,
        host_api_key: str | None = None,
        embed_token: str | None = None,
        timeout: float = 30.0,
        connect_timeout: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._host_api_key = host_api_key or None
        self._embed_token = embed_token or None
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
        )
        self.embed = EmbedResource(self)
        self.chat = ChatResource(self)
        self.histories = HistoriesResource(self)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> SvedaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._host_api_key is not None:
            headers["Authorization"] = f"Bearer {self._host_api_key}"
        if self._embed_token is not None:
            headers["X-Sveda-Embed-Token"] = self._embed_token
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {**self._auth_headers(), "Accept": ACCEPT_JSON}
        json_payload: Mapping[str, Any] | None = dict(payload) if payload else None
        if method.upper() in {"GET", "HEAD", "DELETE"}:
            json_payload = None
        elif json_payload is None:
            json_payload = {}
        try:
            response = self._http.request(
                method,
                self._url(path),
                json=json_payload,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise TransportError(str(exc)) from exc
        return self._decode_json(response)

    def request_stream(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Iterator[StreamEvent]:
        headers = {
            **self._auth_headers(),
            "Accept": ACCEPT_STREAM,
            "Content-Type": "application/json",
        }
        try:
            with self._http.stream(
                method,
                self._url(path),
                json=dict(payload or {}),
                headers=headers,
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    response.read()
                    self._raise_for_status(response)
                yield from iter_sse_lines(response.iter_lines())
        except httpx.RequestError as exc:
            raise TransportError(str(exc)) from exc

    def _decode_json(self, response: httpx.Response) -> dict[str, Any]:
        self._raise_for_status(response)
        if response.content == b"":
            return {}
        try:
            decoded = response.json()
        except ValueError as exc:
            raise UnserializableResponse(
                "Unable to decode Sveda API response as JSON."
            ) from exc
        if not isinstance(decoded, dict):
            raise UnserializableResponse("Unable to decode Sveda API response as JSON.")
        return decoded

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status in {401, 403}:
            raise AuthenticationError(
                f"Sveda API authentication failed with status {status}"
            )
        if status < 200 or status >= 300:
            data: Any = None
            try:
                data = response.json()
            except ValueError:
                data = None
            message = f"Sveda API request failed with status {status}"
            if isinstance(data, dict) and isinstance(data.get("message"), str):
                message = data["message"]
            raise APIError(
                message,
                status_code=status,
                response=data if isinstance(data, dict) else None,
            )


class EmbedResource:
    def __init__(self, client: SvedaClient) -> None:
        self._client = client

    def create_token(
        self,
        visitor_id: str | None = None,
        *,
        host_mcp_url: str | None = None,
        host_mcp_token: str | None = None,
    ) -> EmbedToken:
        payload: dict[str, Any] = {}
        if visitor_id:
            payload["visitor_id"] = visitor_id
        if host_mcp_url and host_mcp_token:
            payload["host_mcp_url"] = host_mcp_url
            payload["host_mcp_token"] = host_mcp_token
        return EmbedToken.from_dict(
            self._client.request_json("POST", "/sveda/embed/token", payload)
        )

    def config(self) -> dict[str, Any]:
        return self._client.request_json("GET", "/sveda/embed/config")


class ChatResource:
    def __init__(self, client: SvedaClient) -> None:
        self._client = client

    def create(
        self,
        messages: list[dict[str, Any]],
        *,
        chat_id: str | None = None,
        **extra: Any,
    ) -> Message:
        return Message.from_dict(
            self._client.request_json(
                "POST",
                "/sveda/message",
                _chat_payload(messages, chat_id, extra),
            )
        )

    def create_streamed(
        self,
        messages: list[dict[str, Any]],
        *,
        chat_id: str | None = None,
        **extra: Any,
    ) -> Iterator[StreamEvent]:
        return self._client.request_stream(
            "POST",
            "/sveda/stream",
            _chat_payload(messages, chat_id, extra),
        )


class HistoriesResource:
    def __init__(self, client: SvedaClient) -> None:
        self._client = client

    def list(self) -> dict[str, Any]:
        return self._client.request_json("GET", "/sveda/chat-histories")

    def get(self, chat_id: str) -> dict[str, Any]:
        return self._client.request_json("GET", _history_path(chat_id))

    def rename(self, chat_id: str, title: str) -> dict[str, Any]:
        return self._client.request_json(
            "PATCH",
            _history_path(chat_id),
            {"title": title},
        )

    def delete(self, chat_id: str) -> dict[str, Any]:
        return self._client.request_json("DELETE", _history_path(chat_id))


def _history_path(chat_id: str) -> str:
    return "/sveda/chat-histories/" + quote(chat_id, safe="")


def _chat_payload(
    messages: list[dict[str, Any]],
    chat_id: str | None,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(extra)
    payload["messages"] = messages
    if "client_tools" in payload:
        payload["clientTools"] = payload.pop("client_tools")
    if "chat_id" in payload:
        payload["chatId"] = payload.pop("chat_id")
    if chat_id is not None:
        payload["chatId"] = chat_id
    return payload
