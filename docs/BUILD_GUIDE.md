# 📘 BUILD GUIDE — SOME/IP Vehicle Simulator

## Prerequisites

### Laptop (Ubuntu 20.04+ hoặc Windows WSL2)
```
- Python 3.10+
- vsomeip 3.x (optional nếu dùng pure Python)
- pip packages: someip, tkinter, pyserial
```

### Pi4 Android 15 Build Machine
```
- Ubuntu 22.04 LTS (khuyến nghị)
- RAM: tối thiểu 32GB (64GB khuyến nghị)
- Disk: 300GB+ free
- Android 15 AOSP source (android-15.0.0_r1 hoặc mới hơn)
- Raspberry Pi 4 BSP patch (KonstaKANG hoặc LineageOS rpi4 tree)
```

---

## PHẦN 1: Setup Laptop Client

### Bước 1.1 — Cài dependencies
```bash
cd someip-vehicle-simulator/laptop-client
chmod +x ../scripts/setup_laptop.sh
../scripts/setup_laptop.sh
```

Hoặc thủ công:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-tk libboost-all-dev cmake
pip3 install someip==0.4.0
```

### Bước 1.2 — Cấu hình IP
Chỉnh file `laptop-client/config/vsomeip_client.json`:
```json
{
  "unicast": "192.168.1.100",   // IP laptop
  ...
  "routing": {
    "host": "192.168.1.200"    // IP Pi4
  }
}
```

### Bước 1.3 — Chạy client
```bash
python3 src/someip_client.py        # CLI mode
python3 src/vehicle_hmi.py          # GUI mode
python3 src/diagnostic_tool.py      # Diagnostic
```

---

## PHẦN 2: Build Android 15 cho Pi4

### Bước 2.1 — Lấy AOSP source

```bash
# Tạo thư mục làm việc
mkdir -p ~/android-rpi4 && cd ~/android-rpi4

# Init repo (Android 15)
repo init -u https://android.googlesource.com/platform/manifest \
  -b android-15.0.0_r1 --depth=1

# Thêm Pi4 manifest (KonstaKANG)
# Tạo file: .repo/local_manifests/rpi4.xml
mkdir -p .repo/local_manifests
cat > .repo/local_manifests/rpi4.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="konsta" fetch="https://github.com/KonstaKANG" />
  <project path="device/brcm/rpi4" name="android_device_brcm_rpi4"
           remote="konsta" revision="android-15.0" />
  <project path="kernel/brcm/rpi4" name="android_kernel_brcm_rpi4"
           remote="konsta" revision="android-15.0" />
</manifest>
EOF

repo sync -c -j$(nproc) --force-sync --no-clone-bundle --no-tags
```

### Bước 2.2 — Tích hợp vsomeip vào AOSP

```bash
# Clone vsomeip vào vendor
mkdir -p vendor/covesa
git clone https://github.com/COVESA/vsomeip.git vendor/covesa/vsomeip --depth=1 -b 3.4.10

# Copy prebuilt boost (hoặc build từ source)
# vsomeip phụ thuộc Boost 1.74+
sudo apt-get install -y libboost-dev libboost-system-dev \
  libboost-thread-dev libboost-log-dev

# Tạo Android.bp cho vsomeip (xem vendor/covesa/vsomeip/Android.bp)
```

### Bước 2.3 — Copy project files

```bash
# App Android
cp -r pi4-android/ ~/android-rpi4/packages/apps/VehicleDashboard/

# Native SOME/IP server
cp -r someip-server/ ~/android-rpi4/vendor/vehicle/someip-server/

# Config files
cp pi4-android/app/src/main/res/raw/vsomeip_server.json \
   ~/android-rpi4/vendor/vehicle/someip-server/config/
```

### Bước 2.4 — Thêm vào product config

Thêm vào `device/brcm/rpi4/device.mk`:
```makefile
# SOME/IP Vehicle Simulator
PRODUCT_PACKAGES += \
    VehicleDashboard \
    someip-vehicle-server \
    vsomeip3 \
    vsomeip3-cfg

# SELinux policies
BOARD_SEPOLICY_DIRS += packages/apps/VehicleDashboard/sepolicy

# Network permissions cho SOME/IP (UDP)
PRODUCT_COPY_FILES += \
    vendor/vehicle/someip-server/config/vsomeip_server.json:$(TARGET_COPY_OUT_VENDOR)/etc/vsomeip_server.json
```

### Bước 2.5 — Build

```bash
cd ~/android-rpi4
source build/envsetup.sh
lunch aosp_rpi4-userdebug

# Build toàn bộ (lần đầu ~2-4 giờ)
make -j$(nproc)

# Hoặc chỉ build app + native server
mmm packages/apps/VehicleDashboard
mmm vendor/vehicle/someip-server
```

### Bước 2.6 — Flash Pi4

```bash
# Tạo image
make dist

# Flash (Pi4 kết nối qua fastboot hoặc dùng SD card)
# Option A: fastboot
adb reboot bootloader
fastboot flashall -w

# Option B: SD card image
ls out/target/product/rpi4/*.img
# Dùng balenaEtcher hoặc dd để flash system.img vào SD card
dd if=out/target/product/rpi4/system.img of=/dev/sdX bs=4M status=progress
```

---

## PHẦN 3: Cấu hình mạng

### Pi4 và Laptop cùng network
```bash
# Pi4 (Android shell)
adb shell ifconfig eth0 192.168.1.200 netmask 255.255.255.0

# Laptop
sudo ip addr add 192.168.1.100/24 dev eth0
```

### Kiểm tra kết nối
```bash
# Từ laptop
ping 192.168.1.200

# Test SOME/IP port
nc -u 192.168.1.200 30490   # SOME/IP SD port
```

---

## PHẦN 4: Chạy và kiểm tra

### Start server trên Pi4
```bash
adb shell am start-service com.vehicle.someip/.service.SomeIpService
adb logcat -s SomeIpService VehicleHalBridge
```

### Start client trên Laptop
```bash
python3 laptop-client/src/vehicle_hmi.py
```

### Expected output
```
[Pi4 logcat]
SomeIpService: vsomeip initialized, version 3.4.10
SomeIpService: Service 0x1234/0x0001 registered
VehicleHalBridge: VehicleProperty.PERF_VEHICLE_SPEED updated: 60.5 km/h

[Laptop terminal]
[SOME/IP] Connected to 192.168.1.200:30490
[SOME/IP] Subscribed to VehicleSpeed event (0x8001)
[DATA] Speed: 60.5 km/h | RPM: 2400 | Throttle: 45%
```

---

## Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| `vsomeip: no configuration found` | Thiếu file JSON | Copy vsomeip_server.json vào /vendor/etc/ |
| `SUBSCRIBE_NACK` | Firewall block UDP 30490 | `iptables -A INPUT -p udp --dport 30490 -j ACCEPT` |
| JNI crash `UnsatisfiedLinkError` | .so chưa được copy | Kiểm tra `LOCAL_JNI_SHARED_LIBRARIES` trong Android.bp |
| HAL không nhận data | Permission SELinux | `adb shell setenforce 0` (debug only) |
| Build fail `boost not found` | Boost chưa cài | `sudo apt-get install libboost-all-dev` |
