"""
EdgeStelle 设备端 SDK (Python 模拟版)

完整工作流:
  1. 通过 HTTP GET 从云端拉取测试模板
  2. 解析模板中的指标定义
  3. 执行模拟测试 (生成合理随机数据)
  4. 将结果打包为 JSON
  5. 通过 MQTT 发布到 iot/test/report/{device_id}
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import requests

from .device_config import DeviceConfig
from .test_runner import run_simulated_tests

logger = logging.getLogger("edgestelle.device_sdk")


class EdgeStelleSDK:
    """设备端 SDK 主类。"""

    def __init__(self, config: DeviceConfig | None = None):
        self.config = config or DeviceConfig()
        self._mqtt_client: mqtt.Client | None = None

    # ────────────── MQTT ──────────────

    def _init_mqtt(self) -> mqtt.Client:
        """初始化并连接 MQTT 客户端。"""
        client_id = f"device-{self.config.device_id}-{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )

        if self.config.mqtt_username:
            client.username_pw_set(
                self.config.mqtt_username, self.config.mqtt_password
            )

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("✅ MQTT 已连接 — broker=%s:%d",
                            self.config.mqtt_broker_host,
                            self.config.mqtt_broker_port)
            else:
                logger.error("❌ MQTT 连接失败 — rc=%d", rc)

        def on_publish(client, userdata, mid, rc=None, properties=None):
            logger.info("📤 报告已发布 — mid=%s", mid)

        client.on_connect = on_connect
        client.on_publish = on_publish

        client.connect(
            self.config.mqtt_broker_host,
            self.config.mqtt_broker_port,
            keepalive=60,
        )
        client.loop_start()
        return client

    # ────────────── 模板拉取 ──────────────

    def fetch_template(self, template_id: str) -> dict:
        """
        通过 HTTP GET 从云端拉取测试模板。

        Parameters
        ----------
        template_id : str
            模板 UUID。

        Returns
        -------
        dict
            完整的模板 JSON。
        """
        url = f"{self.config.api_base_url}/api/v1/templates/{template_id}"
        logger.info("📥 正在拉取模板 — %s", url)

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        template = resp.json()
        logger.info("✅ 模板已获取 — name=%s version=%s",
                     template.get("name"), template.get("version"))
        return template

    # ────────────── 测试执行 ──────────────

    def execute_test(self, template: dict) -> dict:
        """
        根据模板定义执行模拟测试并组装报告 JSON。

        Parameters
        ----------
        template : dict
            从云端拉取的完整模板。

        Returns
        -------
        dict
            可通过 MQTT 发布的报告 payload。
        """
        schema_def = template.get("schema_definition", {})
        metrics = schema_def.get("metrics", [])

        if not metrics:
            raise ValueError("模板中未定义任何测试指标")

        logger.info("🧪 开始执行测试 — %d 个指标", len(metrics))
        results = run_simulated_tests(metrics)

        report = {
            "report_id": str(uuid.uuid4()),
            "template_id": template["id"],
            "device_id": self.config.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

        # 简单标记是否有异常
        anomalies = []
        for r in results:
            if r.get("threshold_max") is not None and r["value"] > r["threshold_max"]:
                anomalies.append(f'{r["name"]}={r["value"]}{r["unit"]} (> {r["threshold_max"]})')
            if r.get("threshold_min") is not None and r["value"] < r["threshold_min"]:
                anomalies.append(f'{r["name"]}={r["value"]}{r["unit"]} (< {r["threshold_min"]})')

        report["has_anomaly"] = len(anomalies) > 0
        report["anomaly_summary"] = anomalies

        logger.info("📊 测试完成 — 异常指标: %s",
                     anomalies if anomalies else "无")
        return report

    # ────────────── 报告上报 ──────────────

    def publish_report(self, report: dict) -> None:
        """
        通过 MQTT 发布测试报告。

        Parameters
        ----------
        report : dict
            测试报告 JSON。
        """
        if self._mqtt_client is None:
            self._mqtt_client = self._init_mqtt()
            time.sleep(1)  # 等待连接建立

        topic = self.config.mqtt_report_topic
        payload = json.dumps(report, ensure_ascii=False)

        result = self._mqtt_client.publish(
            topic, payload, qos=1, retain=False
        )
        logger.info("📡 发布到 %s — payload_size=%d bytes",
                     topic, len(payload))
        result.wait_for_publish(timeout=10)

    # ────────────── 完整流程 ──────────────

    def run(self, template_id: str) -> dict:
        """
        完整工作流：拉取模板 → 执行测试 → 上报结果。

        Parameters
        ----------
        template_id : str
            要执行的模板 UUID。

        Returns
        -------
        dict
            发布的报告内容。
        """
        template = self.fetch_template(template_id)
        report = self.execute_test(template)
        self.publish_report(report)
        return report

    def disconnect(self) -> None:
        """断开 MQTT 连接。"""
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            logger.info("🔌 MQTT 已断开")


# ────────────── CLI 入口 ──────────────

def main():
    """命令行入口：python -m device_sdk.python.sdk <template_id>"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    )

    if len(sys.argv) < 2:
        print("用法: python -m device_sdk.python.sdk <template_id>")
        sys.exit(1)

    template_id = sys.argv[1]
    config = DeviceConfig()
    sdk = EdgeStelleSDK(config)

    try:
        report = sdk.run(template_id)
        print("\n✅ 测试报告已上报:\n")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("❌ 执行失败: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        sdk.disconnect()


if __name__ == "__main__":
    main()
