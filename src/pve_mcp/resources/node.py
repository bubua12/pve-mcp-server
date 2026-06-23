"""节点相关 MCP Resources"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from pve_mcp.client.base import PVEClient


def register_node_resources(mcp: FastMCP) -> None:
    """注册节点相关资源到 MCP Server。"""

    @mcp.resource("pve://nodes")
    async def get_nodes() -> str:
        """获取所有 PVE 节点列表及其基本状态。"""
        client: PVEClient = mcp.state["pve_client"]
        try:
            nodes = await client.get("/nodes")
            result = []
            for n in nodes:
                result.append({
                    "node": n.get("node"),
                    "status": n.get("status"),
                    "cpu": n.get("cpu", 0),
                    "maxcpu": n.get("maxcpu", 0),
                    "mem": n.get("mem", 0),
                    "maxmem": n.get("maxmem", 0),
                    "uptime": n.get("uptime", 0),
                })
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取节点资源失败: {e}")
            return json.dumps({"error": str(e)})

    @mcp.resource("pve://nodes/{node}/status")
    async def get_node_status(node: str) -> str:
        """获取指定节点的详细状态数据。"""
        client: PVEClient = mcp.state["pve_client"]
        try:
            data = await client.get(f"/nodes/{node}/status")
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"获取节点 {node} 状态资源失败: {e}")
            return json.dumps({"error": str(e)})

    @mcp.resource("pve://nodes/{node}/storage")
    async def get_node_storage(node: str) -> str:
        """获取指定节点的存储池列表。"""
        client: PVEClient = mcp.state["pve_client"]
        try:
            data = await client.get(f"/nodes/{node}/storage")
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"获取节点 {node} 存储资源失败: {e}")
            return json.dumps({"error": str(e)})
