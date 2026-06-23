# PVE MCP Server 详细设计文档 (SDD)

> **版本**: v1.0  
> **日期**: 2026-06-23  
> **作者**: Claude (AI 架构师)  
> **状态**: Draft  
> **技术栈**: Python 3.14, MCP SDK, httpx  
> **关联文档**: [PRD.md](./PRD.md)

---

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI 客户端 (Claude)                        │
│                    通过 MCP 协议交互 (stdio)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (本项目)                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Transport Layer                         │  │
│  │              (stdio / SSE 可选)                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    MCP 协议层                               │  │
│  │         Tool 注册 / Resource 注册 / Prompt 注册            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    业务逻辑层                               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │  节点     │ │   VM     │ │   LXC    │ │  资源     │      │  │
│  │  │  模块     │ │   模块   │ │   模块   │ │  分析     │      │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    数据访问层                               │  │
│  │              PVE API Client (httpx)                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Proxmox VE REST API                           │
│              https://pve-node:8006/api2/json                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 架构分层职责

| 层 | 职责 | 技术实现 |
|---|------|----------|
| **Transport Layer** | MCP 协议传输 | `mcp.server.stdio` 或 `mcp.server.sse` |
| **MCP 协议层** | 注册 Tools/Resources/Prompts | `FastMCP` 装饰器 |
| **业务逻辑层** | 数据处理、格式化、业务规则 | Python 模块 |
| **数据访问层** | PVE API 调用、认证、错误处理 | `httpx` + `PVEClient` 类 |

---

## 2. 项目结构

```
pve-mcp-server/
├── pyproject.toml              # 项目配置
├── README.md                   # 使用文档
├── .env.example                # 环境变量示例
│
├── src/
│   └── pve_mcp/
│       ├── __init__.py         # 包初始化
│       ├── server.py           # MCP Server 主入口
│       ├── config.py           # 配置管理
│       │
│       ├── client/             # PVE API 客户端
│       │   ├── __init__.py
│       │   ├── base.py         # 基础客户端类
│       │   ├── exceptions.py   # 自定义异常
│       │   └── models.py       # 数据模型 (dataclass)
│       │
│       ├── tools/              # MCP Tools 实现
│       │   ├── __init__.py
│       │   ├── node.py         # 节点相关工具
│       │   ├── vm.py           # VM 相关工具
│       │   ├── storage.py      # 存储相关工具 (Phase 2)
│       │   └── cluster.py      # 集群相关工具 (Phase 2)
│       │
│       ├── resources/          # MCP Resources 实现
│       │   ├── __init__.py
│       │   ├── node.py         # 节点资源
│       │   └── vm.py           # VM 资源
│       │
│       ├── prompts/            # MCP Prompts 实现
│       │   ├── __init__.py
│       │   └── diagnostics.py  # 诊断提示词模板
│       │
│       └── utils/              # 工具函数
│           ├── __init__.py
│           ├── formatters.py   # 输出格式化
│           └── validators.py   # 输入验证
│
├── tests/                      # 测试
│   ├── conftest.py
│   ├── test_client/
│   ├── test_tools/
│   └── test_resources/
│
└── docs/                       # 文档
    ├── PRD.md
    └── SDD.md                  # 本文档
```

---

## 3. 核心模块设计

### 3.1 配置管理 (`config.py`)

使用 `pydantic-settings` 管理配置，支持环境变量和 `.env` 文件。

```python
"""配置管理模块"""

from pydantic_settings import BaseSettings
from pydantic import Field


class PVEConfig(BaseSettings):
    """PVE 连接配置"""
    
    # PVE 节点地址
    host: str = Field(
        default="https://localhost:8006",
        description="PVE 节点地址 (包含端口)"
    )
    
    # 认证方式 1: API Token (推荐)
    token_name: str | None = Field(
        default=None,
        description="API Token 名称 (格式: user@realm!tokenid)"
    )
    token_secret: str | None = Field(
        default=None,
        description="API Token Secret"
    )
    
    # 认证方式 2: 用户名密码
    username: str | None = Field(
        default=None,
        description="PVE 用户名"
    )
    password: str | None = Field(
        default=None,
        description="PVE 密码"
    )
    
    # 连接配置
    verify_ssl: bool = Field(
        default=False,
        description="是否验证 SSL 证书"
    )
    timeout: int = Field(
        default=30,
        description="请求超时时间 (秒)"
    )
    
    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )
    
    model_config = {
        "env_prefix": "PVE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
    
    def get_auth_mode(self) -> str:
        """返回认证模式: 'token' 或 'password'"""
        if self.token_name and self.token_secret:
            return "token"
        elif self.username and self.password:
            return "password"
        else:
            raise ValueError("必须配置 PVE_TOKEN_NAME + PVE_TOKEN_SECRET 或 PVE_USERNAME + PVE_PASSWORD")
```

### 3.2 PVE API 客户端 (`client/base.py`)

封装所有与 PVE API 的交互。

