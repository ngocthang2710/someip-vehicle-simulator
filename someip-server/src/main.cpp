#include "VehicleService.h"
#include <android/log.h>
#include <signal.h>
#include <iostream>

#define LOG_TAG "VehicleServer"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

static std::shared_ptr<VehicleService> g_service;

static void signal_handler(int signum) {
    LOGI("Signal %d received — stopping server", signum);
    if (g_service) g_service->stop();
    exit(0);
}

int main(int argc, char** argv) {
    LOGI("=================================================");
    LOGI("  SOME/IP Vehicle Server v1.0 — Android 15/Pi4  ");
    LOGI("=================================================");

    signal(SIGTERM, signal_handler);
    signal(SIGINT,  signal_handler);

    g_service = std::make_shared<VehicleService>();

    // Register command callbacks
    g_service->setThrottleCallback([](float throttle) {
        LOGI("[CMD] Throttle set to %.2f%%", throttle * 100.0f);
    });
    g_service->setBrakeCallback([](float brake) {
        LOGI("[CMD] Brake applied: %.2f%%", brake * 100.0f);
    });

    if (!g_service->init()) {
        LOGI("Failed to initialize VehicleService");
        return 1;
    }

    LOGI("Starting vehicle simulation...");
    g_service->start();  // Blocks until stop() is called

    return 0;
}
