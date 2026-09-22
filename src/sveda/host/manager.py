from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import httpx

from sveda.client import SvedaClient
from sveda.exceptions import APIError, AuthenticationError, TransportError
from sveda.host.constants import DEFAULT_MCP_ABILITY, DEFAULT_MCP_PATH
from sveda.host.token_store import McpTokenStore


def _trim_slash(value: str) -> str:
    return str(value or "").rstrip("/")


def _invoke_tools_callback(callback: Callable[..., list[Any]], user: Any) -> list[Any]:
    if user is None:
        return callback()
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        try:
            return callback(user)
        except TypeError:
            return callback()

    accepts_user = False
    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            accepts_user = True
            break
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            accepts_user = True
            break

    if accepts_user:
        return callback(user)
    return callback()


class HostManager:
    def __init__(
        self,
        *,
        base_url: str = "",
        host_api_key: str = "",
        timeout: float = 30.0,
        connect_timeout: float = 5.0,
        mcp_path: str = DEFAULT_MCP_PATH,
        mcp_url: str = "",
        server_name: str = "Host Application",
        server_version: str = "0.1.0",
        instructions: str = "",
        mcp_ability: str = DEFAULT_MCP_ABILITY,
        token_ttl_seconds: int = 3600,
        visitor_prefix: str = "host",
        token_store: McpTokenStore | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = _trim_slash(base_url)
        self.host_api_key = str(host_api_key).strip()
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.mcp_path = str(mcp_path or DEFAULT_MCP_PATH)
        self.mcp_url = _trim_slash(mcp_url)
        self.server_name = server_name
        self.server_version = server_version
        self.instructions = instructions
        self.mcp_ability = mcp_ability
        self.token_ttl_seconds = max(60, int(token_ttl_seconds))
        self.visitor_prefix = visitor_prefix
        self.token_store = token_store or McpTokenStore()
        self._http_client = http_client

        self._authorize_using: Callable[[Any], bool] | None = None
        self._after_authenticate_using: Callable[[Any], None] | None = None
        self._resolve_tools_using: Callable[..., list[Any]] | None = None
        self._policy_using: Callable[[Any], Any] | None = None
        self._visitor_id_using: Callable[[Any], str] | None = None
        self._mint_token_using: Callable[[Any], str] | None = None
        self._verify_bearer_token_using: Callable[[str], Any] | None = None

    def authorize_using(self, callback: Callable[[Any], bool]) -> HostManager:
        self._authorize_using = callback
        return self

    def after_authenticate_using(self, callback: Callable[[Any], None]) -> HostManager:
        self._after_authenticate_using = callback
        return self

    def resolve_tools_using(self, callback: Callable[..., list[Any]]) -> HostManager:
        self._resolve_tools_using = callback
        return self

    def policy_using(self, callback: Callable[[Any], Any]) -> HostManager:
        self._policy_using = callback
        return self

    def visitor_id_using(self, callback: Callable[[Any], str]) -> HostManager:
        self._visitor_id_using = callback
        return self

    def mint_token_using(self, callback: Callable[[Any], str]) -> HostManager:
        self._mint_token_using = callback
        return self

    def verify_bearer_token_using(self, callback: Callable[[str], Any]) -> HostManager:
        self._verify_bearer_token_using = callback
        return self

    def authorize(self, user: Any) -> bool:
        if self._authorize_using is None:
            return True
        return bool(self._authorize_using(user))

    def after_authenticate(self, user: Any) -> None:
        if self._after_authenticate_using is not None:
            self._after_authenticate_using(user)

    def describe(self, user: Any = None) -> dict[str, Any]:
        from sveda.host.manifest import build_host_manifest

        return build_host_manifest(self, user)

    def resolve_tools(self, user: Any = None) -> list[Any]:
        if self._resolve_tools_using is None:
            return []
        tools = _invoke_tools_callback(self._resolve_tools_using, user)
        if not isinstance(tools, list):
            return []
        return [
            tool
            for tool in tools
            if tool is not None
            and (
                callable(getattr(tool, "name", None))
                or isinstance(getattr(tool, "name", None), str)
            )
        ]

    def policy_for(self, user: Any) -> str | None:
        if self._policy_using is None:
            return None
        value = self._policy_using(user)
        if value is None:
            return None
        policy = str(value).strip()
        return policy or None

    def visitor_id(self, user: Any) -> str:
        if self._visitor_id_using is not None:
            return str(self._visitor_id_using(user))
        user_id = user.get("id") if isinstance(user, dict) else user
        return f"{self.visitor_prefix}-{user_id}"

    def mint_mcp_token(self, user: Any) -> str:
        if self._mint_token_using is not None:
            return str(self._mint_token_using(user))
        return self.default_mint_mcp_token(user)

    def default_mint_mcp_token(self, user: Any) -> str:
        user_id = user.get("id") if isinstance(user, dict) else "anonymous"
        self.token_store.revoke_for_user(str(user_id))
        return self.token_store.mint(
            str(user_id),
            ability=self.mcp_ability,
            ttl_seconds=self.token_ttl_seconds,
        )

    def mcp_public_url(self, request_origin: str | None = None) -> str:
        if self.mcp_url:
            return self.mcp_url
        origin = _trim_slash(request_origin or "")
        path = self.mcp_path if self.mcp_path.startswith("/") else f"/{self.mcp_path}"
        if not origin:
            return path
        return f"{origin}{path}"

    def is_configured(self) -> bool:
        return self.base_url != "" and self.host_api_key != ""

    def host_client(self) -> SvedaClient:
        return SvedaClient(
            self.base_url,
            host_api_key=self.host_api_key,
            timeout=self.timeout,
            connect_timeout=self.connect_timeout,
            http_client=self._http_client,
        )

    def start_session(
        self,
        user: Any,
        *,
        request_origin: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise APIError("Sveda host is not configured.", status_code=404)

        mcp_token = self.mint_mcp_token(user)
        visitor_id = self.visitor_id(user)
        host_mcp_url = self.mcp_public_url(request_origin)

        try:
            with self.host_client() as client:
                created = client.embed.create_token(
                    visitor_id=visitor_id,
                    host_mcp_url=host_mcp_url,
                    host_mcp_token=mcp_token,
                    policy=self.policy_for(user),
                )
        except (AuthenticationError, TransportError, APIError) as exc:
            raise APIError(
                str(exc),
                status_code=502,
            ) from exc

        if created.token == "":
            raise APIError("Sidecar returned an empty embed token.", status_code=502)

        return {
            "origin": self.base_url,
            "token": created.token,
            "expires_in": created.expires_in,
            "appearance": created.appearance,
        }

    def authenticate_bearer_token(self, plain_token: str) -> dict[str, Any] | None:
        if not str(plain_token or "").strip():
            return None

        if self._verify_bearer_token_using is not None:
            verified = self._verify_bearer_token_using(plain_token)
            if verified is None:
                return None
            if isinstance(verified, dict) and "user" in verified:
                return verified
            return {"user": verified}

        record = self.token_store.verify(plain_token, self.mcp_ability)
        if record is None:
            return None
        return {"user": {"id": record["user_id"]}}
