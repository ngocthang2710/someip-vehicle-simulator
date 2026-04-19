package com.vehicle.someip.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.util.Log;
import androidx.annotation.Nullable;

/**
 * Android Foreground Service — quản lý lifecycle của SOME/IP bridge.
 * Start khi boot, stop khi app bị kill.
 */
public class SomeIpService extends Service
        implements SomeIpBridge.VehicleDataCallback {

    private static final String TAG = "SomeIpService";
    private static final String VSOMEIP_CONFIG = "/vendor/etc/vsomeip_server.json";
    private static final String CHANNEL_ID = "vehicle_someip";
    private static final int NOTIF_ID = 1001;

    private SomeIpBridge mBridge;
    private final LocalBinder mBinder = new LocalBinder();

    // ─── Binder ───────────────────────────────────────────────────────────────
    public class LocalBinder extends Binder {
        public SomeIpService getService() { return SomeIpService.this; }
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) { return mBinder; }

    // ─── Lifecycle ────────────────────────────────────────────────────────────
    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "SomeIpService created");
        createNotificationChannel();
        startForeground(NOTIF_ID, buildNotification("Initializing SOME/IP..."));

        mBridge = new SomeIpBridge();
        mBridge.registerCallback(this);

        // Init trên background thread để không block main thread
        new Thread(this::initAndStart, "someip-init").start();
    }

    private void initAndStart() {
        Log.i(TAG, "Initializing vsomeip with config: " + VSOMEIP_CONFIG);
        boolean ok = mBridge.initialize(VSOMEIP_CONFIG);
        if (ok) {
            Log.i(TAG, "vsomeip initialized — starting service");
            updateNotification("SOME/IP Active ✓");
            mBridge.start();  // blocks
        } else {
            Log.e(TAG, "vsomeip initialization FAILED");
            updateNotification("SOME/IP Error ✗");
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "ACTION_STOP".equals(intent.getAction())) {
            Log.i(TAG, "Stop action received");
            stopSelf();
            return START_NOT_STICKY;
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.i(TAG, "SomeIpService destroyed — stopping vsomeip");
        if (mBridge != null) mBridge.stop();
    }

    // ─── SomeIpBridge.VehicleDataCallback ────────────────────────────────────
    @Override
    public void onVehicleUpdate(float speedKmh, int rpm, int gear,
                                float fuelPercent, float throttle,
                                boolean brakeActive, float coolantTemp) {
        // Forward to VehicleDataManager (thread-safe dispatcher)
        VehicleDataManager.getInstance().onVehicleUpdate(
            speedKmh, rpm, gear, fuelPercent, throttle, brakeActive, coolantTemp);

        // Update HAL nếu cần
        VehicleHalBridge.getInstance().onVehicleUpdate(
            speedKmh, rpm, gear, fuelPercent, throttle, brakeActive, coolantTemp);
    }

    // ─── Public control API ───────────────────────────────────────────────────
    public void setThrottle(float throttle) {
        if (mBridge != null) mBridge.setThrottle(throttle);
    }

    public void setBrake(float brake) {
        if (mBridge != null) mBridge.setBrake(brake);
    }

    public void emergencyStop() {
        if (mBridge != null) mBridge.emergencyStop();
    }

    // ─── Notification helpers ─────────────────────────────────────────────────
    private void createNotificationChannel() {
        NotificationChannel ch = new NotificationChannel(
            CHANNEL_ID, "Vehicle SOME/IP Service",
            NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("Manages SOME/IP vehicle data connection");
        getSystemService(NotificationManager.class).createNotificationChannel(ch);
    }

    private Notification buildNotification(String text) {
        return new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Vehicle Dashboard")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build();
    }

    private void updateNotification(String text) {
        Notification n = buildNotification(text);
        getSystemService(NotificationManager.class).notify(NOTIF_ID, n);
    }
}
