"""自定义异常体系"""


class PVEError(Exception):
    """PVE 相关错误的基类"""


class PVEConnectionError(PVEError):
    """连接 PVE 失败（网络不通、地址错误、超时）"""


class PVEAuthenticationError(PVEError):
    """认证失败（Token 无效或权限不足）"""


class PVEAPIError(PVEError):
    """PVE API 返回错误响应"""


class PVEConfigError(PVEError):
    """配置错误（缺少必填项等）"""


class VMNotFoundError(PVEError):
    """虚拟机未找到"""


class NodeNotFoundError(PVEError):
    """节点未找到"""