```python
"""PVE REST API 客户端"""

import httpx
from typing import Any
from .exceptions import (
    PVEConnectionError,
    PVEAuthenticationError,
    PVEAPIError,
    PVETimeoutError,
)
from ..config import PVEConfig


class PVEClient:
    """Proxmox VE REST API 客户端
    
    使用 httpx 实现异步 HTTP 请求，支持 API Token 和用户名密码认证。
    """
    
    def __init__(self, config: PVEConfig) -> None:
        self._config = config
        self._base_url = f"{config.host}/api2/json"
        self._client: httpx.AsyncClient | None = None
        self._ticket: str | None = None  # 仅密码认证时使用
        self._csrf_token: str | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                verify=self._config.verify_ssl,
                timeout=httpx.Timeout(self._config.timeout),
            )
        return self._client
    
    async def _get_headers(self) -> dict[str, str]:
        """获取认证头"""
        auth_mode = self._config.get_auth_mode()
        
        if auth_mode == "token":
            return {
                "Authorization": f"PVEAPIToken={self._config.token_name}={self._config.token_secret}"
            }
        else:
            # 密码认证需要先获取 ticket
            if not self._ticket:
                await self._authenticate()
            return {
                "Cookie": f"PVEAuthCookie={self._ticket}",
                "CSRFPreventionToken": self._csrf_token,
            }
    
    async def _authenticate(self) -> None:
        """使用用户名密码认证"""
        client = await self._get_client()
        response = await client.post(
            f"{self._config.host}/api2/json/access/ticket",
            data={
                "username": self._config.username,
                "password": self._config.password,
            },
        )
        
        if response.status_code != 200:
            raise PVEAuthenticationError(f"认证失败: {response.text}")
        
        data = response.json()["data"]
        self._ticket = data["ticket"]
        self._csrf_token = data["CSRFPreventionToken"]
    
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """发送 GET 请求"""
        return await self._request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """发送 POST 请求"""
        return await self._request("POST", endpoint, data=data)
    
    async def put(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """发送 PUT 请求"""
        return await self._request("PUT", endpoint, data=data)
    
    async def delete(self, endpoint: str) -> Any:
        """发送 DELETE 请求"""
        return await self._request("DELETE", endpoint)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """发送 HTTP 请求并处理响应"""
        client = await self._get_client()
        headers = await self._get_headers()
        url = f"{self._base_url}{endpoint}"
        
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
            )
        except httpx.TimeoutException as e:
            raise PVETimeoutError(f"请求超时: {endpoint}") from e
        except httpx.ConnectError as e:
            raise PVEConnectionError(f"连接失败: {self._config.host}") from e
        
        # 处理 HTTP 错误
        if response.status_code == 401:
            raise PVEAuthenticationError("认证失败，请检查 Token 或用户名密码")
        elif response.status_code == 403:
            raise PVEAPIError("权限不足，无法访问该资源")
        elif response.status_code >= 400:
            raise PVEAPIError(f"API 错误 [{response.status_code}]: {response.text}")
        
        # 解析响应
        result = response.json()
        return result.get("data")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

### 3.3 数据模型 (`client/models.py`)

使用 `dataclass` 定义 PVE 返回数据的结构。

```python
"""PVE 数据模型定义"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NodeStatus:
    """节点状态信息"""
    node: str
    status: str  # "online" / "offline"
    uptime: int  # 秒
    cpu: float   # CPU 使用率 (0-1)
    maxcpu: int  # CPU 核心数
    mem: int     # 已用内存 (字节)
    maxmem: int  # 总内存 (字节)
    disk: int    # 已用磁盘 (字节)
    maxdisk: int # 总磁盘 (字节)
    loadavg: list[float] = field(default_factory=list)  # [1min, 5min, 15min]
    
    @property
    def cpu_percent(self) -> float:
        """CPU 使用率百分比"""
        return self.cpu * 100
    
    @property
    def mem_percent(self) -> float:
        """内存使用率百分比"""
        if self.maxmem == 0:
            return 0.0
        return (self.mem / self.maxmem) * 100
    
    @property
    def disk_percent(self) -> float:
        """磁盘使用率百分比"""
        if self.maxdisk == 0:
            return 0.0
        return (self.disk / self.maxdisk) * 100
    
    @property
    def uptime_str(self) -> str:
        """格式化的运行时间"""
        days = self.uptime // 86400
        hours = (self.uptime % 86400) // 3600
        minutes = (self.uptime % 3600) // 60
        if days > 0:
            return f"{days} 天 {hours} 小时 {minutes} 分"
        elif hours > 0:
            return f"{hours} 小时 {minutes} 分"
        else:
            return f"{minutes} 分"


@dataclass
class VMStatus:
    """虚拟机状态信息"""
    vmid: int
    name: str
    status: str  # "running" / "stopped" / "paused"
    cpu: float   # CPU 使用率 (0-maxcpu)
    maxcpu: int  # vCPU 数量
    mem: int     # 已用内存 (字节)
    maxmem: int  # 总内存 (字节)
    disk: int    # 已用磁盘 (字节)
    maxdisk: int # 总磁盘 (字节)
    uptime: int  # 运行时间 (秒)
    pid: int | None = None  # 进程 ID
    
    @property
    def cpu_percent(self) -> float:
        """CPU 使用率百分比"""
        if self.maxcpu == 0:
            return 0.0
        return (self.cpu / self.maxcpu) * 100
    
    @property
    def mem_percent(self) -> float:
        """内存使用率百分比"""
        if self.maxmem == 0:
            return 0.0
        return (self.mem / self.maxmem) * 100
    
    @property
    def mem_gb(self) -> float:
        """已用内存 (GB)"""
        return self.mem / (1024 ** 3)
    
    @property
    def maxmem_gb(self) -> float:
        """总内存 (GB)"""
        return self.maxmem / (1024 ** 3)
    
    @property
    def is_running(self) -> bool:
        """是否运行中"""
        return self.status == "running"


@dataclass
class VMConfig:
    """虚拟机配置信息"""
    vmid: int
    name: str
    cores: int
    memory: int  # MB
    cpu: str = "host"
    bios: str = "seabios"
    machine: str = "q35"
    ostype: str = "l26"
    scsihw: str = "virtio-scsi-single"
    net: dict[str, str] = field(default_factory=dict)
    scsi: dict[str, str] = field(default_factory=dict)
    ide: dict[str, str] = field(default_factory=dict)
    sata: dict[str, str] = field(default_factory=dict)
    virtio: dict[str, str] = field(default_factory=dict)
    description: str = ""
    
    @property
    def memory_gb(self) -> float:
        """内存大小 (GB)"""
        return self.memory / 1024


@dataclass
class VMCurrentStatus:
    """虚拟机当前运行状态"""
    vmid: int
    status: str
    cpu: float
    cpus: int
    mem: int
    maxmem: int
    disk: int
    maxdisk: int
    uptime: int
    nics: dict[str, Any] = field(default_factory=dict)
    blockstat: dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageStatus:
    """存储状态信息"""
    storage: str
    type: str
    content: str
    total: int
    used: int
    avail: int
    active: bool = True
    
    @property
    def used_percent(self) -> float:
        """使用率百分比"""
        if self.total == 0:
            return 0.0
        return (self.used / self.total) * 100


@dataclass
class RRDSample:
    """RRD 数据采样点"""
    timestamp: int
    cpu: float | None = None
    memused: int | None = None
    memtotal: int | None = None
    netin: int | None = None
    netout: int | None = None
    diskread: int | None = None
    diskwrite: int | None = None
    
    @property
    def datetime(self) -> datetime:
        """转换为 datetime 对象"""
        return datetime.fromtimestamp(self.timestamp)
```

### 3.4 异常定义 (`client/exceptions.py`)

```python
"""自定义异常类"""


class PVEError(Exception):
    """PVE 相关异常基类"""
    pass


class PVEConnectionError(PVEError):
    """连接 PVE 失败"""
    pass


class PVEAuthenticationError(PVEError):
    """认证失败"""
    pass


class PVEAPIError(PVEError):
    """PVE API 返回错误"""
    pass


class PVETimeoutError(PVEError):
    """请求超时"""
    pass


class PVEConfigError(PVEError):
    """配置错误"""
    pass


class VMNotFoundError(PVEError):
    """虚拟机未找到"""
    pass


class NodeNotFoundError(PVEError):
    """节点未找到"""
    pass
```

---

## 4. MCP Server 主入口 (`server.py`)

```python
"""MCP Server 主入口"""

import asyncio
from mcp.server.fastmcp import FastMCP
from loguru import logger

from .config import PVEConfig
from .client.base import PVEClient
from .tools.node import register_node_tools
from .tools.vm import register_vm_tools
from .resources.node import register_node_resources
from .resources.vm import register_vm_resources
from .prompts.diagnostics import register_prompts


def create_server() -> FastMCP:
    """创建并配置 MCP Server"""
    
    # 加载配置
    config = PVEConfig()
    logger.info(f"PVE Host: {config.host}")
    logger.info(f"认证模式: {config.get_auth_mode()}")
    
    # 创建 PVE 客户端
    pve_client = PVEClient(config)
    
    # 创建 MCP Server
    mcp = FastMCP(
        name="pve-mcp-server",
        version="1.0.0",
    )
    
    # 注册 Tools
    register_node_tools(mcp, pve_client)
    register_vm_tools(mcp, pve_client)
    
    # 注册 Resources
    register_node_resources(mcp, pve_client)
    register_vm_resources(mcp, pve_client)
    
    # 注册 Prompts
    register_prompts(mcp)
    
    logger.info("MCP Server 初始化完成")
    return mcp


def main() -> None:
    """主函数入口"""
    mcp = create_server()
    
    # 运行 Server (stdio 模式)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

---

## 5. MCP Tools 实现

### 5.1 节点工具 (`tools/node.py`)

```python
"""节点相关 MCP Tools"""

from mcp.server.fastmcp import FastMCP
from loguru import logger

from ..client.base import PVEClient
from ..client.models import NodeStatus
from ..utils.formatters import (
    format_node_status,
    format_node_list,
    format_resource_overview,
)


def register_node_tools(mcp: FastMCP, client: PVEClient) -> None:
    """注册节点相关工具"""
    
    @mcp.tool()
    async def get_node_status(node: str | None = None) -> str:
        """获取 PVE 节点的当前状态
        
        返回节点的 CPU、内存、磁盘、负载等详细信息，
        并给出负载评估和建议。
        
        Args:
            node: 节点名称 (可选，默认使用第一个在线节点)
        """
        try:
            # 获取节点名称
            if not node:
                nodes = await client.get("/nodes")
                if not nodes:
                    return "❌ 未找到任何 PVE 节点"
                node = nodes[0]["node"]
            
            # 获取节点状态
            status_data = await client.get(f"/nodes/{node}/status")
            
            # 获取详细 CPU 信息
            cpu_data = await client.get(f"/nodes/{node}/cpuinfo")
            
            # 解析为模型
            status = NodeStatus(
                node=node,
                status=status_data.get("status", "unknown"),
                uptime=status_data.get("uptime", 0),
                cpu=status_data.get("cpu", 0),
                maxcpu=status_data.get("maxcpu", cpu_data.get("cpus", 1)),
                mem=status_data.get("mem", 0),
                maxmem=status_data.get("maxmem", 0),
                disk=status_data.get("rootfs", {}).get("used", 0),
                maxdisk=status_data.get("rootfs", {}).get("total", 0),
                loadavg=status_data.get("loadavg", []),
            )
            
            return format_node_status(status)
            
        except Exception as e:
            logger.error(f"获取节点状态失败: {e}")
            return f"❌ 获取节点状态失败: {e}"
    
    @mcp.tool()
    async def list_nodes() -> str:
        """列出 PVE 集群中的所有节点
        
        返回所有节点的名称、状态、资源使用概览。
        """
        try:
            nodes = await client.get("/nodes")
            return format_node_list(nodes)
        except Exception as e:
            logger.error(f"获取节点列表失败: {e}")
            return f"❌ 获取节点列表失败: {e}"
    
    @mcp.tool()
    async def get_resource_overview() -> str:
        """获取 PVE 资源使用概览
        
        汇总所有节点的 CPU、内存、存储使用情况，
        并计算超分配率，给出资源评估建议。
        """
        try:
            nodes = await client.get("/nodes")
            all_vms = []
            
            for node in nodes:
                node_name = node["node"]
                vms = await client.get(f"/nodes/{node_name}/qemu")
                all_vms.extend(vms)
            
            return format_resource_overview(nodes, all_vms)
        except Exception as e:
            logger.error(f"获取资源概览失败: {e}")
            return f"❌ 获取资源概览失败: {e}"
```

### 5.2 VM 工具 (`tools/vm.py`)

```python
"""虚拟机相关 MCP Tools"""

from mcp.server.fastmcp import FastMCP
from loguru import logger

from ..client.base import PVEClient
from ..client.models import VMStatus, VMConfig, VMCurrentStatus
from ..utils.formatters import (
    format_vm_list,
    format_vm_detail,
    format_top_vms,
    format_rrd_data,
)
from ..utils.validators import validate_vmid


def register_vm_tools(mcp: FastMCP, client: PVEClient) -> None:
    """注册虚拟机相关工具"""
    
    @mcp.tool()
    async def list_vms(node: str | None = None) -> str:
        """列出节点上的所有虚拟机
        
        返回所有 VM 的 ID、名称、状态、CPU/内存使用情况。
        
        Args:
            node: 节点名称 (可选)
        """
        try:
            if not node:
                nodes = await client.get("/nodes")
                node = nodes[0]["node"]
            
            vms_data = await client.get(f"/nodes/{node}/qemu")
            
            vms = []
            for vm in vms_data:
                vms.append(VMStatus(
                    vmid=vm["vmid"],
                    name=vm.get("name", f"vm-{vm['vmid']}"),
                    status=vm["status"],
                    cpu=vm.get("cpu", 0),
                    maxcpu=vm.get("maxcpu", 1),
                    mem=vm.get("mem", 0),
                    maxmem=vm.get("maxmem", 0),
                    disk=vm.get("disk", 0),
                    maxdisk=vm.get("maxdisk", 0),
                    uptime=vm.get("uptime", 0),
                    pid=vm.get("pid"),
                ))
            
            return format_vm_list(node, vms)
            
        except Exception as e:
            logger.error(f"获取 VM 列表失败: {e}")
            return f"❌ 获取 VM 列表失败: {e}"
    
    @mcp.tool()
    async def get_vm_detail(vmid: int, node: str | None = None) -> str:
        """获取单个虚拟机的详细信息
        
        返回 VM 的完整配置、当前状态、磁盘、网络等信息。
        
        Args:
            vmid: 虚拟机 ID
            node: 节点名称 (可选)
        """
        validate_vmid(vmid)
        
        try:
            if not node:
                nodes = await client.get("/nodes")
                node = nodes[0]["node"]
            
            # 获取配置
            config_data = await client.get(f"/nodes/{node}/qemu/{vmid}/config")
            
            # 获取当前状态
            status_data = await client.get(f"/nodes/{node}/qemu/{vmid}/status/current")
            
            # 解析配置
            config = VMConfig(
                vmid=vmid,
                name=config_data.get("name", f"vm-{vmid}"),
                cores=config_data.get("cores", 1),
                memory=config_data.get("memory", 512),
                cpu=config_data.get("cpu", "host"),
                bios=config_data.get("bios", "seabios"),
                machine=config_data.get("machine", "q35"),
                ostype=config_data.get("ostype", "l26"),
                scsihw=config_data.get("scsihw", "virtio-scsi-single"),
                net={k: v for k, v in config_data.items() if k.startswith("net")},
                scsi={k: v for k, v in config_data.items() if k.startswith("scsi")},
                ide={k: v for k, v in config_data.items() if k.startswith("ide")},
                virtio={k: v for k, v in config_data.items() if k.startswith("virtio")},
                description=config_data.get("description", ""),
            )
            
            # 解析状态
            status = VMCurrentStatus(
                vmid=vmid,
                status=status_data.get("status", "unknown"),
                cpu=status_data.get("cpu", 0),
                cpus=status_data.get("cpus", 1),
                mem=status_data.get("mem", 0),
                maxmem=status_data.get("maxmem", 0),
                disk=status_data.get("disk", 0),
                maxdisk=status_data.get("maxdisk", 0),
                uptime=status_data.get("uptime", 0),
                nics=status_data.get("nics", {}),
                blockstat=status_data.get("blockstat", {}),
            )
            
            return format_vm_detail(node, config, status)
            
        except Exception as e:
            logger.error(f"获取 VM {vmid} 详情失败: {e}")
            return f"❌ 获取 VM {vmid} 详情失败: {e}"
    
    @mcp.tool()
    async def get_top_vms(
        node: str | None = None,
        sort_by: str = "cpu",
        limit: int = 5,
    ) -> str:
        """获取资源消耗最高的虚拟机
        
        按 CPU 或内存使用率排序，返回 Top N 的 VM 列表。
        
        Args:
            node: 节点名称 (可选)
            sort_by: 排序方式 "cpu" 或 "memory"
            limit: 返回数量 (默认 5)
        """
        if sort_by not in ("cpu", "memory"):
            return "❌ sort_by 参数必须是 'cpu' 或 'memory'"
        
        try:
            if not node:
                nodes = await client.get("/nodes")
                node = nodes[0]["node"]
            
            vms_data = await client.get(f"/nodes/{node}/qemu")
            
            # 只处理运行中的 VM
            running_vms = [vm for vm in vms_data if vm["status"] == "running"]
            
            # 排序
            if sort_by == "cpu":
                running_vms.sort(key=lambda x: x.get("cpu", 0) / max(x.get("maxcpu", 1), 1), reverse=True)
            else:
                running_vms.sort(key=lambda x: x.get("mem", 0) / max(x.get("maxmem", 1), 1), reverse=True)
            
            # 取 Top N
            top_vms = running_vms[:limit]
            
            vms = []
            for vm in top_vms:
                vms.append(VMStatus(
                    vmid=vm["vmid"],
                    name=vm.get("name", f"vm-{vm['vmid']}"),
                    status=vm["status"],
                    cpu=vm.get("cpu", 0),
                    maxcpu=vm.get("maxcpu", 1),
                    mem=vm.get("mem", 0),
                    maxmem=vm.get("maxmem", 0),
                    disk=vm.get("disk", 0),
                    maxdisk=vm.get("maxdisk", 0),
                    uptime=vm.get("uptime", 0),
                ))
            
            return format_top_vms(node, vms, sort_by)
            
        except Exception as e:
            logger.error(f"获取 Top VMs 失败: {e}")
            return f"❌ 获取 Top VMs 失败: {e}"
    
    @mcp.tool()
    async def get_rrd_data(
        node: str | None = None,
        timeframe: str = "day",
        cf: str = "AVERAGE",
    ) -> str:
        """获取节点的历史性能数据 (RRD)
        
        返回指定时间范围内的 CPU、内存、磁盘 IO、网络 IO 历史数据。
        
        Args:
            node: 节点名称 (可选)
            timeframe: 时间范围 "hour", "day", "week", "month", "year"
            cf: 聚合方式 "AVERAGE" 或 "MAX"
        """
        valid_timeframes = ("hour", "day", "week", "month", "year")
        if timeframe not in valid_timeframes:
            return f"❌ timeframe 必须是 {valid_timeframes} 之一"
        
        try:
            if not node:
                nodes = await client.get("/nodes")
                node = nodes[0]["node"]
            
            rrd_data = await client.get(
                f"/nodes/{node}/rrddata",
                params={"timeframe": timeframe, "cf": cf}
            )
            
            return format_rrd_data(node, rrd_data, timeframe, cf)
            
        except Exception as e:
            logger.error(f"获取 RRD 数据失败: {e}")
            return f"❌ 获取 RRD 数据失败: {e}"
```

---

## 6. MCP Resources 实现

### 6.1 节点资源 (`resources/node.py`)

```python
"""节点相关 MCP Resources"""

from mcp.server.fastmcp import FastMCP
from loguru import logger

from ..client.base import PVEClient
from ..client.models import NodeStatus


def register_node_resources(mcp: FastMCP, client: PVEClient) -> None:
    """注册节点相关资源"""
    
    @mcp.resource("pve://nodes")
    async def get_nodes_resource() -> str:
        """获取所有节点列表"""
        try:
            nodes = await client.get("/nodes")
            result = []
            for node in nodes:
                result.append({
                    "node": node["node"],
                    "status": node["status"],
                    "cpu": node.get("cpu", 0),
                    "maxcpu": node.get("maxcpu", 0),
                    "mem": node.get("mem", 0),
                    "maxmem": node.get("maxmem", 0),
                    "uptime": node.get("uptime", 0),
                })
            return str(result)
        except Exception as e:
            logger.error(f"获取节点资源失败: {e}")
            return f"Error: {e}"
    
    @mcp.resource("pve://nodes/{node}/status")
    async def get_node_status_resource(node: str) -> str:
        """获取单个节点状态"""
        try:
            status = await client.get(f"/nodes/{node}/status")
            return str(status)
        except Exception as e:
            logger.error(f"获取节点 {node} 状态资源失败: {e}")
            return f"Error: {e}"
```

### 6.2 VM 资源 (`resources/vm.py`)

```python
"""虚拟机相关 MCP Resources"""

from mcp.server.fastmcp import FastMCP
from loguru import logger

from ..client.base import PVEClient


def register_vm_resources(mcp: FastMCP, client: PVEClient) -> None:
    """注册虚拟机相关资源"""
    
    @mcp.resource("pve://nodes/{node}/qemu")
    async def get_vms_resource(node: str) -> str:
        """获取节点上所有 VM 列表"""
        try:
            vms = await client.get(f"/nodes/{node}/qemu")
            return str(vms)
        except Exception as e:
            logger.error(f"获取 VM 列表资源失败: {e}")
            return f"Error: {e}"
    
    @mcp.resource("pve://nodes/{node}/qemu/{vmid}")
    async def get_vm_resource(node: str, vmid: int) -> str:
        """获取单个 VM 详情"""
        try:
            config = await client.get(f"/nodes/{node}/qemu/{vmid}/config")
            status = await client.get(f"/nodes/{node}/qemu/{vmid}/status/current")
            return str({"config": config, "status": status})
        except Exception as e:
            logger.error(f"获取 VM {vmid} 资源失败: {e}")
            return f"Error: {e}"
```

---

## 7. 输出格式化 (`utils/formatters.py`)

### 7.1 节点状态格式化

```python
"""输出格式化工具函数"""

from ..client.models import NodeStatus, VMStatus, RRDSample


def format_node_status(status: NodeStatus) -> str:
    """格式化节点状态为人类可读文本"""
    
    # 负载评估
    load_1min = status.loadavg[0] if status.loadavg else 0
    load_assessment = _assess_load(load_1min, status.maxcpu)
    cpu_assessment = _assess_cpu(status.cpu_percent)
    mem_assessment = _assess_memory(status.mem_percent)
    disk_assessment = _assess_disk(status.disk_percent)
    
    return f"""📊 PVE 节点状态: {status.node}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🖥️  系统信息
   节点名称: {status.node}
   运行时间: {status.uptime_str}
   状态: {"🟢 在线" if status.status == "online" else "🔴 离线"}

