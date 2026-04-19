#include "someip_bridge.h"
#include "../../../someip-server/src/VehicleService.h"

#include <android/log.h>
#include <memory>
#include <thread>
#include <mutex>

#define LOG_TAG "SomeIpBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ─── Globals ──────────────────────────────────────────────────────────────────
static std::unique_ptr<VehicleService>  g_vehicle_service;
static JavaVM*                          g_jvm = nullptr;
static jobject                          g_callback_obj = nullptr;
static jmethodID                        g_on_speed_method = nullptr;
static jmethodID                        g_on_rpm_method   = nullptr;
static jmethodID                        g_on_update_method = nullptr;
static std::mutex                       g_callback_mutex;

// ─── JVM setup ───────────────────────────────────────────────────────────────
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* /*reserved*/) {
    g_jvm = vm;
    LOGI("JNI_OnLoad: SomeIpBridge loaded");
    return JNI_VERSION_1_6;
}

// ─── Helper: attach current thread ───────────────────────────────────────────
static JNIEnv* attachCurrentThread() {
    JNIEnv* env = nullptr;
    if (g_jvm->AttachCurrentThread(&env, nullptr) != JNI_OK) {
        LOGE("Failed to attach thread to JVM");
        return nullptr;
    }
    return env;
}

// ─── Callback dispatcher ──────────────────────────────────────────────────────
// Được gọi từ simulation thread (C++) → gọi lên Java
static void dispatchVehicleUpdate(const VehicleState& state) {
    std::lock_guard<std::mutex> lock(g_callback_mutex);
    if (!g_callback_obj || !g_on_update_method) return;

    JNIEnv* env = attachCurrentThread();
    if (!env) return;

    // Gọi Java: onVehicleUpdate(float speed, int rpm, int gear, float fuel,
    //                           float throttle, boolean brake, float coolant)
    env->CallVoidMethod(
        g_callback_obj,
        g_on_update_method,
        static_cast<jfloat>(state.speed_kmh),
        static_cast<jint>(state.engine_rpm),
        static_cast<jint>(state.gear),
        static_cast<jfloat>(state.fuel_percent),
        static_cast<jfloat>(state.throttle_pos),
        static_cast<jboolean>(state.brake_active),
        static_cast<jfloat>(state.coolant_temp)
    );

    if (env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
    }
}

// ─── JNI: nativeInit ──────────────────────────────────────────────────────────
JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeInit(
    JNIEnv* env, jobject /*thiz*/, jstring config_path)
{
    const char* path = env->GetStringUTFChars(config_path, nullptr);
    LOGI("nativeInit: config=%s", path);

    // Set vsomeip config path
    setenv("VSOMEIP_CONFIGURATION", path, 1);
    env->ReleaseStringUTFChars(config_path, path);

    g_vehicle_service = std::make_unique<VehicleService>();
    bool ok = g_vehicle_service->init();

    if (ok) {
        LOGI("VehicleService initialized successfully");
    } else {
        LOGE("VehicleService initialization FAILED");
        g_vehicle_service.reset();
    }
    return static_cast<jboolean>(ok);
}

// ─── JNI: nativeStart ────────────────────────────────────────────────────────
JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeStart(
    JNIEnv* /*env*/, jobject /*thiz*/)
{
    if (!g_vehicle_service) {
        LOGE("nativeStart: service not initialized");
        return;
    }
    LOGI("Starting VehicleService...");
    // start() blocks, phải chạy trong thread riêng
    std::thread([]() {
        g_vehicle_service->start();
    }).detach();
}

// ─── JNI: nativeStop ─────────────────────────────────────────────────────────
JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeStop(
    JNIEnv* /*env*/, jobject /*thiz*/)
{
    if (g_vehicle_service) {
        LOGI("Stopping VehicleService...");
        g_vehicle_service->stop();
    }
}

// ─── JNI: nativeSetThrottle ──────────────────────────────────────────────────
JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeSetThrottle(
    JNIEnv* /*env*/, jobject /*thiz*/, jfloat throttle)
{
    if (!g_vehicle_service) return JNI_FALSE;
    // Direct call (same process)
    float t = std::max(0.0f, std::min(1.0f, static_cast<float>(throttle)));
    g_vehicle_service->updateSpeed(g_vehicle_service->getState().speed_kmh);
    LOGI("Throttle set: %.2f", t);
    return JNI_TRUE;
}

// ─── JNI: nativeSetBrake ─────────────────────────────────────────────────────
JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeSetBrake(
    JNIEnv* /*env*/, jobject /*thiz*/, jfloat brake)
{
    if (!g_vehicle_service) return JNI_FALSE;
    g_vehicle_service->updateBrakeStatus(brake > 0.1f);
    LOGI("Brake: %.2f", static_cast<float>(brake));
    return JNI_TRUE;
}

// ─── JNI: nativeEmergencyStop ────────────────────────────────────────────────
JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeEmergencyStop(
    JNIEnv* /*env*/, jobject /*thiz*/)
{
    if (!g_vehicle_service) return JNI_FALSE;
    LOGI("EMERGENCY STOP!");
    g_vehicle_service->updateBrakeStatus(true);
    return JNI_TRUE;
}

// ─── JNI: nativeRegisterCallback ─────────────────────────────────────────────
JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeRegisterCallback(
    JNIEnv* env, jobject /*thiz*/, jobject callback)
{
    std::lock_guard<std::mutex> lock(g_callback_mutex);

    // Release old ref
    if (g_callback_obj) {
        env->DeleteGlobalRef(g_callback_obj);
        g_callback_obj = nullptr;
    }

    if (!callback) return;

    g_callback_obj = env->NewGlobalRef(callback);
    jclass cls = env->GetObjectClass(g_callback_obj);

    // Tìm method: void onVehicleUpdate(float,int,int,float,float,boolean,float)
    g_on_update_method = env->GetMethodID(
        cls, "onVehicleUpdate", "(FIIFFFZF)V");

    if (!g_on_update_method) {
        LOGE("onVehicleUpdate method not found in callback class");
        env->DeleteGlobalRef(g_callback_obj);
        g_callback_obj = nullptr;
    } else {
        LOGI("Callback registered successfully");
    }
}
