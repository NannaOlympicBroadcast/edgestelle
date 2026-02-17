#!/usr/bin/env python3
"""
EdgeStelle — Master 启动脚本
使用 uvicorn 运行 FastAPI 应用
"""

import uvicorn
from shared.config import MasterSettings


def main():
    settings = MasterSettings()
    uvicorn.run(
        "master.app:app",
        host=settings.master_host,
        port=settings.master_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