💻 CPU
   使用率: {status.cpu_percent:.1f}% ({status.maxcpu} 核)
   1分钟负载: {load_1min:.2f}
   评估: {cpu_assessment}

🧠 内存
   总量: {status.maxmem / (1024**3):.1f} GB
   已用: {status.mem / (1024**3):.1f} GB ({status.mem_percent:.1f}%)
   可用: {(status.maxmem - status.mem) / (1024**3):.1f} GB
   评估: {mem_assessment}

💾 磁盘 (/)
   总量: {status.maxdisk / (1024**3):.0f} GB
   已用: {status.disk / (1024**3):.0f} GB ({status.disk_percent:.1f}%)
   可用: {(status.maxdisk - status.disk) / (1024**3):.0f} GB
   评估: {disk_assessment}

🔥 负载评估: {load_assessment}"""


def _assess_load(load: float, cores: int) -> str:
    """评估负载情况"""
    ratio = load / cores
    if ratio < 0.7:
        return "✅ 正常"
    elif ratio < 1.0:
        return "⚠️ 中等"
    elif ratio < 1.5:
        return "🟡 偏高"
    else:
        return "🔴 过高"


def _assess_cpu(percent: float) -> str:
    """评估 CPU 使用率"""
    if percent < 50:
        return f"✅ 正常 ({percent:.1f}%)"
    elif percent < 70:
        return f"⚠️ 中等 ({percent:.1f}%)"
    elif percent < 90:
        return f"🟡 偏高 ({percent:.1f}%)"
    else:
        return f"🔴 过高 ({percent:.1f}%)"


def _assess_memory(percent: float) -> str:
    """评估内存使用率"""
    if percent < 60:
        return f"✅ 正常 ({percent:.1f}%)"
    elif percent < 80:
        return f"⚠️ 中等 ({percent:.1f}%)"
    elif percent < 95:
        return f"🟡 偏高 ({percent:.1f}%)"
    else:
        return f"🔴 过高 ({percent:.1f}%)"


def _assess_disk(percent: float) -> str:
    """评估磁盘使用率"""
    if percent < 70:
        return f"✅ 正常 ({percent:.1f}%)"
    elif percent < 85:
        return f"⚠️ 中等 ({percent:.1f}%)"
    elif percent < 95:
        return f"🟡 偏高 ({percent:.1f}%)"
    else:
        return f"🔴 危险 ({percent:.1f}%)"


def format_vm_list(node: str, vms: list[VMStatus]) -> str:
    """格式化 VM 列表"""
    running = [vm for vm in vms if vm.is_running]
    stopped = [vm for vm in vms if not vm.is_running]
    
    result = f"""📋 虚拟机列表: {node}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 运行中 ({len(running)}/{len(vms)})
