package com.vehicle.someip.hal;

import android.car.Car;
import android.car.hardware.CarPropertyValue;
import android.car.hardware.property.CarPropertyManager;
import android.content.Context;
import android.util.Log;

/**
 * Bridge từ SOME/IP data → Android VehicleHAL / CarPropertyManager.
 *
 * Sử dụng Car API để set VehicleProperty, cho phép các app khác
 * (và CarService) đọc được dữ liệu từ SOME/IP.
 *
 * Requires: android.car.permission.CAR_SPEED, CAR_ENGINE_DETAILED
 */
public class VehicleHalBridge {

    private static final String TAG = "VehicleHalBridge";
    private static volatile VehicleHalBridge sInstance;

    private Car mCar;
    private CarPropertyManager mPropertyManager;
    private boolean mConnected = false;

    // VehicleProperty IDs (từ android.car.VehiclePropertyIds)
    private static final int PROP_SPEED        = 0x11600207; // PERF_VEHICLE_SPEED
    private static final int PROP_RPM          = 0x11400305; // ENGINE_RPM
    private static final int PROP_FUEL         = 0x11600309; // FUEL_LEVEL
    private static final int PROP_GEAR         = 0x11400400; // GEAR_SELECTION
    private static final int AREA_GLOBAL       = 0;

    public static VehicleHalBridge getInstance() {
        if (sInstance == null) {
            synchronized (VehicleHalBridge.class) {
                if (sInstance == null) sInstance = new VehicleHalBridge();
            }
        }
        return sInstance;
    }

    private VehicleHalBridge() {}

    public void connect(Context context) {
        if (mConnected) return;
        try {
            mCar = Car.createCar(context, null, Car.CAR_WAIT_TIMEOUT_WAIT_FOREVER,
                (car, ready) -> {
                    if (ready) {
                        mPropertyManager = (CarPropertyManager)
                            car.getCarManager(Car.PROPERTY_SERVICE);
                        mConnected = true;
                        Log.i(TAG, "Connected to CarService / VehicleHAL");
                    }
                });
        } catch (Exception e) {
            Log.e(TAG, "Failed to connect to CarService", e);
        }
    }

    public void disconnect() {
        if (mCar != null) {
            mCar.disconnect();
            mConnected = false;
        }
    }

    /**
     * Được gọi mỗi khi có data mới từ SOME/IP.
     * Cập nhật VehicleProperty để CarService và các app khác thấy.
     */
    public void onVehicleUpdate(float speedKmh, int rpm, int gear,
                                float fuelPercent, float throttle,
                                boolean brakeActive, float coolantTemp) {
        if (!mConnected || mPropertyManager == null) return;

        try {
            // Tốc độ: HAL expects m/s
            float speedMs = speedKmh / 3.6f;
            setFloatProperty(PROP_SPEED, speedMs);

            // RPM
            setFloatProperty(PROP_RPM, (float) rpm);

            // Fuel: HAL expects liters — giả lập tank 50L
            float fuelLiters = (fuelPercent / 100.0f) * 50.0f;
            setFloatProperty(PROP_FUEL, fuelLiters);

            // Gear: mapping our gear → VehicleGear enum
            setIntProperty(PROP_GEAR, mapGearToVehicleGear(gear));

        } catch (Exception e) {
            Log.w(TAG, "Failed to update VehicleProperty: " + e.getMessage());
        }
    }

    private void setFloatProperty(int propId, float value) {
        if (mPropertyManager == null) return;
        try {
            mPropertyManager.setProperty(Float.class, propId, AREA_GLOBAL, value);
            Log.v(TAG, String.format("Property 0x%08X = %.3f", propId, value));
        } catch (Exception e) {
            Log.w(TAG, "setFloatProperty 0x" + Integer.toHexString(propId) + " failed: " + e.getMessage());
        }
    }

    private void setIntProperty(int propId, int value) {
        if (mPropertyManager == null) return;
        try {
            mPropertyManager.setProperty(Integer.class, propId, AREA_GLOBAL, value);
        } catch (Exception e) {
            Log.w(TAG, "setIntProperty failed: " + e.getMessage());
        }
    }

    // Map our gear (0=P,1=R,2=N,3-8=D1-D5) → VehicleGear constants
    private int mapGearToVehicleGear(int gear) {
        switch (gear) {
            case 0:  return 4;   // GEAR_PARK
            case 1:  return 2;   // GEAR_REVERSE
            case 2:  return 8;   // GEAR_NEUTRAL
            case 3:  return 16;  // GEAR_FIRST
            case 4:  return 32;  // GEAR_SECOND
            case 5:  return 64;  // GEAR_THIRD
            case 6:  return 128; // GEAR_FOURTH
            case 7:  return 256; // GEAR_FIFTH
            default: return 16;
        }
    }
}
