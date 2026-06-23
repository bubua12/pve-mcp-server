"""PVE REST API 异步客户端"""

from __future__ import annotations

import httpx
from loguru import logger

from pve_mcp.config import PVEConfig
from pve_mcp.client.exceptions import (
    PVEAPIError,
    PVEAuthenticationError,
    PVEConnectionError,
)


class PVEClient:
    """Proxmox VE REST API 异步客户端。

    仅处理 HTTP 通信，不做业务逻辑。
    所有方法返回原始 JSON data 字段内容。
    """

    def __init__(self, config: PVEConfig) -> None:
        self._config = config
        self._base_url = f"{config.host.rstrip('/')}/api2/json"
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """懒初始化 httpx 客户端，复用连接池。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": (
                        f"PVEAPIToken={self._config.token_id}"
                        f"={self._config.token_secret}"
                    ),
                },
                verify=self._config.verify_ssl,
                timeout=httpx.Timeout(self._config.timeout),
            )
        return self._client

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        """GET 请求，返回 data 字段。"""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: dict | None = None) -> dict | list:
        """POST 请求，返回 data 字段。"""
        return await self._request("POST", path, data=data)

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict | list:
        """发送请求，统一错误处理。"""
        client = await self._ensure_client()
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.ConnectError as e:
            raise PVEConnectionError(
                f"无法连接到 PVE: {self._config.host}，请检查地址和网络"
            ) from e
        except httpx.TimeoutException as e:
            raise PVEConnectionError(
                f"PVE 请求超时（{self._config.timeout}s）"
            ) from e

        if response.status_code == 401:
            raise PVEAuthenticationError(
                "认证失败，请检查 PVE_TOKEN_ID 和 PVE_TOKEN_SECRET"
            )
        if response.status_code == 403:
            raise PVEAuthenticationError(
                "权限不足，请检查 API Token 的权限分配（需要 Sys.Audit, VM.Audit）"
            )
        if response.status_code >= 400:
            raise PVEAPIError(
                f"PVE API 错误 [{response.status_code}]: {response.text}"
            )

        body = response.json()
        return body.get("data", body)

    async def detect_node(self) -> str:
        """自动检测节点名称（单机模式）。"""
        nodes = await self.get("/nodes")
        if not nodes:
            raise PVEAPIError("PVE 未发现任何节点")
        node_name = nodes[0]["node"]
        logger.debug(f"自动检测到节点: {node_name}")
        return node_name

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("PVE HTTP 客户端已关闭")