┌──────┬─────────────────┬─────────┬──────────┬──────────┐
│ VMID │ 名称            │ CPU     │ 内存     │ 磁盘     │
├──────┼─────────────────┼─────────┼──────────┼──────────┤"""
    
    for vm in running:
        result += f"\n│ {vm.vmid:<4} │ {vm.name:<15} │ {vm.cpu_percent:>5.1f}% │ {vm.mem_gb:.1f}/{vm.maxmem_gb:.0f} GB │ {vm.maxdisk / (1024**3):.0f} GB    │"
    
    result += "\n└──────┴─────────────────┴─────────┴──────────┴──────────┘"
    
    if stopped:
        result += f"\n\n🔴 已停止 ({len(stopped)}/{len(vms)})"
        result += "\n┌──────┬─────────────────┐"
        result += "\n│ VMID │ 名称            │"
        result += "\n├──────┼─────────────────┤"
        for vm in stopped:
            result += f"\n│ {vm.vmid:<4} │ {vm.name:<15} │"
        result += "\n└──────┴─────────────────┘"
    
    return result


def format_top_vms(node: str, vms: list[VMStatus], sort_by: str) -> str:
    """格式化 Top N VM 列表"""
    label = "CPU" if sort_by == "cpu" else "内存"
    
    result = f"""🏆 Top {len(vms)} {label}消耗虚拟机: {node}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────┬─────────────────┬─────────┬──────────┬──────────────────────┐
