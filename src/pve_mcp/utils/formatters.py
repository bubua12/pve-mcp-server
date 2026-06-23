"""数据格式化 — 将结构化数据转为人类可读的 Markdown 文本"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pve_mcp.client.models import NodeStatus, VMInfo, VMDetail, StorageInfo, RRDSample

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _bytes_to_gb(b: int) -> float:
    return b / (1024**3)


def _pct(used: int, total: int) -> float:
    return (used / total * 100) if total else 0.0


def _assess(value_pct: float, warn: float = 70, danger: float = 90) -> str:
    if value_pct < warn:
        return "✅ 正常"
    elif value_pct < danger:
        return "⚠️ 警告"
    return "🔴 危险"


def _assess_load(load: float, cores: int) -> str:
    if cores == 0:
        return "❓ 未知"
    ratio = load / cores
    if ratio < 1.0:
        return "✅ 正常"
    elif ratio < 1.5:
        return "⚠️ 偏高"
    return "🔴 过高"


# ---------------------------------------------------------------------------
# 节点格式化
# ---------------------------------------------------------------------------

def format_node_status(status: NodeStatus) -> str:
    """格式化节点状态为 Markdown 文本。"""
    load1 = status.loadavg[0] if status.loadavg else 0.0
    load5 = status.loadavg[1] if len(status.loadavg) > 1 else 0.0
    load15 = status.loadavg[2] if len(status.loadavg) > 2 else 0.0

    lines = [
        f"## 🖥️ PVE 节点状态: {status.node}",
        "",
        "### 系统信息",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 节点名称 | {status.node} |",
        f"| 状态 | {'🟢 在线' if status.status == 'online' else '🔴 离线'} |",
        f"| 运行时间 | {status.uptime_str} |",
        f"| PVE 版本 | {status.pve_version or 'N/A'} |",
        f"| 内核版本 | {status.kversion or 'N/A'} |",
        "",
        "### 💻 CPU",
        f"| 指标 | 值 | 状态 |",
        f"|------|-----|------|",
        f"| 核心数 | {status.maxcpu} 核 | — |",
        f"| 使用率 | {status.cpu_percent:.1f}% | {_assess(status.cpu_percent)} |",
        f"| 1 分钟负载 | {load1:.2f} | {_assess_load(load1, status.maxcpu)} |",
        f"| 5 分钟负载 | {load5:.2f} | {_assess_load(load5, status.maxcpu)} |",
        f"| 15 分钟负载 | {load15:.2f} | {_assess_load(load15, status.maxcpu)} |",
        "",
        "### 🧠 内存",
        f"| 指标 | 值 | 状态 |",
        f"|------|-----|------|",
        f"| 总内存 | {_bytes_to_gb(status.maxmem):.1f} GB | — |",
        f"| 已用 | {_bytes_to_gb(status.mem):.1f} GB ({status.mem_percent:.1f}%) | {_assess(status.mem_percent)} |",
        f"| 可用 | {_bytes_to_gb(status.maxmem - status.mem):.1f} GB | — |",
        "",
        "### 💾 磁盘 (root)",
        f"| 指标 | 值 | 状态 |",
        f"|------|-----|------|",
        f"| 总容量 | {_bytes_to_gb(status.maxdisk):.0f} GB | — |",
        f"| 已用 | {_bytes_to_gb(status.disk):.0f} GB ({status.disk_percent:.1f}%) | {_assess(status.disk_percent, 80, 95)} |",
    ]

    # 综合评估
    overall = "✅ 整体健康"
    if status.cpu_percent > 90 or status.mem_percent > 95 or status.disk_percent > 95:
        overall = "🔴 存在风险，请立即关注"
    elif status.cpu_percent > 70 or status.mem_percent > 80 or status.disk_percent > 85:
        overall = "⚠️ 部分指标偏高，建议关注"

    lines += ["", f"### 📊 综合评估: {overall}"]
    return "\n".join(lines)


def format_node_list(nodes: list[dict]) -> str:
    """格式化节点列表。"""
    lines = ["## 🖥️ 节点列表", "", "| 节点 | 状态 | CPU | 内存 | 运行时间 |", "|------|------|-----|------|----------|"]
    for n in nodes:
        status_icon = "🟢" if n.get("status") == "online" else "🔴"
        cpu_pct = n.get("cpu", 0) * 100
        mem_pct = _pct(n.get("mem", 0), n.get("maxmem", 0))
        uptime = n.get("uptime", 0)
        days = uptime // 86400
        hours = (uptime % 86400) // 3600
        lines.append(
            f"| {n.get('node', '?')} | {status_icon} {n.get('status', '?')} "
            f"| {cpu_pct:.1f}% ({n.get('maxcpu', '?')}核) "
            f"| {mem_pct:.1f}% "
            f"| {days}天{hours}小时 |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# VM 格式化
# ---------------------------------------------------------------------------

def format_vm_list(node: str, vms: list[VMInfo]) -> str:
    """格式化虚拟机列表。"""
    running = [v for v in vms if v.is_running]
    stopped = [v for v in vms if not v.is_running]

    lines = [
        f"## 🖥️ 虚拟机列表 ({node})",
        "",
        f"共 {len(vms)} 台虚拟机，{len(running)} 台运行中",
        "",
    ]

    if running:
        lines += [
            f"### 🟢 运行中 ({len(running)})",
            "",
            "| VMID | 名称 | CPU | 内存 | 磁盘 | 运行时间 |",
            "|------|------|-----|------|------|----------|",
        ]
        for v in running:
            lines.append(
                f"| {v.vmid} | {v.name} "
                f"| {v.cpu_percent:.1f}% ({v.maxcpu}核) "
                f"| {v.mem_used_gb:.1f}/{v.mem_total_gb:.0f} GB "
                f"| {_bytes_to_gb(v.maxdisk):.0f} GB "
                f"| {v.uptime_str} |"
            )
        lines.append("")

    if stopped:
        lines += [
            f"### ⚫ 已停止 ({len(stopped)})",
            "",
            "| VMID | 名称 | 分配资源 |",
            "|------|------|----------|",
        ]
        for v in stopped:
            lines.append(
                f"| {v.vmid} | {v.name} | {v.maxcpu}核 / {_bytes_to_gb(v.maxmem):.0f} GB |"
            )

    return "\n".join(lines)


def format_vm_detail(node: str, config: VMDetail, status: VMInfo | None = None) -> str:
    """格式化虚拟机详情。"""
    lines = [
        f"## 📋 虚拟机详情: VM {config.vmid} ({config.name})",
        "",
        "### 基本信息",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| VMID | {config.vmid} |",
        f"| 名称 | {config.name} |",
        f"| 状态 | {'🟢 运行中' if config.status == 'running' else '⚫ 已停止'} |",
        f"| 运行时间 | {status.uptime_str if status else '—'} |",
        f"| 描述 | {config.description or 'N/A'} |",
        "",
        "### 硬件配置",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| CPU | {config.cpu_cores} 核 ({config.cpu_type}) |",
        f"| 内存 | {config.memory_gb:.1f} GB |",
    ]

    if config.disks:
        lines += ["", "### 💾 磁盘", "| 设备 | 存储池 | 大小 |", "|------|--------|------|"]
        for d in config.disks:
            lines.append(f"| {d.device} | {d.storage} | {_bytes_to_gb(d.size):.0f} GB |")

    if config.nics:
        lines += ["", "### 🌐 网络", "| 设备 | 模型 | 桥接 | MAC |", "|------|------|------|-----|"]
        for n in config.nics:
            lines.append(f"| {n.device} | {n.model} | {n.bridge} | {n.mac} |")

    if status and status.is_running:
        lines += [
            "",
            "### 📊 实时状态",
            f"| 指标 | 值 | 状态 |",
            f"|------|-----|------|",
            f"| CPU 使用率 | {status.cpu_percent:.1f}% | {_assess(status.cpu_percent)} |",
            f"| 内存使用 | {status.mem_used_gb:.1f} / {status.mem_total_gb:.1f} GB ({status.mem_percent:.1f}%) | {_assess(status.mem_percent)} |",
        ]

    if config.snapshot_count > 0:
        lines += ["", f"### 📸 快照: {config.snapshot_count} 个"]

    return "\n".join(lines)


def format_top_vms(vms: list[VMInfo], sort_by: str) -> str:
    """格式化 Top N 资源消耗 VM 列表。"""
    label = "CPU" if sort_by == "cpu" else "内存"
    lines = [
        f"## 🏆 Top {len(vms)} {label}消耗虚拟机",
        "",
        f"| 排名 | VMID | 名称 | CPU | 内存 | 运行时间 |",
        f"|------|------|------|-----|------|----------|",
    ]
    for i, v in enumerate(vms, 1):
        lines.append(
            f"| {i} | {v.vmid} | {v.name} "
            f"| {v.cpu_percent:.1f}% ({v.maxcpu}核) "
            f"| {v.mem_used_gb:.1f}/{v.mem_total_gb:.0f} GB ({v.mem_percent:.1f}%) "
            f"| {v.uptime_str} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 存储格式化
# ---------------------------------------------------------------------------

def format_storage_list(storages: list[StorageInfo]) -> str:
    """格式化存储池列表。"""
    lines = [
        "## 💾 存储池列表",
        "",
        "| 名称 | 类型 | 总容量 | 已用 | 使用率 | 内容类型 | 状态 |",
        "|------|------|--------|------|--------|----------|------|",
    ]
    for s in storages:
        icon = "🟢" if s.active else "🔴"
        lines.append(
            f"| {s.storage} | {s.type} "
            f"| {s.total_gb:.0f} GB | {s.used_gb:.0f} GB "
            f"| {s.used_percent:.1f}% {_assess(s.used_percent, 70, 90)} "
            f"| {s.content} | {icon} {'活跃' if s.active else '离线'} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 资源分配格式化
# ---------------------------------------------------------------------------

def format_resource_allocation(
    physical_cpu: int,
    physical_mem: int,
    allocated_vcpu: int,
    allocated_mem: int,
    running_vms: int,
    stopped_vms: int,
    running_vcpu: int,
) -> str:
    """格式化资源分配分析。"""
    cpu_ratio = allocated_vcpu / physical_cpu if physical_cpu else 0
    mem_ratio = allocated_mem / physical_mem if physical_mem else 0

    def _overcommit(ratio: float) -> str:
        if ratio < 1.0:
            return "✅ 安全"
        elif ratio < 1.5:
            return "⚠️ 超分配"
        return "🔴 严重超分配"

    # 容量建议
    remaining_cpu = physical_cpu - allocated_vcpu
    remaining_mem = physical_mem - allocated_mem
    recommendations = []
    if remaining_cpu <= 0:
        recommendations.append("CPU 已无余量，不建议创建新 VM")
    if remaining_mem < 4 * (1024**3):
        recommendations.append("内存剩余不足 4 GB，创建新 VM 前请评估")
    if not recommendations:
        recommendations.append("资源充足，可继续创建 VM")

    lines = [
        "## 📊 资源分配分析",
        "",
        "### CPU 分配",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 物理核心 | {physical_cpu} 核 |",
        f"| 已分配 vCPU | {allocated_vcpu} |",
        f"| 运行中 VM vCPU | {running_vcpu} |",
        f"| 超分配率 | {cpu_ratio:.0%} {_overcommit(cpu_ratio)} |",
        "",
        "### 内存分配",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 物理内存 | {_bytes_to_gb(physical_mem):.1f} GB |",
        f"| 已分配内存 | {_bytes_to_gb(allocated_mem):.1f} GB |",
        f"| 超分配率 | {mem_ratio:.0%} {_overcommit(mem_ratio)} |",
        "",
        "### 虚拟机统计",
        f"| 状态 | 数量 |",
        f"|------|------|",
        f"| 运行中 | {running_vms} |",
        f"| 已停止 | {stopped_vms} |",
        f"| 合计 | {running_vms + stopped_vms} |",
        "",
        "### 💡 建议",
    ]
    for r in recommendations:
        lines.append(f"- {r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RRD 格式化
# ---------------------------------------------------------------------------

def format_rrd_data(samples: list[RRDSample], timeframe: str, cf: str) -> str:
    """格式化 RRD 历史趋势数据。"""
    if not samples:
        return "## 📈 性能趋势\n\n暂无数据。"

    cpu_vals = [s.cpu for s in samples if s.cpu is not None]
    mem_vals = [s.mem_used for s in samples if s.mem_used is not None]

    lines = [
        f"## 📈 性能趋势 (最近 {timeframe}, {cf})",
        "",
    ]

    if cpu_vals:
        lines += [
            "### CPU 使用率",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 平均 | {sum(cpu_vals) / len(cpu_vals) * 100:.1f}% |",
            f"| 最高 | {max(cpu_vals) * 100:.1f}% |",
            f"| 最低 | {min(cpu_vals) * 100:.1f}% |",
            "",
        ]

    if mem_vals:
        avg_mem = sum(mem_vals) / len(mem_vals)
        lines += [
            "### 内存使用",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 平均 | {_bytes_to_gb(int(avg_mem)):.1f} GB |",
            f"| 最高 | {_bytes_to_gb(max(mem_vals)):.1f} GB |",
            f"| 最低 | {_bytes_to_gb(min(mem_vals)):.1f} GB |",
            "",
        ]

    lines.append(f"> 💡 共 {len(samples)} 个数据点。可切换 timeframe 为 hour/week/month/year 获取不同粒度。")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 错误格式化
# ---------------------------------------------------------------------------

def format_connection_error(host: str) -> str:
    return f"""## ❌ 连接 PVE 失败

**目标地址**：{host}

**排查建议**：
1. 检查 `PVE_HOST` 环境变量是否正确
2. 确认 PVE 服务是否正在运行
3. 检查网络是否可达
4. 确认端口 8006 是否开放
"""


def format_auth_error(detail: str) -> str:
    return f"""## ❌ 认证失败

**错误信息**：{detail}

**排查建议**：
1. 检查 `PVE_TOKEN_ID` 和 `PVE_TOKEN_SECRET` 是否正确
2. 确认 Token 未过期或被删除
3. 确认 Token 有足够权限（需要 Sys.Audit, VM.Audit）
"""


def format_error(title: str, detail: str) -> str:
    return f"## ❌ {title}\n\n{detail}"
