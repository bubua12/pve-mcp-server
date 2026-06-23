"""输入验证函数"""

from pve_mcp.client.exceptions import PVEAPIError


def validate_vmid(vmid: int) -> None:
    """验证 VM ID 是否有效。"""
    if not (1 <= vmid <= 999999):
        raise PVEAPIError(f"VM ID 必须在 1~999999 之间，当前值: {vmid}")


def validate_node_name(node: str) -> None:
    """验证节点名称。"""
    if not node or not node.strip():
        raise PVEAPIError("节点名称不能为空")


def validate_rrd_timeframe(timeframe: str) -> None:
    """验证 RRD 时间范围参数。"""
    valid = ("hour", "day", "week", "month", "year")
    if timeframe not in valid:
        raise PVEAPIError(f"timeframe 必须是 {'/'.join(valid)} 之一，当前值: {timeframe}")


def validate_sort_by(sort_by: str) -> None:
    """验证排序字段。"""
    valid = ("cpu", "memory")
    if sort_by not in valid:
        raise PVEAPIError(f"sort_by 必须是 {'/'.join(valid)} 之一，当前值: {sort_by}")