│ VMID │ 名称            │ CPU     │ 内存     │ 运行时间             │
├──────┼─────────────────┼─────────┼──────────┼──────────────────────┤"""
    
    for vm in vms:
        uptime_str = f"{vm.uptime // 86400}天 {(vm.uptime % 86400) // 3600}小时" if vm.uptime > 0 else "N/A"
        result += f"\n│ {vm.vmid:<4} │ {vm.name:<15} │ {vm.cpu_percent:>5.1f}% │ {vm.mem_gb:.1f}/{vm.maxmem_gb:.0f} GB │ {uptime_str:<20} │"
    
    result += "\n└──────┴─────────────────┴─────────┴──────────┴──────────────────────┘"
    
    return result


def format_rrd_data(
    node: str,
    data: list[dict],
    timeframe: str,
    cf: str,
) -> str:
    """格式化 RRD 数据"""
    if not data:
        return f"📊 RRD 数据: {node} (无数据)"
    
    # 计算统计数据
    cpu_values = [d.get("cpu", 0) for d in data if d.get("cpu") is not None]
    mem_values = [d.get("memused", 0) for d in data if d.get("memused") is not None]
    
    result = f"""📈 节点 {node} 性能趋势 (最近 {timeframe}, {cf})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💻 CPU 使用率
   平均: {sum(cpu_values) / len(cpu_values) * 100:.1f}%
   最高: {max(cpu_values) * 100:.1f}%
   最低: {min(cpu_values) * 100:.1f}%

