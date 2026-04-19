#!/usr/bin/env bash
# setup_laptop.sh — Cài đặt dependencies cho Laptop client
set -euo pipefail

echo "================================================================"
echo "  SOME/IP Vehicle Simulator — Laptop Setup"
echo "================================================================"

# Check OS
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "[WARN] Script này tối ưu cho Linux (Ubuntu 20.04+)"
fi

echo ""
echo "[1/4] Cài hệ thống dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-tk \
    libboost-all-dev cmake build-essential \
    net-tools iputils-ping netcat-openbsd \
    wireshark-common

echo ""
echo "[2/4] Cài Python packages..."
pip3 install --user --upgrade pip
pip3 install --user \
    someip==0.4.0 \
    pyserial \
    matplotlib \
    numpy

echo ""
echo "[3/4] Kiểm tra kết nối mạng..."
echo "  Local interfaces:"
ip -brief addr show | grep -E "eth|wlan|enp|wlp" | head -5

echo ""
echo "[4/4] Test import Python modules..."
python3 -c "
import tkinter; print('  ✓ tkinter')
import socket;  print('  ✓ socket')
import struct;  print('  ✓ struct')
import threading; print('  ✓ threading')
print('  ✓ Tất cả modules OK')
"

echo ""
echo "================================================================"
echo "  Setup hoàn tất!"
echo ""
echo "  Bước tiếp theo:"
echo "  1. Chỉnh IP Pi4 trong: laptop-client/config/vsomeip_client.json"
echo "  2. Chạy: python3 laptop-client/src/someip_client.py --host <Pi4_IP>"
echo "  3. Hoặc GUI: python3 laptop-client/src/vehicle_hmi.py --host <Pi4_IP>"
echo "================================================================"
