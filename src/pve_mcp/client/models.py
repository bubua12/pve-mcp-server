"""PVE API 响应数据模型"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NodeStatus:
    """节点状态信息"""

    node: str
    status: str  # "online" / "offline"
    uptime: int  # 秒
    cpu: float  # CPU 使用率 (0~1)
    maxcpu: int  # CPU 核心数
    mem: int  # 已用内存（字节）
    maxmem: int  # 总内存（字节）
    disk: int  # 根分区已用（字节）
    maxdisk: int  # 根分区总容量（字节）
    loadavg: list[float] = field(default_factory=list)
    kversion: str = ""
    pve_version: str = ""

    @property
    def cpu_percent(self) -> float:
        return self.cpu * 100

    @property
    def mem_percent(self) -> float:
        return (self.mem / self.maxmem * 100) if self.maxmem else 0.0

    @property
    def disk_percent(self) -> float:
        return (self.disk / self.maxdisk * 100) if self.maxdisk else 0.0

    @property
    def uptime_str(self) -> str:
        days, rem = divmod(self.uptime, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days} 天")
        if hours:
            parts.append(f"{hours} 小时")
        parts.append(f"{minutes} 分")
        return " ".join(parts)


@dataclass
class VMInfo:
    """虚拟机简要信息"""

    vmid: int
    name: str
    status: str  # "running" / "stopped" / "paused"
    cpu: float  # 当前 CPU 使用 (0~maxcpu)
    maxcpu: int
    mem: int  # 当前内存使用（字节）
    maxmem: int  # 分配内存（字节）
    disk: int  # 磁盘使用（字节）
    maxdisk: int  # 磁盘容量（字节）
    uptime: int  # 秒
    node: str = ""

    @property
    def cpu_percent(self) -> float:
        return (self.cpu / self.maxcpu * 100) if self.maxcpu else 0.0

    @property
    def mem_percent(self) -> float:
        return (self.mem / self.maxmem * 100) if self.maxmem else 0.0

    @property
    def mem_used_gb(self) -> float:
        return self.mem / (1024**3)

    @property
    def mem_total_gb(self) -> float:
        return self.maxmem / (1024**3)

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def uptime_str(self) -> str:
        if self.uptime == 0:
            return "—"
        days, rem = divmod(self.uptime, 86400)
        hours, _ = divmod(rem, 3600)
        return f"{days}天{hours}小时" if days else f"{hours}小时"


@dataclass
class DiskInfo:
    """磁盘配置"""

    device: str  # "virtio0", "scsi0"
    storage: str  # 存储池名称
    size: int  # 字节
    format: str = ""  # "raw", "qcow2"


@dataclass
class NICInfo:
    """网卡配置"""

    device: str  # "net0"
    model: str  # "virtio", "e1000"
    bridge: str = ""
    mac: str = ""


@dataclass
class VMDetail:
    """虚拟机详细配置"""

    vmid: int
    name: str
    status: str
    uptime: int
    cpu_cores: int
    cpu_type: str
    memory: int  # 字节
    disks: list[DiskInfo] = field(default_factory=list)
    nics: list[NICInfo] = field(default_factory=list)
    cpu_usage: float = 0.0
    mem_used: int = 0
    snapshot_count: int = 0
    description: str = ""

    @property
    def memory_gb(self) -> float:
        return self.memory / (1024**3)

    @property
    def mem_used_percent(self) -> float:
        return (self.mem_used / self.memory * 100) if self.memory else 0.0


@dataclass
class StorageInfo:
    """存储池信息"""

    storage: str
    type: str  # "lvm", "zfspool", "dir", ...
    total: int  # 字节
    used: int  # 字节
    available: int  # 字节
    content: str = ""  # "images,iso,backup"
    enabled: bool = True
    active: bool = True

    @property
    def used_percent(self) -> float:
        return (self.used / self.total * 100) if self.total else 0.0

    @property
    def total_gb(self) -> float:
        return self.total / (1024**3)

    @property
    def used_gb(self) -> float:
        return self.used / (1024**3)


@dataclass
class ResourceAllocation:
    """资源分配分析结果"""

    physical_cpu: int
    allocated_vcpu: int
    cpu_overcommit_ratio: float
    physical_mem: int
    allocated_mem: int
    mem_overcommit_ratio: float
    running_vms: int
    stopped_vms: int
    total_containers: int
    recommendation: str


@dataclass
class RRDSample:
    """RRD 时间序列采样点"""

    timestamp: int
    cpu: float | None = None
    mem_used: int | None = None
    mem_total: int | None = None
    net_in: int | None = None
    net_out: int | None = None
    disk_read: int | None = None
    disk_write: int | None = None
    loadavg: float | None = None

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)
