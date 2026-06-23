# PVE MCP Server

[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

通过 [MCP (Model Context Protocol)](https://modelcontextprotocol.io) 协议，让你的 AI 助手直接监控和分析 Proxmox VE 虚拟化环境。

## ✨ 功能

### MCP Tools（工具）

| 工具 | 描述 |
|------|------|
| `get_node_status` | 节点实时状态（CPU/内存/负载/磁盘） |
| `list_nodes` | 集群节点列表 |
| `list_vms` | 虚拟机列表及运行状态 |
| `get_vm_detail` | 单台 VM 详细配置与实时状态 |
| `get_top_vms` | 资源消耗 Top N 排名 |
| `list_storage` | 存储池容量使用情况 |
| `analyze_resource_allocation` | 资源分配分析，超分配检测 |
| `get_rrd_data` | 历史性能趋势数据 |

### MCP Resources（资源）

| URI | 描述 |
|-----|------|
| `pve://nodes` | 节点列表 |
| `pve://nodes/{node}/status` | 节点状态 |
| `pve://nodes/{node}/qemu` | VM 列表 |
| `pve://nodes/{node}/qemu/{vmid}` | VM 详情 |
| `pve://nodes/{node}/storage` | 存储列表 |

### MCP Prompts（提示词）

| Prompt | 描述 |
|--------|------|
| `diagnose_high_load` | 负载过高诊断流程 |
| `capacity_planning` | 资源容量规划 |
| `daily_check` | 日常健康巡检 |

## 🚀 快速开始

### 1. 创建 PVE API Token

登录 PVE Web UI → **Datacenter** → **Permissions** → **API Tokens**：

- 用户：`monitor@pam`
- Token ID：`mcp-token`
- 权限：分配 `Sys.Audit`、`VM.Audit`、`VM.Monitor`、`Datastore.Audit` 角色

### 2. 安装

```bash
# 克隆项目
git clone <repo-url>
cd pve-mcp-server

# 安装（使用 uv 推荐）
uv pip install -e .

# 或 pip
pip install -e .
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 PVE 信息
```

关键配置项：

| 变量 | 说明 | 必填 |
|------|------|------|
| `PVE_HOST` | PVE 地址，如 `https://192.168.1.100:8006` | ✅ |
| `PVE_TOKEN_ID` | Token ID，如 `monitor@pam!mcp-token` | ✅ |
| `PVE_TOKEN_SECRET` | Token Secret | ✅ |
| `PVE_VERIFY_SSL` | 是否验证 SSL（自签名证书设 `false`） | ❌ |

### 4. 运行

```bash
# 直接运行
pve-mcp-server

# 或
python -m pve_mcp.server
```

## 🔌 接入 Claude Desktop / Claude Code

在 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "pve-monitor": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/pve-mcp-server", "pve-mcp-server"],
      "env": {
        "PVE_HOST": "https://192.168.1.100:8006",
        "PVE_TOKEN_ID": "monitor@pam!mcp-token",
        "PVE_TOKEN_SECRET": "your-secret-here",
        "PVE_VERIFY_SSL": "false"
      }
    }
  }
}
```

配置完成后，你就可以在 AI 对话中直接问：

- "帮我看看 PVE 现在的整体状态"
- "哪台 VM 最吃 CPU？"
- "我想新建一个 4 核 8G 的 VM，资源够吗？"
- "最近一周负载趋势怎么样？"

## 📁 项目结构

```
pve-mcp-server/
├── src/pve_mcp/
│   ├── server.py           # MCP Server 入口
│   ├── config.py           # 配置管理
│   ├── client/
│   │   ├── base.py         # PVE API 客户端
│   │   ├── models.py       # 数据模型
│   │   └── exceptions.py   # 异常定义
│   ├── tools/
│   │   ├── node.py         # 节点工具
│   │   └── vm.py           # 虚拟机工具
│   ├── resources/
│   │   ├── node.py         # 节点资源
│   │   └── vm.py           # VM 资源
│   ├── prompts/
│   │   └── diagnostics.py  # 诊断提示词
│   └── utils/
│       ├── formatters.py   # 输出格式化
│       └── validators.py   # 输入验证
├── tests/
├── docs/
│   ├── PRD.md              # 产品需求文档
│   └── SDD.md              # 详细设计文档
├── pyproject.toml
└── .env.example
```

## 🔒 安全说明

- 推荐使用 **API Token** 认证，权限遵循最小原则
- Token Secret 通过环境变量注入，不硬编码
- 所有工具默认**只读**，不执行写操作
- 日志中不记录 Token 等敏感信息

## 📜 License

MIT
