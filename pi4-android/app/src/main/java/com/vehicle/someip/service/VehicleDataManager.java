package com.vehicle.someip.service;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Thread-safe vehicle data manager.
 * Nhận raw data từ SOME/IP JNI, normalize và phân phối cho observers.
 */
public class VehicleDataManager {

    private static final String TAG = "VehicleDataManager";
    private static volatile VehicleDataManager sInstance;

    private final Handler mMainHandler = new Handler(Looper.getMainLooper());
    private final CopyOnWriteArrayList<VehicleDataListener> mListeners = new CopyOnWriteArrayList<>();

    // Current vehicle state snapshot
    private volatile VehicleSnapshot mSnapshot = new VehicleSnapshot();

    // ─── Singleton ────────────────────────────────────────────────────────────
    public static VehicleDataManager getInstance() {
        if (sInstance == null) {
            synchronized (VehicleDataManager.class) {
                if (sInstance == null) sInstance = new VehicleDataManager();
            }
        }
        return sInstance;
    }

    private VehicleDataManager() {}

    // ─── Data model ───────────────────────────────────────────────────────────
    public static class VehicleSnapshot {
        public final float   speedKmh;
        public final int     rpm;
        public final int     gear;
        public final float   fuelPercent;
        public final float   throttle;
        public final boolean brakeActive;
        public final float   coolantTemp;
        public final long    timestampMs;

        public VehicleSnapshot() {
            this(0f, 800, 0, 100f, 0f, false, 25f);
        }

        public VehicleSnapshot(float speed, int rpm, int gear, float fuel,
                               float throttle, boolean brake, float coolant) {
            this.speedKmh    = speed;
            this.rpm         = rpm;
            this.gear        = gear;
            this.fuelPercent = fuel;
            this.throttle    = throttle;
            this.brakeActive = brake;
            this.coolantTemp = coolant;
            this.timestampMs = System.currentTimeMillis();
        }

        public String getGearLabel() {
            switch (gear) {
                case 0: return "P";
                case 1: return "R";
                case 2: return "N";
                default: return "D" + (gear - 2);
            }
        }

        @Override
        public String toString() {
            return String.format("Speed=%.1f km/h RPM=%d Gear=%s Fuel=%.1f%% Throttle=%.0f%% Brake=%b Coolant=%.1f°C",
                speedKmh, rpm, getGearLabel(), fuelPercent, throttle * 100, brakeActive, coolantTemp);
        }
    }

    // ─── Listener interface ───────────────────────────────────────────────────
    public interface VehicleDataListener {
        void onVehicleDataUpdated(VehicleSnapshot snapshot);
    }

    public void addListener(VehicleDataListener listener) {
        mListeners.add(listener);
    }

    public void removeListener(VehicleDataListener listener) {
        mListeners.remove(listener);
    }

    // ─── Called from SomeIpService (SOME/IP thread) ───────────────────────────
    public void onVehicleUpdate(float speedKmh, int rpm, int gear, float fuel,
                                float throttle, boolean brake, float coolant) {
        final VehicleSnapshot snapshot = new VehicleSnapshot(
            speedKmh, rpm, gear, fuel, throttle, brake, coolant);
        mSnapshot = snapshot;

        Log.v(TAG, snapshot.toString());

        // Dispatch trên main thread
        mMainHandler.post(() -> {
            for (VehicleDataListener listener : mListeners) {
                try {
                    listener.onVehicleDataUpdated(snapshot);
                } catch (Exception e) {
                    Log.e(TAG, "Listener error", e);
                }
            }
        });
    }

    public VehicleSnapshot getLatestSnapshot() {
        return mSnapshot;
    }
}
