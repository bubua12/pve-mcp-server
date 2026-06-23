"""节点相关 MCP Tools"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from loguru import logger
from mcp.server.fastmcp import Context

from pve_mcp.client.exceptions import PVEError
from pve_mcp.client.models import NodeStatus, StorageInfo
from pve_mcp.utils.formatters import (
    format_node_status,
    format_node_list,
    format_resource_allocation,
    format_storage_list,
    format_connection_error,
    format_auth_error,
    format_error,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from pve_mcp.client.base import PVEClient
    from pve_mcp.server import AppState


def _handle_error(func):
    """装饰器：捕获异常，返回友好的错误文本。"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except PVEError as e:
            logger.error(f"工具 {func.__name__} 执行失败: {e}")
            from pve_mcp.client.exceptions import PVEConnectionError, PVEAuthenticationError

            if isinstance(e, PVEConnectionError):
                return format_error("连接失败", str(e))
            if isinstance(e, PVEAuthenticationError):
                return format_auth_error(str(e))
            return format_error("执行出错", str(e))
        except Exception as e:
            logger.exception(f"工具 {func.__name__} 未预期异常")
            return format_error("未知错误", f"{type(e).__name__}: {e}")

    return wrapper


def _get_app_state(ctx: Context) -> AppState:
    """从 Context 中获取 lifespan 注入的 AppState。"""
    return ctx.request_context.lifespan_context


async def _resolve_node(client: PVEClient, config, node: str | None) -> str:
    """解析节点名称：优先使用参数，其次配置，最后自动检测。"""
    if node:
        return node
    if config.node_name:
        return config.node_name
    return await client.detect_node()


def register_node_tools(mcp: FastMCP) -> None:
    """注册节点相关工具到 MCP Server。"""

    @mcp.tool()
    @_handle_error
    async def get_node_status(ctx: Context, node: str | None = None) -> str:
        """获取 PVE 节点的实时状态，包括 CPU、内存、负载、磁盘使用等信息。

        返回节点的健康评估，标记各项指标是否处于正常/警告/危险状态。

        Args:
            node: 节点名称（可选，单机模式下自动检测）
        """
        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        # /nodes/{node}/status 不含 maxcpu/maxmem，需从 /nodes 补充
        nodes_data, status_data, version_data = await __import__("asyncio").gather(
            client.get("/nodes"),
            client.get(f"/nodes/{node}/status"),
            client.get("/version"),
        )

        def _int(v, default=0):
            return int(v) if v is not None else default

        def _float(v, default=0.0):
            return float(v) if v is not None else default

        # 从节点列表取硬件信息
        maxcpu = 0
        maxmem = 0
        node_status_str = status_data.get("status", "unknown")
        for n in nodes_data:
            if n.get("node") == node:
                maxcpu = _int(n.get("maxcpu", 0))
                maxmem = _int(n.get("maxmem", 0))
                if node_status_str == "unknown":
                    node_status_str = n.get("status", "unknown")
                break

        rootfs = status_data.get("rootfs", {}) or {}
        # PVE /nodes/{node}/status 返回的 mem/memory 可能是 int 也可能是 dict
        mem_raw = status_data.get("mem", status_data.get("memory", 0))
        if isinstance(mem_raw, dict):
            mem_used = _int(mem_raw.get("used", 0))
        else:
            mem_used = _int(mem_raw)

        status = NodeStatus(
            node=node,
            status=node_status_str,
            uptime=_int(status_data.get("uptime", 0)),
            cpu=_float(status_data.get("cpu", 0)),
            maxcpu=maxcpu,
            mem=mem_used,
            maxmem=maxmem,
            disk=_int(rootfs.get("used", 0)),
            maxdisk=_int(rootfs.get("total", 0)),
            loadavg=[float(x) for x in status_data.get("loadavg", [])],
            kversion=str(status_data.get("kversion", "")),
            pve_version=str(version_data.get("version", "")),
        )

        return format_node_status(status)

    @mcp.tool()
    @_handle_error
    async def list_nodes(ctx: Context) -> str:
        """列出 PVE 集群中所有节点的状态概览。

        返回每个节点的名称、状态、CPU 和内存使用率、运行时间。
        """
        client: PVEClient = _get_app_state(ctx).pve_client
        nodes = await client.get("/nodes")
        return format_node_list(nodes)

    @mcp.tool()
    @_handle_error
    async def list_storage(ctx: Context, node: str | None = None) -> str:
        """列出 PVE 所有存储池及其容量使用情况。

        返回每个存储池的类型、总容量、已用空间、使用率、支持的内容类型。

        Args:
            node: 节点名称（可选）
        """
        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        data = await client.get(f"/nodes/{node}/storage")
        storages = [
            StorageInfo(
                storage=s.get("storage", ""),
                type=s.get("type", ""),
                total=int(s.get("total", 0)),
                used=int(s.get("used", 0)),
                available=int(s.get("avail", 0)),
                content=s.get("content", ""),
                enabled=s.get("enabled", True),
                active=s.get("active", True),
            )
            for s in data
        ]

        return format_storage_list(storages)

    @mcp.tool()
    @_handle_error
    async def analyze_resource_allocation(ctx: Context, node: str | None = None) -> str:
        """分析 PVE 的资源分配情况，检测超分配风险。

        对比物理资源与已分配资源，计算 CPU 和内存的超分配率，给出容量建议。
        适合判断是否还能创建新 VM。
        """
        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        # 同时获取节点信息（含物理资源）和 VM 列表
        nodes, qemu, lxc = await __import__("asyncio").gather(
            client.get("/nodes"),
            client.get(f"/nodes/{node}/qemu"),
            client.get(f"/nodes/{node}/lxc"),
        )

        # 从节点列表中匹配当前节点，获取物理资源（更可靠）
        physical_cpu = 0
        physical_mem = 0
        for n in nodes:
            if n.get("node") == node:
                physical_cpu = int(n.get("maxcpu", 0))
                physical_mem = int(n.get("maxmem", 0))
                break

        # 如果节点列表里没取到，回退到 status 接口
        if not physical_cpu or not physical_mem:
            status_data = await client.get(f"/nodes/{node}/status")
            if not physical_cpu:
                physical_cpu = int(status_data.get("maxcpu", 0))
            if not physical_mem:
                physical_mem = int(status_data.get("maxmem", 0))

        allocated_vcpu = 0
        allocated_mem = 0
        running_vcpu = 0
        running_vms = 0
        stopped_vms = 0

        for vm in qemu:
            # /nodes/{node}/qemu 列表返回 cpus，不是 maxcpu
            vm_vcpu = int(vm.get("cpus", vm.get("maxcpu", 0)))
            vm_mem = int(vm.get("maxmem", 0))
            allocated_vcpu += vm_vcpu
            allocated_mem += vm_mem
            if vm.get("status") == "running":
                running_vms += 1
                running_vcpu += vm_vcpu
            else:
                stopped_vms += 1

        return format_resource_allocation(
            physical_cpu=physical_cpu,
            physical_mem=physical_mem,
            allocated_vcpu=allocated_vcpu,
            allocated_mem=allocated_mem,
            running_vms=running_vms,
            stopped_vms=stopped_vms,
            running_vcpu=running_vcpu,
        )
