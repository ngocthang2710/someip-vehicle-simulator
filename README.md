<img width="771" height="551" alt="image" src="https://github.com/user-attachments/assets/7f7b8daa-95b1-4529-960d-8f1b511b092f" />

# 🚗 SOME/IP Vehicle Simulator — Pi4 (Android 15)

## Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                         LAPTOP (Client)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Python SOME/IP Client  │  HMI Dashboard  │  Diagnostic │   │
│  └──────────────┬──────────────────────────────────────────┘   │
└─────────────────┼───────────────────────────────────────────────┘
                  │  Ethernet / Wi-Fi (SOME/IP over UDP)
                  │  Service ID: 0x1234 / Instance: 0x0001
┌─────────────────┼───────────────────────────────────────────────┐
│                 ▼          Pi4 (Android 15)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              SOME/IP Server (vsomeip / Native C++)        │  │
│  │   - VehicleSpeedService  (Event 0x8001)                   │  │
│  │   - EngineRPMService     (Event 0x8002)                   │  │
│  │   - ThrottleService      (Method 0x0001)                  │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │  JNI Bridge                                │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │              VehicleHAL Service (HIDL/AIDL)              │  │
│  │   android.hardware.automotive.vehicle@2.0                  │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │  Binder IPC                                │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │            CarService / VehiclePropertyManager            │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │  CarAPI                                    │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │         VehicleDashboard App (Android UI)                 │  │
│  │   - Speedometer  - Tachometer  - Throttle Control         │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Cấu trúc thư mục

```
someip-vehicle-simulator/
├── README.md                          ← File này
├── docs/
│   ├── ARCHITECTURE.md                ← Chi tiết kiến trúc
│   ├── BUILD_GUIDE.md                 ← Hướng dẫn build đầy đủ
│   └── SOMEIP_SPEC.md                 ← SOME/IP service spec
│
├── laptop-client/                     ← Chạy trên Laptop
│   ├── src/
│   │   ├── someip_client.py           ← SOME/IP client chính
│   │   ├── vehicle_hmi.py             ← HMI dashboard (tkinter)
│   │   └── diagnostic_tool.py         ← Tool chẩn đoán
│   └── config/
│       └── vsomeip_client.json        ← vsomeip config
│
├── pi4-android/                       ← Tích hợp vào Android 15 AOSP
│   ├── Android.bp                     ← Build system
│   ├── jni/
│   │   ├── Android.bp
│   │   ├── someip_bridge.cpp          ← JNI: vsomeip ↔ Java
│   │   └── someip_bridge.h
│   └── app/
│       └── src/main/
│           ├── AndroidManifest.xml
│           ├── java/com/vehicle/someip/
│           │   ├── service/
│           │   │   ├── SomeIpService.java       ← Android Service
│           │   │   └── VehicleDataManager.java  ← Data layer
│           │   ├── hal/
│           │   │   └── VehicleHalBridge.java    ← HAL interface
│           │   └── ui/
│           │       ├── DashboardActivity.java   ← Main UI
│           │       └── GaugeView.java           ← Custom gauge view
│           └── res/
│               ├── layout/
│               │   └── activity_dashboard.xml
│               └── values/
│                   ├── strings.xml
│                   └── colors.xml
│
├── someip-server/                     ← SOME/IP Server (native, chạy trên Pi4)
│   ├── Android.bp
│   ├── src/
│   │   ├── main.cpp                   ← Entry point
│   │   ├── VehicleService.cpp         ← Service implementation
│   │   └── VehicleService.h
│   └── config/
│       └── vsomeip_server.json        ← vsomeip server config
│
└── scripts/
    ├── setup_laptop.sh                ← Cài đặt dependencies laptop
    ├── flash_pi4.sh                   ← Flash Android lên Pi4
    └── run_demo.sh                    ← Chạy demo end-to-end
```

## Quick Start

### 1. Laptop (Client)
```bash
cd laptop-client
pip install someip pyserial tkinter
python src/someip_client.py
```

### 2. Pi4 Android Build
```bash
# Trong AOSP source tree
source build/envsetup.sh
lunch aosp_rpi4-userdebug
# Copy project vào đúng path
cp -r pi4-android/ packages/apps/VehicleSimulator/
cp -r someip-server/ vendor/vehicle/someip-server/
mma -j$(nproc)
```

Xem `docs/BUILD_GUIDE.md` để biết hướng dẫn chi tiết.
