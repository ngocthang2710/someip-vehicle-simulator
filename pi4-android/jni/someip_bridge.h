#pragma once
// someip_bridge.h — JNI bridge giữa vsomeip (C++) và Java Android Service
// Đặt tại: packages/apps/VehicleDashboard/jni/someip_bridge.h

#include <jni.h>
#include <string>

#ifdef __cplusplus
extern "C" {
#endif

// ─── JNI exports ─────────────────────────────────────────────────────────────
// Package: com.vehicle.someip.service
// Class:   SomeIpBridge (native methods)

JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeInit(
    JNIEnv* env, jobject thiz, jstring config_path);

JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeStart(
    JNIEnv* env, jobject thiz);

JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeStop(
    JNIEnv* env, jobject thiz);

// Commands gửi xuống server (hoặc gọi local nếu cùng process)
JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeSetThrottle(
    JNIEnv* env, jobject thiz, jfloat throttle);

JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeSetBrake(
    JNIEnv* env, jobject thiz, jfloat brake);

JNIEXPORT jboolean JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeEmergencyStop(
    JNIEnv* env, jobject thiz);

// Đăng ký Java callback để nhận event data
JNIEXPORT void JNICALL
Java_com_vehicle_someip_service_SomeIpBridge_nativeRegisterCallback(
    JNIEnv* env, jobject thiz, jobject callback);

#ifdef __cplusplus
}
#endif
