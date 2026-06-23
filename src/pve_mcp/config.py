"""PVE 连接配置管理"""

from pydantic import Field
from pydantic_settings import BaseSettings


class PVEConfig(BaseSettings):
    """PVE 连接配置，通过环境变量或 .env 文件注入。

    优先级：环境变量 > .env 文件 > 默认值
    """

    model_config = {"env_prefix": "PVE_"}

    host: str = Field(
        description="PVE 主机地址，如 https://192.168.1.100:8006",
    )
    token_id: str = Field(
        description="API Token ID，格式：用户名@域名!token名，如 monitor@pam!mcp-token",
    )
    token_secret: str = Field(
        description="API Token Secret",
    )
    verify_ssl: bool = Field(
        default=False,
        description="是否验证 SSL 证书（自签名证书时设为 False）",
    )
    timeout: float = Field(
        default=10.0,
        description="API 请求超时时间（秒）",
    )
    node_name: str | None = Field(
        default=None,
        description="节点名称，留空则自动检测",
    )
    log_level: str = Field(
        default="INFO",
        description="日志级别",
    )
