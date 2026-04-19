#!/usr/bin/env bash
# run_demo.sh — Chạy demo end-to-end
# Giả sử Pi4 đã được flash Android 15 + app đã cài
set -euo pipefail

PI4_IP="${1:-192.168.1.200}"
ADB="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}/platform-tools/adb"

echo "================================================================"
echo "  SOME/IP Vehicle Simulator — End-to-End Demo"
echo "  Pi4 IP: $PI4_IP"
echo "================================================================"

echo ""
echo "[Step 1] Kiểm tra kết nối Pi4..."
if ! ping -c 2 -W 2 "$PI4_IP" &>/dev/null; then
    echo "[ERROR] Không thể ping $PI4_IP"
    echo "  Kiểm tra: Pi4 đã boot? Đúng IP? Cùng subnet?"
    exit 1
fi
echo "  ✓ Pi4 reachable"

echo ""
echo "[Step 2] Kiểm tra ADB..."
if $ADB devices | grep -q device; then
    echo "  ✓ ADB connected"
    $ADB devices
else
    echo "  [WARN] Không có ADB device. Thử kết nối qua TCP..."
    $ADB connect "$PI4_IP:5555" || echo "  [WARN] ADB TCP failed — tiếp tục"
fi

echo ""
echo "[Step 3] Start SomeIpService trên Pi4..."
$ADB shell am start-foreground-service \
    com.vehicle.someip/.service.SomeIpService 2>/dev/null || \
    echo "  [WARN] Không thể start qua ADB — service có thể đã chạy"

sleep 2

echo ""
echo "[Step 4] Kiểm tra logcat..."
echo "  Last 10 lines từ SomeIpService:"
$ADB logcat -d -s "SomeIpService:I" "VehicleHalBridge:I" "SomeIpBridge:I" \
    2>/dev/null | tail -10 || echo "  [WARN] Không thể đọc logcat"

echo ""
echo "[Step 5] Start Dashboard Activity..."
$ADB shell am start -n com.vehicle.someip/.ui.DashboardActivity 2>/dev/null || \
    echo "  [WARN] Không thể start Activity qua ADB"

echo ""
echo "[Step 6] Start Laptop HMI..."
echo "  Launching vehicle_hmi.py..."
cd "$(dirname "$0")/.."
python3 laptop-client/src/vehicle_hmi.py --host "$PI4_IP" &
HMI_PID=$!
echo "  HMI PID: $HMI_PID"

echo ""
echo "================================================================"
echo "  Demo đang chạy!"
echo ""
echo "  • Pi4 HMI:    Xem trên màn hình Pi4"
echo "  • Laptop HMI: Đang mở GUI window"
echo "  • Logcat:     adb logcat -s SomeIpService VehicleHalBridge"
echo "  • Dừng:       Ctrl+C hoặc kill $HMI_PID"
echo "================================================================"

wait $HMI_PID
