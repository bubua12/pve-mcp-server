"""MCP Server 主入口"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from loguru import logger
from mcp.server.fastmcp import FastMCP

from pve_mcp.config import PVEConfig
from pve_mcp.client.base import PVEClient
from pve_mcp.tools.node import register_node_tools
from pve_mcp.tools.vm import register_vm_tools
from pve_mcp.resources.node import register_node_resources
from pve_mcp.resources.vm import register_vm_resources
from pve_mcp.prompts.diagnostics import register_prompts


@dataclass
class AppState:
    """MCP Server 运行时共享状态，通过 lifespan 注入到 mcp.state。"""

    pve_client: PVEClient
    config: PVEConfig


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppState]:
    """管理 Server 生命周期：初始化 PVE 连接和清理资源。"""
    config = PVEConfig()
    client = PVEClient(config)

    logger.info(f"正在连接 PVE: {config.host}")

    try:
        node = config.node_name or await client.detect_node()
        logger.info(f"连接成功，节点: {node}")
    except Exception as e:
        logger.warning(f"PVE 预检失败（工具调用时将重试）: {e}")

    yield AppState(pve_client=client, config=config)

    await client.close()
    logger.info("PVE 连接已关闭")


def create_server() -> FastMCP:
    """创建并配置 MCP Server。"""
    mcp = FastMCP(
        name="pve-monitor",
        version="1.0.0",
        lifespan=app_lifespan,
        instructions=(
            "这是一个 PVE (Proxmox VE) 监控 MCP 服务。"
            "你可以查询 PVE 节点状态、虚拟机列表、资源分配情况、历史趋势等。"
            "所有工具返回人类可读的 Markdown 文本。"
        ),
    )

    # 将 mcp 实例注册到 tools/resources 时，它们通过 mcp.state 访问 PVE 客户端
    register_node_tools(mcp)
    register_vm_tools(mcp)
    register_node_resources(mcp)
    register_vm_resources(mcp)
    register_prompts(mcp)

    return mcp


def main() -> None:
    """主入口：配置日志并启动 MCP Server。"""
    logger.remove()

    # 从环境变量读取日志级别（默认 INFO）
    import os

    log_level = os.environ.get("PVE_LOG_LEVEL", "INFO").upper()
    logger.add(sys.stderr, level=log_level, format="{time:HH:mm:ss} | {level:<7} | {message}")

    logger.info("PVE MCP Server 启动中...")
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
