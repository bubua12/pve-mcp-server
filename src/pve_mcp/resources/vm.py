"""虚拟机相关 MCP Resources"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from loguru import logger
from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from pve_mcp.client.base import PVEClient


def _get_pve_client(ctx: Context):
    """从 Context 中获取 lifespan 注入的 PVEClient。"""
    return ctx.request_context.lifespan_context.pve_client


def register_vm_resources(mcp: FastMCP) -> None:
    """注册虚拟机相关资源到 MCP Server。"""

    @mcp.resource("pve://nodes/{node}/qemu")
    async def get_vms(ctx: Context, node: str) -> str:
        """获取指定节点上所有 QEMU 虚拟机列表。"""
        client: PVEClient = _get_pve_client(ctx)
        try:
            data = await client.get(f"/nodes/{node}/qemu")
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"获取 VM 列表资源失败: {e}")
            return json.dumps({"error": str(e)})

    @mcp.resource("pve://nodes/{node}/qemu/{vmid}")
    async def get_vm(ctx: Context, node: str, vmid: str) -> str:
        """获取指定虚拟机的配置和当前状态。"""
        client: PVEClient = _get_pve_client(ctx)
        try:
            import asyncio
            config_data, status_data = await asyncio.gather(
                client.get(f"/nodes/{node}/qemu/{vmid}/config"),
                client.get(f"/nodes/{node}/qemu/{vmid}/status/current"),
            )
            return json.dumps(
                {"config": config_data, "status": status_data},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        except Exception as e:
            logger.error(f"获取 VM {vmid} 资源失败: {e}")
            return json.dumps({"error": str(e)})