🧠 内存使用
   平均: {sum(mem_values) / len(mem_values) / (1024**3):.1f} GB
   最高: {max(mem_values) / (1024**3):.1f} GB
   最低: {min(mem_values) / (1024**3):.1f} GB

📊 历史数据点: {len(data)} 个"""
    
    return result
```

---

## 8. 输入验证 (`utils/validators.py`)

```python
"""输入验证函数"""

from ..client.exceptions import PVEAPIError


def validate_vmid(vmid: int) -> None:
    """验证 VM ID 是否有效"""
    if not (100 <= vmid <= 999999):
        raise PVEAPIError(f"VM ID 必须在 100-999999 之间，当前值: {vmid}")


def validate_node_name(node: str) -> None:
    """验证节点名称"""
    if not node or not node.strip():
        raise PVEAPIError("节点名称不能为空")


def validate_timeframe(timeframe: str) -> None:
    """验证 RRD 时间范围"""
    valid = ("hour", "day", "week", "month", "year")
    if timeframe not in valid:
        raise PVEAPIError(f"timeframe 必须是 {valid} 之一")
```

---

## 9. 错误处理策略

### 9.1 错误分层处理

```
┌─────────────────────────────────────────────────┐
│                MCP Client (Claude)               │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           MCP Tool Handler (tools/*.py)          │
│           捕获异常，返回友好的错误文本              │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           PVE Client (client/base.py)            │
│           抛出具体的异常类型                       │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           httpx (HTTP 层)                        │
│           捕获网络异常，转换为 PVE 异常            │
└─────────────────────────────────────────────────┘
```

### 9.2 错误消息模板

```python
ERROR_MESSAGES = {
    "connection": """❌ 无法连接到 PVE

