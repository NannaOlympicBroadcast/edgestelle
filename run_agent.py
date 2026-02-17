#!/usr/bin/env python3
"""
EdgeStelle — Agent 启动脚本
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    from agent.agent import run_agent

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logging.getLogger("edgestelle.agent").info("Agent 被用户中断")
        sys.exit(0)


if __name__ == "__main__":
    main()
