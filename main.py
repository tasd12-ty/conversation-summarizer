"""
多模态对话摘要系统 - 主入口
"""

import uvicorn
from .api import app


def run(host: str = "0.0.0.0", port: int = 8000):
    """
    启动服务

    Args:
        host: 监听地址
        port: 监听端口
    """
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
