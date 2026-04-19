package com.vehicle.someip.service;

/**
 * JNI wrapper cho vsomeip C++ library.
 * Cầu nối giữa native SOME/IP layer và Android Java service.
 */
public class SomeIpBridge {

    static {
        System.loadLibrary("someip_bridge");
    }

    /**
     * Callback interface — nhận vehicle data từ native simulation loop.
     */
    public interface VehicleDataCallback {
        /**
         * @param speedKmh      Tốc độ (km/h)
         * @param rpm           Vòng tua động cơ
         * @param gear          Số (0=P, 1=R, 2=N, 3-8=D1-D5)
         * @param fuelPercent   Mức nhiên liệu (0-100%)
         * @param throttle      Vị trí ga (0.0-1.0)
         * @param brakeActive   Phanh đang đạp
         * @param coolantTemp   Nhiệt độ nước làm mát (°C)
         */
        void onVehicleUpdate(float speedKmh, int rpm, int gear,
                             float fuelPercent, float throttle,
                             boolean brakeActive, float coolantTemp);
    }

    // ─── Native methods ───────────────────────────────────────────────────────
    public native boolean nativeInit(String configPath);
    public native void    nativeStart();
    public native void    nativeStop();
    public native boolean nativeSetThrottle(float throttle);
    public native boolean nativeSetBrake(float brake);
    public native boolean nativeEmergencyStop();
    public native void    nativeRegisterCallback(VehicleDataCallback callback);

    // ─── Java convenience wrappers ────────────────────────────────────────────
    private VehicleDataCallback mCallback;
    private boolean mInitialized = false;

    public boolean initialize(String vsomeipConfigPath) {
        mInitialized = nativeInit(vsomeipConfigPath);
        return mInitialized;
    }

    public void start() {
        if (mInitialized) nativeStart();
    }

    public void stop() {
        if (mInitialized) nativeStop();
    }

    public void registerCallback(VehicleDataCallback callback) {
        mCallback = callback;
        nativeRegisterCallback(callback);
    }

    public boolean setThrottle(float throttle) {
        return mInitialized && nativeSetThrottle(throttle);
    }

    public boolean setBrake(float brake) {
        return mInitialized && nativeSetBrake(brake);
    }

    public boolean emergencyStop() {
        return mInitialized && nativeEmergencyStop();
    }

    public boolean isInitialized() {
        return mInitialized;
    }
}
