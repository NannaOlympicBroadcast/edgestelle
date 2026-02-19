# EdgeStelle C++ Device SDK — CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
project(edgestelle_device_sdk LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── 依赖查找 ──
find_package(PahoMqttCpp REQUIRED)
find_package(CURL REQUIRED)

# nlohmann/json (header-only，若已通过包管理安装可使用 find_package)
# 如未安装，可将 json.hpp 放入 include/ 目录
find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
    include(FetchContent)
    FetchContent_Declare(json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG        v3.11.3
    )
    FetchContent_MakeAvailable(json)
endif()

# ── 可执行文件 ──
add_executable(edgestelle_device main.cpp)

target_include_directories(edgestelle_device PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(edgestelle_device PRIVATE
    PahoMqttCpp::paho-mqttpp3
    CURL::libcurl
    nlohmann_json::nlohmann_json
)
