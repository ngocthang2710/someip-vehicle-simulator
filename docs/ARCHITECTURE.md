# 🏗 ARCHITECTURE — SOME/IP Vehicle Simulator

## Luồng dữ liệu chi tiết

```
LAPTOP                              Pi4 (Android 15)
─────────────────────               ──────────────────────────────────────────

                                    ┌─────────────────────────────────────┐
                                    │  someip-vehicle-server (native bin) │
                                    │                                     │
                                    │  VehicleService.cpp                 │
                                    │  ┌──────────────────────────────┐  │
                                    │  │  simulationLoop() [100ms]    │  │
                                    │  │  - calc speed/rpm/fuel/gear  │  │
                                    │  │  - app_->notify(EVENT_SPEED) │  │
                                    │  │  - app_->notify(EVENT_RPM)   │  │
                                    │  └──────────────┬───────────────┘  │
                                    │                 │ vsomeip runtime  │
                                    └─────────────────┼────────────────--┘
                                                      │
                         UDP 30501 ◄──────────────────┤ SOME/IP Events
                         TCP 30502 ◄──────────────────┘ SOME/IP Methods
                              │
┌─────────────────────────────┴──────────────────────┐
│  someip_client.py                                   │
│  ┌──────────────────────────────────────────────┐  │
│  │  _recv_loop() [daemon thread]                │  │
│  │  → _handle_message()                         │  │
│  │    → parse EVENT_SPEED → VehicleData.speed   │  │
│  │    → parse EVENT_RPM   → VehicleData.rpm     │  │
│  │    → _notify_callbacks()                     │  │
│  └──────────────────────────────────────────────┘  │
│                         │                           │
│  set_throttle() ────────┼──► TCP → METHOD_SET_THROTTLE │
│  set_brake()    ────────┼──► TCP → METHOD_SET_BRAKE    │
│  emergency_stop()───────┼──► TCP → METHOD_EMERG_STOP   │
└─────────────────────────┴──────────────────────────┘
                          │
              vehicle_hmi.py (tkinter GUI)
              ├── GaugeCanvas.set_value(speed)
              ├── GaugeCanvas.set_value(rpm)
              ├── Labels: gear, fuel, coolant
              └── Controls: throttle/brake slider → set_throttle/set_brake


Pi4 Internal Flow:
─────────────────────────────────────────────────────────────────────

  someip-vehicle-server (C++ process, /vendor/bin/)
           │
           │ [JNI — libsomeip_bridge.so]
           ▼
  SomeIpBridge.java (JNI wrapper)
  → nativeRegisterCallback(callback)
  → callback.onVehicleUpdate(speed, rpm, gear, fuel, throttle, brake, temp)
           │
           ├──► VehicleDataManager.onVehicleUpdate()
           │         │
           │         ├──► [Main Thread] VehicleDataListener.onVehicleDataUpdated()
           │         │         └──► DashboardActivity.onVehicleDataUpdated()
           │         │                  ├── mSpeedGauge.setValue(speed)
           │         │                  ├── mRpmGauge.setValue(rpm)
           │         │                  └── mGearLabel.setText(gear)
           │
           └──► VehicleHalBridge.onVehicleUpdate()
                     │
                     └──► CarPropertyManager.setProperty(PROP_SPEED, speed_ms)
                          CarPropertyManager.setProperty(PROP_RPM, rpm)
                          CarPropertyManager.setProperty(PROP_FUEL, liters)
                          CarPropertyManager.setProperty(PROP_GEAR, gear_enum)
                                │
                                └──► CarService (system_server)
                                          └──► Any app using Car API
                                               can now read vehicle data
```

## Thread Model

| Thread          | Owner                 | Mô tả |
|-----------------|-----------------------|--------|
| main            | vsomeip app_->start() | vsomeip event loop, blocks |
| someip-init     | SomeIpService         | init + start vsomeip |
| someip-recv     | SomeIpClient (laptop) | nhận UDP packets |
| simulation      | VehicleService (C++)  | tính toán trạng thái xe 10Hz |
| Android Main    | DashboardActivity     | UI updates qua Handler |

## Memory Layout

```
/system/app/VehicleDashboard/
├── VehicleDashboard.apk
│   ├── classes.dex
│   ├── lib/arm64-v8a/
│   │   └── libsomeip_bridge.so    ← JNI bridge
│   └── res/

/vendor/bin/
└── someip-vehicle-server          ← Native SOME/IP server binary

/vendor/lib64/
├── libvsomeip3.so
└── libvsomeip3-cfg.so

/vendor/etc/
└── vsomeip_server.json            ← vsomeip configuration
```

## SELinux Contexts (sepolicy)

```
# vehicle_dashboard.te
type vehicle_dashboard, domain;
type vehicle_dashboard_exec, exec_type, vendor_file_type, file_type;

# Allow network access (SOME/IP UDP/TCP)
allow vehicle_dashboard self:udp_socket { create bind connect send_msg recv_msg };
allow vehicle_dashboard self:tcp_socket { create bind connect send_msg recv_msg };

# Allow Car API access
allow vehicle_dashboard carservice_service:service_manager { find };

# Binder to CarService
binder_call(vehicle_dashboard, carservice)
```

## vsomeip Version Compatibility

| Component          | Version  | Notes |
|--------------------|----------|-------|
| vsomeip            | 3.4.10   | COVESA/vsomeip |
| Boost              | 1.74+    | System/Thread/Log/Filesystem |
| Android NDK        | r26+     | C++17 support |
| SOME/IP Protocol   | 1.3      | PRS_SOMEIP_00053 |
| SOME/IP-SD         | 1.2      | PRS_SOMEIPSD_00301 |
