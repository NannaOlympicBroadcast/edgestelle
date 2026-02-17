"""
EdgeStelle — MQTT 协议定义
包含 Topic 常量、Payload 模型和消息类型枚举
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# MQTT Topic 定义
# ============================================================

TOPIC_REGISTER = "system/register"
TOPIC_HEARTBEAT = "system/heartbeat"


def topic_cmd(node_id: str) -> str:
    """构造指定节点的命令下发 Topic"""
    return f"cmd/{node_id}"


def topic_log(node_id: str) -> str:
    """构造指定节点的日志上报 Topic"""
    return f"log/{node_id}"


# ============================================================
# 消息类型枚举
# ============================================================

class MsgType(str, Enum):
    """所有 MQTT 消息的类型标识"""
    # 注册流程
    REGISTER_REQ = "register_req"   # Agent → Master：注册请求
    REGISTER_ACK = "register_ack"   # Master → Agent：注册确认
    REGISTER_NAK = "register_nak"   # Master → Agent：注册拒绝

    # 心跳
    HEARTBEAT = "heartbeat"

    # 命令执行
    CMD = "cmd"                     # Master → Agent：下发命令
    LOG_LINE = "log_line"           # Agent → Master：一行日志
    CMD_DONE = "cmd_done"           # Agent → Master：命令执行完毕


# ============================================================
# Payload 模型
# ============================================================

class RegisterRequest(BaseModel):
    """Agent 发送的注册请求"""
    type: MsgType = MsgType.REGISTER_REQ
    node_name: str
    secret_key: str
    ip: str = ""
    timestamp: float = Field(default_factory=time.time)


class RegisterAck(BaseModel):
    """Master 回复的注册确认"""
    type: MsgType = MsgType.REGISTER_ACK
    node_id: str
    message: str = "注册成功"


class RegisterNak(BaseModel):
    """Master 回复的注册拒绝"""
    type: MsgType = MsgType.REGISTER_NAK
    reason: str = "密钥错误"


class HeartbeatPayload(BaseModel):
    """Agent 发送的心跳"""
    type: MsgType = MsgType.HEARTBEAT
    node_id: str
    status: str = "idle"           # idle / busy
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    timestamp: float = Field(default_factory=time.time)


class CommandPayload(BaseModel):
    """Master 下发的执行命令"""
    type: MsgType = MsgType.CMD
    exec_id: str                    # 执行记录 ID
    command: str                    # Shell 命令/脚本
    timestamp: float = Field(default_factory=time.time)


class LogLinePayload(BaseModel):
    """Agent 回传的单行日志"""
    type: MsgType = MsgType.LOG_LINE
    exec_id: str
    node_id: str
    stream: str = "stdout"          # stdout / stderr
    line: str = ""
    timestamp: float = Field(default_factory=time.time)


class CmdDonePayload(BaseModel):
    """Agent 回传的命令执行完毕通知"""
    type: MsgType = MsgType.CMD_DONE
    exec_id: str
    node_id: str
    exit_code: int = 0
    timestamp: float = Field(default_factory=time.time)
