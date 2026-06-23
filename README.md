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

### 1. 创建 PVE API Token 并分配权限

#### 1.1 创建 API Token

**方式一：Web UI**

登录 PVE Web UI → **数据中心** → **权限** → **API Tokens** → **添加**：

- 用户：`root@pam`（或新建专用用户如 `monitor@pam`）
- Token ID：`mcp-token`
- 勾选 **Privilege Separation**（推荐，Token 权限独立于用户）

> ⚠️ 创建时会显示 Token Secret，**只显示一次**，请务必复制保存。

**方式二：命令行**

```bash
# 创建用户（可选，也可以直接用 root@pam）
pveum user add monitor@pam --comment "PVE MCP monitoring user"

# 创建 Token（privsep=1 表示权限分离）
pveum user token add root@pam mcp-token --privsep 1
```

#### 1.2 分配 Token 权限

> **重要**：PVE 中 API Token 的权限与用户权限是**独立的**，给用户分配权限**不会**自动继承到 Token。必须显式给 Token 分配权限。

**方式一：Web UI**

1. **数据中心** → **权限** → **添加**
2. **路径**：`/`（表示根路径，覆盖所有资源）
3. **角色**：`PVEAuditor`（只读权限）
4. **Token**：选择 `root@pam!mcp-token`（注意不是选择用户）
5. 点击 **添加**

**方式二：命令行（推荐）**

```bash
# 分配只读权限（推荐，最小权限原则）
pveum acl modify / --roles PVEAuditor --tokens 'root@pam!mcp-token'
```

<details>
<summary>其他常用角色（点击展开）</summary>

```bash
# 如果需要更多权限，可以使用以下角色：

# VM 管理权限（启动/停止/重启 VM）
pveum acl modify / --roles PVEVMAdmin --tokens 'root@pam!mcp-token'

# 完整管理权限（谨慎使用）
pveum acl modify / --roles PVEAdmin --tokens 'root@pam!mcp-token'

# 或者组合多个精细权限
pveum acl modify / --roles 'Sys.Audit,VM.Audit,VM.Monitor,Datastore.Audit' --tokens 'root@pam!mcp-token'
```

| 角色 | 权限说明 |
|------|----------|
| `PVEAuditor` | 只读：查看节点、VM、存储、任务等 |
| `PVEVMAdmin` | VM 管理：创建/删除/启动/停止/快照 |
| `PVEAdmin` | 全部管理权限（谨慎使用） |

</details>

#### 1.3 验证权限

```bash
# 查看 Token 列表
pveum user token list root@pam

# 查看当前权限配置
pveum acl list
```

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

## ❓ 常见问题

### Q: 提示 "权限不足" 或 "认证失败"

```
权限不足，请检查 API Token 的权限分配（需要 Sys.Audit, VM.Audit）
```

**原因**：PVE 中 API Token 权限与用户权限是独立的，创建 Token 后必须**单独给 Token 分配权限**。

**解决**：

```bash
# 确认 Token 存在
pveum user token list root@pam

# 给 Token 分配权限（注意用 --tokens 而不是 --users）
pveum acl modify / --roles PVEAuditor --tokens 'root@pam!mcp-token'

# 验证权限已生效
pveum acl list
```

### Q: 提示 "连接超时" 或 "SSL 错误"

检查 `.env` 中的 `PVE_HOST` 是否正确，如果是自签名证书，设置 `PVE_VERIFY_SSL=false`。

### Q: `pveum acl modify` 命令报 "invalid format"

```bash
# ❌ 错误：用户名末尾多了特殊字符
pveum acl modify / --roles PVEAuditor --users root@pam~

# ✅ 正确：确保没有多余字符
pveum acl modify / --roles PVEAuditor --users root@pam
```

### Q: Web UI 中看不到 Token 选项

权限添加界面中，**用户** 和 **Token** 是两个不同的下拉框。如果只看到用户选择，确认你创建的是 API Token 而不是 API Key。

## 🔒 安全说明

- 推荐使用 **API Token** 认证，权限遵循最小原则
- Token Secret 通过环境变量注入，不硬编码
- 所有工具默认**只读**，不执行写操作
- 日志中不记录 Token 等敏感信息

## 📜 License

MIT
