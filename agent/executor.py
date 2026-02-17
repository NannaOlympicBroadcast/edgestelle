"""
EdgeStelle — Agent 命令执行器
使用 asyncio.create_subprocess_shell 执行 Shell 命令
实时逐行捕获 stdout/stderr 并通过 MQTT 发布日志
"""

from __future__ import annotations

import asyncio
import logging
import time

from shared.mqtt_wrapper import MQTTClientWrapper
from shared.protocol import (
    topic_log,
    LogLinePayload,
    CmdDonePayload,
)

logger = logging.getLogger("edgestelle.agent.executor")


async def execute_command(
    cmd: str,
    exec_id: str,
    node_id: str,
    mqtt_client: MQTTClientWrapper,
) -> int:
    """
    异步执行 Shell 命令，逐行读取 stdout/stderr 并实时发布到 MQTT。
    返回进程退出码。
    """
    log_topic = topic_log(node_id)
    logger.info("开始执行命令 [exec=%s]: %s", exec_id, cmd[:200])

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        # 进程创建失败，发送错误日志
        error_msg = f"命令启动失败: {e}"
        logger.error(error_msg)
        mqtt_client.publish_json(log_topic, LogLinePayload(
            exec_id=exec_id,
            node_id=node_id,
            stream="stderr",
            line=error_msg,
        ))
        mqtt_client.publish_json(log_topic, CmdDonePayload(
            exec_id=exec_id,
            node_id=node_id,
            exit_code=-1,
        ))
        return -1

    async def _read_stream(stream: asyncio.StreamReader, stream_name: str):
        """逐行读取流并发布到 MQTT"""
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\n\r")
            mqtt_client.publish_json(log_topic, LogLinePayload(
                exec_id=exec_id,
                node_id=node_id,
                stream=stream_name,
                line=line,
            ))

    # 并发读取 stdout 和 stderr
    await asyncio.gather(
        _read_stream(proc.stdout, "stdout"),
        _read_stream(proc.stderr, "stderr"),
    )

    # 等待进程完成
    exit_code = await proc.wait()

    logger.info("命令执行完毕 [exec=%s], exit_code=%d", exec_id, exit_code)

    # 发送完成通知
    mqtt_client.publish_json(log_topic, CmdDonePayload(
        exec_id=exec_id,
        node_id=node_id,
        exit_code=exit_code,
    ))

    return exit_code
