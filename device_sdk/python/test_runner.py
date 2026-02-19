"""
硬件测试模拟器 — 根据模板指标定义生成合理的模拟测试数据。

在真实设备上，此模块应替换为实际的硬件传感器读取逻辑。
"""

import random
from typing import Any


# ── 各指标的模拟参数 (均值, 标准差, 上下限裁剪) ──
_SIMULATION_PROFILES: dict[str, dict[str, float]] = {
    "cpu_temperature": {"mean": 48.0, "std": 12.0, "min": 25.0, "max": 95.0},
    "memory_usage": {"mean": 55.0, "std": 15.0, "min": 5.0, "max": 99.0},
    "network_latency": {"mean": 35.0, "std": 25.0, "min": 1.0, "max": 500.0},
    "packet_loss_rate": {"mean": 0.8, "std": 1.2, "min": 0.0, "max": 15.0},
    "disk_usage": {"mean": 60.0, "std": 20.0, "min": 1.0, "max": 99.0},
    "cpu_usage": {"mean": 40.0, "std": 20.0, "min": 0.0, "max": 100.0},
    "battery_level": {"mean": 70.0, "std": 25.0, "min": 0.0, "max": 100.0},
    "signal_strength": {"mean": -55.0, "std": 15.0, "min": -100.0, "max": -10.0},
}

# 未知指标的默认分布
_DEFAULT_PROFILE = {"mean": 50.0, "std": 15.0, "min": 0.0, "max": 100.0}


def simulate_metric(metric_name: str) -> float:
    """
    根据指标名称生成一个符合正态分布的模拟值。

    偶尔会产生超出阈值的异常值，以测试 AI Agent 的分析能力。
    """
    profile = _SIMULATION_PROFILES.get(metric_name, _DEFAULT_PROFILE)

    value = random.gauss(profile["mean"], profile["std"])
    value = max(profile["min"], min(profile["max"], value))
    return round(value, 2)


def run_simulated_tests(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    遍历模板中的指标列表，为每个指标生成模拟数据。

    Parameters
    ----------
    metrics : list[dict]
        来自 test_template.schema_definition.metrics 的指标定义列表。
        每个元素至少包含 ``{"name": "xxx", "unit": "xxx"}``。

    Returns
    -------
    list[dict]
        填充了 ``value`` 字段的指标结果列表。
    """
    results = []
    for metric in metrics:
        name = metric.get("name", "unknown")
        value = simulate_metric(name)
        results.append(
            {
                "name": name,
                "unit": metric.get("unit", ""),
                "value": value,
                "threshold_max": metric.get("threshold_max"),
                "threshold_min": metric.get("threshold_min"),
            }
        )
    return results
