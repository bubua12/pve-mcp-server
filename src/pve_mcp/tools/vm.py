"""虚拟机相关 MCP Tools"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING

from loguru import logger
from mcp.server.fastmcp import Context

from pve_mcp.client.exceptions import PVEError, PVEAuthenticationError, PVEConnectionError
from pve_mcp.client.models import VMInfo, VMDetail, DiskInfo, NICInfo, RRDSample
from pve_mcp.utils.formatters import (
    format_vm_list,
    format_vm_detail,
    format_top_vms,
    format_rrd_data,
    format_auth_error,
    format_error,
)
from pve_mcp.utils.validators import validate_vmid, validate_sort_by, validate_rrd_timeframe

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
            if isinstance(e, PVEConnectionError):
                return format_error("连接失败", str(e))
            if isinstance(e, PVEAuthenticationError):
                return format_auth_error(str(e))
            return format_error("执行出错", str(e))
        except Exception as e:
            logger.exception(f"工具 {func.__name__} 未预期异常")
            return format_error("未知错误", f"{type(e).__name__}: {e}")

    return wrapper


async def _resolve_node(client: PVEClient, config, node: str | None) -> str:
    if node:
        return node
    if config.node_name:
        return config.node_name
    return await client.detect_node()


def _get_app_state(ctx: Context) -> AppState:
    """从 Context 中获取 lifespan 注入的 AppState。"""
    return ctx.request_context.lifespan_context


def _parse_vm_info(vm: dict, node: str = "") -> VMInfo:
    """从 API 原始数据构造 VMInfo（PVE API 数值字段可能是字符串，需强制转换）。"""
    return VMInfo(
        vmid=int(vm["vmid"]),
        name=vm.get("name", f"vm-{vm['vmid']}"),
        status=vm.get("status", "unknown"),
        cpu=float(vm.get("cpu", 0)),
        maxcpu=int(vm.get("maxcpu", 1)),
        mem=int(vm.get("mem", 0)),
        maxmem=int(vm.get("maxmem", 0)),
        disk=int(vm.get("disk", 0)),
        maxdisk=int(vm.get("maxdisk", 0)),
        uptime=int(vm.get("uptime", 0)),
        node=node,
    )


def register_vm_tools(mcp: FastMCP) -> None:
    """注册虚拟机相关工具到 MCP Server。"""

    @mcp.tool()
    @_handle_error
    async def list_vms(ctx: Context, node: str | None = None) -> str:
        """列出 PVE 上所有 QEMU 虚拟机及其运行状态。

        返回每台 VM 的 ID、名称、运行状态、CPU/内存/磁盘使用情况。

        Args:
            node: 节点名称（可选，单机模式下自动检测）
        """
        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        vms_data = await client.get(f"/nodes/{node}/qemu")
        vms = [_parse_vm_info(vm, node) for vm in vms_data]

        return format_vm_list(node, vms)

    @mcp.tool()
    @_handle_error
    async def get_vm_detail(ctx: Context, vmid: int, node: str | None = None) -> str:
        """获取单台虚拟机的详细配置与实时状态。

        返回 VM 的 CPU/内存/磁盘/网络配置、快照信息、实时资源使用等。

        Args:
            vmid: 虚拟机 ID（如 100, 101）
            node: 节点名称（可选）
        """
        validate_vmid(vmid)

        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        # 并行获取配置、状态、快照
        config_data, status_data = await asyncio.gather(
            client.get(f"/nodes/{node}/qemu/{vmid}/config"),
            client.get(f"/nodes/{node}/qemu/{vmid}/status/current"),
        )

        # 快照单独获取，失败不影响主流程
        snap_count = 0
        try:
            snapshots = await client.get(f"/nodes/{node}/qemu/{vmid}/snapshot")
            snap_count = len(snapshots) if snapshots else 0
        except Exception:
            pass

        # 解析磁盘
        disks = []
        for key, val in config_data.items():
            if key.startswith(("scsi", "virtio", "ide", "sata")):
                parts = str(val).split(",")
                storage_info = parts[0] if parts else ""
                size = 0
                fmt = ""
                for part in parts:
                    part = part.strip()
                    if part.startswith("size="):
                        size_str = part[5:]
                        size = _parse_size(size_str)
                    elif "=" not in part and part in ("raw", "qcow2", "vmdk"):
                        fmt = part
                storage_name = storage_info.split(":")[0] if ":" in storage_info else ""
                disks.append(DiskInfo(device=key, storage=storage_name, size=size, format=fmt))

        # 解析网卡
        nics = []
        for key, val in config_data.items():
            if key.startswith("net"):
                model = ""
                bridge = ""
                mac = ""
                for part in str(val).split(","):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        if k == "bridge":
                            bridge = v
                    else:
                        # 第一部分通常是 model=MAC
                        if part:
                            model = part.split("=")[0] if "=" in part else part
                nics.append(NICInfo(device=key, model=model, bridge=bridge, mac=mac))

        detail = VMDetail(
            vmid=vmid,
            name=config_data.get("name", f"vm-{vmid}"),
            status=status_data.get("status", "unknown"),
            uptime=status_data.get("uptime", 0),
            cpu_cores=config_data.get("cores", 1),
            cpu_type=config_data.get("cpu", "host"),
            memory=int(config_data.get("memory", 512)) * 1024 * 1024,  # MB → bytes
            disks=disks,
            nics=nics,
            cpu_usage=status_data.get("cpu", 0),
            mem_used=status_data.get("mem", 0),
            snapshot_count=snap_count,
            description=config_data.get("description", ""),
        )

        # 构造简要状态用于格式化（PVE API 返回的数值字段可能是字符串，需强制转换）
        def _int(v, default=0):
            return int(v) if v is not None else default

        def _float(v, default=0.0):
            return float(v) if v is not None else default

        vm_status = VMInfo(
            vmid=vmid,
            name=detail.name,
            status=status_data.get("status", "unknown"),
            cpu=_float(status_data.get("cpu", 0)),
            maxcpu=_int(status_data.get("cpus", config_data.get("cores", 1)), 1),
            mem=_int(status_data.get("mem", 0)),
            maxmem=_int(status_data.get("maxmem", detail.memory)),
            disk=_int(status_data.get("disk", 0)),
            maxdisk=_int(status_data.get("maxdisk", 0)),
            uptime=_int(status_data.get("uptime", 0)),
        )

        return format_vm_detail(node, detail, vm_status)

    @mcp.tool()
    @_handle_error
    async def get_top_vms(
        ctx: Context,
        sort_by: str = "cpu",
        limit: int = 5,
        node: str | None = None,
    ) -> str:
        """获取资源消耗排名前 N 的虚拟机。

        适合快速定位"哪台 VM 最吃资源"。

        Args:
            sort_by: 排序依据，"cpu" 或 "memory"
            limit: 返回数量，默认 5
            node: 节点名称（可选）
        """
        validate_sort_by(sort_by)

        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        vms_data = await client.get(f"/nodes/{node}/qemu")

        # 只看运行中的 VM
        running = [vm for vm in vms_data if vm.get("status") == "running"]

        # 排序
        if sort_by == "cpu":
            running.sort(
                key=lambda x: (x.get("cpu", 0) / x["maxcpu"]) if x.get("maxcpu") else 0,
                reverse=True,
            )
        else:
            running.sort(
                key=lambda x: (x.get("mem", 0) / x["maxmem"]) if x.get("maxmem") else 0,
                reverse=True,
            )

        top = running[:limit]
        vms = [_parse_vm_info(vm, node) for vm in top]

        return format_top_vms(vms, sort_by)

    @mcp.tool()
    @_handle_error
    async def get_rrd_data(
        ctx: Context,
        timeframe: str = "day",
        cf: str = "AVERAGE",
        node: str | None = None,
    ) -> str:
        """获取 PVE 节点的历史性能趋势数据。

        返回 CPU、内存等指标的历史趋势，适合分析负载变化。

        Args:
            timeframe: 时间范围，可选 hour / day / week / month / year
            cf: 聚合方式，AVERAGE（平均值）或 MAX（最大值）
            node: 节点名称（可选）
        """
        validate_rrd_timeframe(timeframe)

        app = _get_app_state(ctx)
        client: PVEClient = app.pve_client
        config = app.config
        node = await _resolve_node(client, config, node)

        rrd = await client.get(
            f"/nodes/{node}/rrddata",
            params={"timeframe": timeframe, "cf": cf},
        )

        samples = [
            RRDSample(
                timestamp=s.get("time", 0),
                cpu=s.get("cpu"),
                mem_used=s.get("memused"),
                mem_total=s.get("memtotal"),
                net_in=s.get("netin"),
                net_out=s.get("netout"),
                disk_read=s.get("diskread"),
                disk_write=s.get("diskwrite"),
            )
            for s in rrd
        ]

        return format_rrd_data(samples, timeframe, cf)


def _parse_size(size_str: str) -> int:
    """解析 PVE 磁盘大小字符串为字节，如 '32G' → 34359738368。"""
    size_str = size_str.strip().upper()
    if not size_str:
        return 0
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = size_str[-1]
    if suffix in multipliers:
        try:
            return int(float(size_str[:-1]) * multipliers[suffix])
        except ValueError:
            return 0
    try:
        return int(size_str)
    except ValueError:
        return 0
