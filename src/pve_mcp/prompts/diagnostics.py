"""诊断提示词模板"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """注册 MCP Prompts。"""

    @mcp.prompt()
    def diagnose_high_load() -> str:
        """PVE 负载过高诊断流程。

        当用户反映 PVE 负载高时，引导 AI 按此流程排查。
        """
        return """你是一位 PVE 运维专家。用户反映 PVE 负载过高，请按以下步骤排查：

1. 先调用 get_node_status 获取节点状态，确认 CPU 使用率和负载情况
2. 调用 list_vms 查看所有虚拟机，找出 CPU 使用率最高的 VM
3. 调用 get_top_vms(sort_by="cpu") 确认 Top N 资源消耗 VM
4. 如果内存也是问题，调用 get_top_vms(sort_by="memory") 查看内存消耗排名
5. 综合分析，给出具体建议

回复时请：
- 先给出问题诊断结论
- 列出关键数据指标
- 给出可操作的优化建议
"""

    @mcp.prompt()
    def capacity_planning() -> str:
        """资源容量规划。

        当用户想创建新 VM 或评估资源是否充足时使用。
        """
        return """你是一位 PVE 运维专家。用户想评估资源是否充足，请按以下步骤分析：

1. 调用 get_node_status 获取物理资源总览
2. 调用 analyze_resource_allocation 获取资源分配详情
3. 根据用户想创建的 VM 规格，判断是否可行
4. 如果资源不足，建议哪些 VM 可以清理或优化

回复时请：
- 明确告知能否创建
- 用数字说话（物理资源 vs 已分配 vs 剩余）
- 如果超分配，给出风险提示和优化建议
"""

    @mcp.prompt()
    def daily_check() -> str:
        """日常健康巡检流程。"""
        return """你是一位 PVE 运维专家。请执行日常健康巡检：

1. 调用 get_node_status 获取节点状态
2. 调用 list_vms 查看虚拟机列表
3. 调用 list_storage 查看存储使用情况
4. 调用 analyze_resource_allocation 检查资源分配

输出格式：
- 先给出整体评估（✅ 良好 / ⚠️ 需关注 / ❌ 有问题）
- 列出关键指标
- 标出需要关注的项目
- 给出建议操作
"""
