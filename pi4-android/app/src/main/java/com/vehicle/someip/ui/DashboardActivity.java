package com.vehicle.someip.ui;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Bundle;
import android.os.IBinder;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.SeekBar;
import android.widget.TextView;
import android.util.Log;

import com.vehicle.someip.R;
import com.vehicle.someip.service.SomeIpService;
import com.vehicle.someip.service.VehicleDataManager;

/**
 * Main dashboard UI — hiển thị realtime vehicle data từ SOME/IP.
 */
public class DashboardActivity extends Activity
        implements VehicleDataManager.VehicleDataListener {

    private static final String TAG = "DashboardActivity";

    // Views
    private GaugeView mSpeedGauge;
    private GaugeView mRpmGauge;
    private TextView  mGearLabel;
    private TextView  mSpeedText;
    private TextView  mRpmText;
    private TextView  mCoolantText;
    private ProgressBar mFuelBar;
    private TextView  mFuelText;
    private TextView  mStatusText;
    private SeekBar   mThrottleBar;
    private SeekBar   mBrakeBar;
    private Button    mEmergencyBtn;
    private TextView  mConnectionStatus;

    // Service binding
    private SomeIpService mService;
    private boolean mBound = false;

    private final ServiceConnection mConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            SomeIpService.LocalBinder lb = (SomeIpService.LocalBinder) binder;
            mService = lb.getService();
            mBound = true;
            updateConnectionStatus("SOME/IP Connected ✓");
            Log.i(TAG, "Bound to SomeIpService");
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            mBound = false;
            updateConnectionStatus("SOME/IP Disconnected ✗");
        }
    };

    // ─── Lifecycle ────────────────────────────────────────────────────────────
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_dashboard);

        initViews();
        setupControls();

        // Start & bind service
        Intent serviceIntent = new Intent(this, SomeIpService.class);
        startForegroundService(serviceIntent);
        bindService(serviceIntent, mConnection, Context.BIND_AUTO_CREATE);
    }

    @Override
    protected void onResume() {
        super.onResume();
        VehicleDataManager.getInstance().addListener(this);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VehicleDataManager.getInstance().removeListener(this);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mBound) {
            unbindService(mConnection);
            mBound = false;
        }
    }

    // ─── View initialization ──────────────────────────────────────────────────
    private void initViews() {
        mSpeedGauge       = findViewById(R.id.gauge_speed);
        mRpmGauge         = findViewById(R.id.gauge_rpm);
        mGearLabel        = findViewById(R.id.tv_gear);
        mSpeedText        = findViewById(R.id.tv_speed_value);
        mRpmText          = findViewById(R.id.tv_rpm_value);
        mCoolantText      = findViewById(R.id.tv_coolant);
        mFuelBar          = findViewById(R.id.pb_fuel);
        mFuelText         = findViewById(R.id.tv_fuel_value);
        mStatusText       = findViewById(R.id.tv_status);
        mThrottleBar      = findViewById(R.id.sb_throttle);
        mBrakeBar         = findViewById(R.id.sb_brake);
        mEmergencyBtn     = findViewById(R.id.btn_emergency);
        mConnectionStatus = findViewById(R.id.tv_connection_status);

        // Configure gauges
        mSpeedGauge.setMaxValue(200f);
        mSpeedGauge.setUnit("km/h");
        mSpeedGauge.setLabel("SPEED");

        mRpmGauge.setMaxValue(8000f);
        mRpmGauge.setUnit("RPM");
        mRpmGauge.setLabel("ENGINE");
        mRpmGauge.setRedZoneStart(6000f);

        mFuelBar.setMax(100);
    }

    private void setupControls() {
        // Throttle
        mThrottleBar.setMax(100);
        mThrottleBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar sb, int progress, boolean fromUser) {
                if (fromUser && mBound) mService.setThrottle(progress / 100.0f);
            }
            @Override public void onStartTrackingTouch(SeekBar sb) {}
            @Override public void onStopTrackingTouch(SeekBar sb) {}
        });

        // Brake
        mBrakeBar.setMax(100);
        mBrakeBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar sb, int progress, boolean fromUser) {
                if (fromUser && mBound) mService.setBrake(progress / 100.0f);
            }
            @Override public void onStartTrackingTouch(SeekBar sb) {}
            @Override public void onStopTrackingTouch(SeekBar sb) {}
        });

        // Emergency stop
        mEmergencyBtn.setOnClickListener(v -> {
            if (mBound) {
                mService.emergencyStop();
                mThrottleBar.setProgress(0);
                mBrakeBar.setProgress(100);
            }
        });
    }

    // ─── VehicleDataListener ──────────────────────────────────────────────────
    @Override
    public void onVehicleDataUpdated(VehicleDataManager.VehicleSnapshot s) {
        // Đã được dispatch trên main thread bởi VehicleDataManager
        mSpeedGauge.setValue(s.speedKmh);
        mRpmGauge.setValue(s.rpm);
        mGearLabel.setText(s.getGearLabel());
        mSpeedText.setText(String.format("%.1f", s.speedKmh));
        mRpmText.setText(String.valueOf(s.rpm));
        mCoolantText.setText(String.format("%.1f°C", s.coolantTemp));
        mFuelBar.setProgress((int) s.fuelPercent);
        mFuelText.setText(String.format("%.1f%%", s.fuelPercent));

        String status = String.format("Speed: %.1f | RPM: %d | %s | Fuel: %.1f%%",
            s.speedKmh, s.rpm, s.getGearLabel(), s.fuelPercent);
        mStatusText.setText(status);

        // Visual brake indicator
        mEmergencyBtn.setAlpha(s.brakeActive ? 1.0f : 0.5f);
    }

    private void updateConnectionStatus(String status) {
        runOnUiThread(() -> mConnectionStatus.setText(status));
    }
}
