/*
 * EdgeStelle — C++ Device SDK 示例程序
 *
 * 编译:
 *   g++ -std=c++17 -o edgestelle_device main.cpp \
 *       -lpaho-mqttpp3 -lpaho-mqtt3as -lcurl -lpthread
 *
 * 运行:
 *   ./edgestelle_device <template_id> [device_id] [api_url] [mqtt_uri]
 */

#include "edgestelle_device.hpp"
#include <iostream>
#include <cstdlib>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "用法: " << argv[0]
                  << " <template_id> [device_id] [api_url] [mqtt_uri]"
                  << std::endl;
        return 1;
    }

    std::string template_id = argv[1];

    edgestelle::DeviceConfig cfg;
    if (argc >= 3) cfg.device_id       = argv[2];
    if (argc >= 4) cfg.api_base_url    = argv[3];
    if (argc >= 5) cfg.mqtt_broker_uri = argv[4];

    // 也可从环境变量读取
    if (const char* env = std::getenv("DEVICE_ID"))        cfg.device_id       = env;
    if (const char* env = std::getenv("API_BASE_URL"))     cfg.api_base_url    = env;
    if (const char* env = std::getenv("MQTT_BROKER_URI"))  cfg.mqtt_broker_uri = env;

    try {
        edgestelle::EdgeStelleDevice device(cfg);
        auto report = device.run(template_id);
        std::cout << "\n✅ 测试报告:\n"
                  << report.dump(2) << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "❌ 错误: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