可能原因:
1. PVE 节点地址配置错误
2. PVE 节点未启动或网络不通
3. 防火墙阻止了 8006 端口

请检查:
- PVE_HOST 环境变量是否正确
- 能否 ping 通 PVE 节点
- 能否访问 https://<pve-host>:8006""",

    "authentication": """❌ PVE 认证失败

可能原因:
1. API Token 配置错误
2. Token 已过期或被删除
3. 用户名/密码错误

请检查:
- PVE_TOKEN_NAME 和 PVE_TOKEN_SECRET 是否正确
- 或 PVE_USERNAME 和 PVE_PASSWORD 是否正确
- Token 是否有访问权限""",

    "timeout": """❌ 请求超时

可能原因:
1. PVE 节点负载过高
2. 网络延迟过大

请稍后重试，或检查 PVE 节点状态""",
}
```

---

## 10. 依赖管理 (`pyproject.toml`)

```toml
[project]
name = "pve-mcp-server"
version = "1.0.0"
description = "Proxmox VE MCP Server - 通过 MCP 协议监控和管理 PVE"
readme = "README.md"
requires-python = ">=3.14"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "mcp[cli]>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "loguru>=0.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[project.scripts]
pve-mcp-server = "pve_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.14"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 11. 环境变量配置 (`.env.example`)

