/*
 * EdgeStelle — C++ Device SDK
 *
 * 依赖:
 *   - Eclipse Paho MQTT C++ (libpaho-mqttpp3)
 *   - nlohmann/json (header-only JSON 库)
 *   - libcurl (HTTP GET 模板)
 *
 * 编译 (Linux/嵌入式):
 *   g++ -std=c++17 -o edgestelle_device edgestelle_device.cpp \
 *       -lpaho-mqttpp3 -lpaho-mqtt3as -lcurl -lpthread
 */

#ifndef EDGESTELLE_DEVICE_SDK_HPP
#define EDGESTELLE_DEVICE_SDK_HPP

#include <string>
#include <vector>
#include <random>
#include <chrono>
#include <sstream>
#include <iostream>
#include <stdexcept>
#include <functional>

// ─── 第三方头文件 ───
#include <nlohmann/json.hpp>
#include <mqtt/async_client.h>
#include <curl/curl.h>

using json = nlohmann::json;

namespace edgestelle {

// ═════════════════════════════════════════════════════
//  配置
// ═════════════════════════════════════════════════════

struct DeviceConfig {
    std::string device_id       = "edge-cpp-001";
    std::string api_base_url    = "http://localhost:8000";
    std::string mqtt_broker_uri = "tcp://localhost:1883";
    std::string mqtt_username;
    std::string mqtt_password;
    std::string mqtt_topic_prefix = "iot/test/report";

    std::string mqtt_report_topic() const {
        return mqtt_topic_prefix + "/" + device_id;
    }
};

// ═════════════════════════════════════════════════════
//  HTTP 工具 (libcurl)
// ═════════════════════════════════════════════════════

namespace detail {

static size_t write_callback(void* contents, size_t size, size_t nmemb, std::string* out) {
    size_t total = size * nmemb;
    out->append(static_cast<char*>(contents), total);
    return total;
}

inline std::string http_get(const std::string& url) {
    CURL* curl = curl_easy_init();
    if (!curl) throw std::runtime_error("Failed to init curl");

    std::string response;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error(
            std::string("HTTP GET failed: ") + curl_easy_strerror(res)
        );
    }
    return response;
}

} // namespace detail

// ═════════════════════════════════════════════════════
//  模拟测试执行器
// ═════════════════════════════════════════════════════

class TestSimulator {
public:
    TestSimulator() : rng_(std::random_device{}()) {}

    /**
     * 根据指标名称生成模拟数值。
     */
    double simulate_metric(const std::string& name) {
        auto it = profiles_.find(name);
        const auto& p = (it != profiles_.end()) ? it->second : default_profile_;

        std::normal_distribution<double> dist(p.mean, p.stddev);
        double val = dist(rng_);
        val = std::max(p.min_val, std::min(p.max_val, val));
        return std::round(val * 100.0) / 100.0;
    }

    /**
     * 批量执行模拟测试。
     */
    json run_tests(const json& metrics) {
        json results = json::array();
        for (const auto& metric : metrics) {
            std::string name = metric.value("name", "unknown");
            double value = simulate_metric(name);

            json result = {
                {"name",  name},
                {"unit",  metric.value("unit", "")},
                {"value", value},
            };
            if (metric.contains("threshold_max")) result["threshold_max"] = metric["threshold_max"];
            if (metric.contains("threshold_min")) result["threshold_min"] = metric["threshold_min"];
            results.push_back(result);
        }
        return results;
    }

private:
    struct Profile { double mean, stddev, min_val, max_val; };

    std::mt19937 rng_;
    Profile default_profile_ = {50.0, 15.0, 0.0, 100.0};

    std::unordered_map<std::string, Profile> profiles_ = {
        {"cpu_temperature",   {48.0, 12.0, 25.0, 95.0}},
        {"memory_usage",      {55.0, 15.0,  5.0, 99.0}},
        {"network_latency",   {35.0, 25.0,  1.0, 500.0}},
        {"packet_loss_rate",  { 0.8,  1.2,  0.0, 15.0}},
        {"disk_usage",        {60.0, 20.0,  1.0, 99.0}},
        {"cpu_usage",         {40.0, 20.0,  0.0, 100.0}},
    };
};

// ═════════════════════════════════════════════════════
//  SDK 主类
// ═════════════════════════════════════════════════════

class EdgeStelleDevice {
public:
    explicit EdgeStelleDevice(const DeviceConfig& cfg) : config_(cfg), simulator_() {}

    /**
     * 从云端拉取测试模板。
     */
    json fetch_template(const std::string& template_id) {
        std::string url = config_.api_base_url + "/api/v1/templates/" + template_id;
        std::cout << "[SDK] 📥 拉取模板: " << url << std::endl;

        std::string body = detail::http_get(url);
        return json::parse(body);
    }

    /**
     * 根据模板执行测试并组装报告。
     */
    json execute_test(const json& tmpl) {
        const auto& metrics = tmpl["schema_definition"]["metrics"];
        std::cout << "[SDK] 🧪 执行测试 — " << metrics.size() << " 个指标" << std::endl;

        json results = simulator_.run_tests(metrics);

        // 检测异常
        json anomalies = json::array();
        for (const auto& r : results) {
            if (r.contains("threshold_max") && r["value"].get<double>() > r["threshold_max"].get<double>()) {
                anomalies.push_back(r["name"].get<std::string>() + " 超标");
            }
            if (r.contains("threshold_min") && r["value"].get<double>() < r["threshold_min"].get<double>()) {
                anomalies.push_back(r["name"].get<std::string>() + " 低于下限");
            }
        }

        // ISO 8601 时间戳
        auto now = std::chrono::system_clock::now();
        auto t   = std::chrono::system_clock::to_time_t(now);
        std::ostringstream ts;
        ts << std::put_time(std::gmtime(&t), "%Y-%m-%dT%H:%M:%SZ");

        return {
            {"template_id", tmpl["id"]},
            {"device_id",   config_.device_id},
            {"timestamp",   ts.str()},
            {"results",     results},
            {"has_anomaly", !anomalies.empty()},
            {"anomaly_summary", anomalies},
        };
    }

    /**
     * 通过 MQTT 发布测试报告。
     */
    void publish_report(const json& report) {
        std::string uri = config_.mqtt_broker_uri;
        std::string client_id = "device-" + config_.device_id;

        mqtt::async_client client(uri, client_id);

        auto connOpts = mqtt::connect_options_builder()
            .clean_session(true)
            .finalize();

        if (!config_.mqtt_username.empty()) {
            connOpts.set_user_name(config_.mqtt_username);
            connOpts.set_password(config_.mqtt_password);
        }

        std::cout << "[SDK] 📡 连接 MQTT: " << uri << std::endl;
        client.connect(connOpts)->wait();

        std::string topic   = config_.mqtt_report_topic();
        std::string payload = report.dump();

        auto msg = mqtt::make_message(topic, payload, 1 /* QoS */, false);
        client.publish(msg)->wait();

        std::cout << "[SDK] ✅ 报告已发布到 " << topic
                  << " (" << payload.size() << " bytes)" << std::endl;

        client.disconnect()->wait();
    }

    /**
     * 完整流程：拉取 → 测试 → 上报。
     */
    json run(const std::string& template_id) {
        auto tmpl  = fetch_template(template_id);
        auto report = execute_test(tmpl);
        publish_report(report);
        return report;
    }

private:
    DeviceConfig  config_;
    TestSimulator simulator_;
};

} // namespace edgestelle

#endif // EDGESTELLE_DEVICE_SDK_HPP