```bash
# PVE 节点地址 (必填)
PVE_HOST=https://your-pve-node:8006

# 认证方式 1: API Token (推荐)
# 在 PVE Web UI -> Datacenter -> Permissions -> API Tokens 创建
PVE_TOKEN_NAME=your-user@pam!your-token-name
PVE_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 认证方式 2: 用户名密码 (不推荐用于生产)
# PVE_USERNAME=root
# PVE_PASSWORD=your-password

# SSL 配置
PVE_VERIFY_SSL=false

# 超时时间 (秒)
PVE_TIMEOUT=30

# 日志级别
PVE_LOG_LEVEL=INFO
```

---

## 12. 部署与运行

### 12.1 安装

```bash
# 克隆项目
git clone <repo-url>
cd pve-mcp-server

# 使用 uv 安装 (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 12.2 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

### 12.3 运行

```bash
# 直接运行
pve-mcp-server

# 或使用 python -m
python -m pve_mcp.server
```

### 12.4 Claude Desktop 配置

在 Claude Desktop 配置文件中添加:

```json
{
  "mcpServers": {
    "pve": {
      "command": "pve-mcp-server",
      "env": {
        "PVE_HOST": "https://your-pve-node:8006",
        "PVE_TOKEN_NAME": "your-user@pam!your-token-name",
        "PVE_TOKEN_SECRET": "your-token-secret"
      }
    }
  }
}
```

---

## 13. 测试策略

### 13.1 单元测试示例

```python
"""测试节点状态格式化"""

import pytest
from pve_mcp.client.models import NodeStatus
from pve_mcp.utils.formatters import format_node_status


def test_format_node_status_normal():
    """测试正常状态格式化"""
    status = NodeStatus(
        node="pve-node01",
        status="online",
        uptime=1300000,
        cpu=0.45,
        maxcpu=8,
        mem=18 * (1024**3),
        maxmem=32 * (1024**3),
        disk=156 * (1024**3),
        maxdisk=500 * (1024**3),
        loadavg=[2.15, 1.89, 1.56],
    )
    
    result = format_node_status(status)
    
    assert "pve-node01" in result
    assert "45.0%" in result
    assert "🟢 在线" in result
```

### 13.2 集成测试 (使用 mock)

```python
"""测试 PVE 客户端"""

import pytest
from unittest.mock import AsyncMock, patch
from pve_mcp.client.base import PVEClient
from pve_mcp.config import PVEConfig


@pytest.fixture
def mock_config():
    return PVEConfig(
        host="https://localhost:8006",
        token_name="test@pam!test",
        token_secret="test-secret",
    )


@pytest.mark.asyncio
async def test_get_nodes(mock_config):
    """测试获取节点列表"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"node": "pve-node01", "status": "online"}
            ]
        }
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        client = PVEClient(mock_config)
        nodes = await client.get("/nodes")
        
        assert len(nodes) == 1
        assert nodes[0]["node"] == "pve-node01"
```

---

## 14. 安全考虑

### 14.1 认证安全

| 措施 | 说明 |
|------|------|
| Token 优先 | 推荐使用 API Token 而非用户名密码 |
| 最小权限 | Token 只授予必要的权限 (Sys.Audit, VM.Audit, VM.Monitor) |
| 环境变量 | 敏感信息存储在环境变量中，不硬编码 |

### 14.2 网络安全

| 措施 | 说明 |
|------|------|
| SSL 验证 | 生产环境应启用 SSL 证书验证 |
| 内网访问 | MCP Server 应部署在可访问 PVE 的内网环境 |
| 防火墙 | 限制 PVE 8006 端口的访问来源 |

### 14.3 数据安全

| 措施 | 说明 |
|------|------|
| 日志脱敏 | 日志中不记录 Token、密码等敏感信息 |
| 错误信息 | 错误返回中不暴露内部实现细节 |

---

## 15. 未来扩展点

### 15.1 Phase 2 扩展

- [ ] 添加 VM 控制工具 (启动/停止/重启)
- [ ] 添加快照管理工具
- [ ] 添加存储查询工具

### 15.2 Phase 3 扩展

- [ ] 添加 LXC 容器支持
- [ ] 添加集群管理支持
- [ ] 添加防火墙规则管理

### 15.3 性能优化

- [ ] 添加结果缓存 (TTL 缓存)
- [ ] 支持批量查询
- [ ] 异步并发请求

---

*文档结束*
