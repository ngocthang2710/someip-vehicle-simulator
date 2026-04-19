#!/usr/bin/env python3
"""
someip_client.py — SOME/IP client cho Laptop
Kết nối tới VehicleService trên Pi4 và in dữ liệu xe theo thời gian thực.

Sử dụng: python3 someip_client.py [--host 192.168.1.200] [--port 30490]
"""

import socket
import struct
import threading
import time
import argparse
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('SomeIpClient')

# ─── SOME/IP Constants ────────────────────────────────────────────────────────
SOMEIP_HEADER_LEN = 16  # bytes

# Service IDs
SVC_VEHICLE  = 0x1234
SVC_ENGINE   = 0x1235
SVC_THROTTLE = 0x1236
INSTANCE_ID  = 0x0001

# Method/Event IDs
METHOD_SET_THROTTLE = 0x0001
METHOD_SET_BRAKE    = 0x0002
METHOD_GET_INFO     = 0x0003
METHOD_EMERG_STOP   = 0x0004

EVENT_SPEED   = 0x8001
EVENT_RPM     = 0x8002
EVENT_FUEL    = 0x8003
EVENT_GEAR    = 0x8004
EVENT_BRAKE   = 0x8005

# Eventgroup IDs
EG_SPEED_RPM = 0x0001
EG_FUEL_GEAR = 0x0002
EG_BRAKE     = 0x0003

# Message Types
MSG_REQUEST      = 0x00
MSG_REQUEST_NACK = 0x01
MSG_RESPONSE     = 0x80
MSG_ERROR        = 0x81
MSG_NOTIFY       = 0x02
MSG_SUBSCRIBE    = 0x06  # SD Entry type
MSG_SUBSCRIBE_ACK= 0x07

# SOME/IP-SD constants
SD_SERVICE_ID    = 0xFFFF
SD_INSTANCE_ID   = 0x0100
SD_METHOD_ID     = 0x8100
SD_CLIENT_ID     = 0x0000
SD_MULTICAST     = '239.224.224.245'
SD_PORT          = 30490


# ─── Data classes ─────────────────────────────────────────────────────────────
@dataclass
class VehicleData:
    speed_kmh:    float = 0.0
    rpm:          int   = 800
    gear:         int   = 0
    fuel_pct:     float = 100.0
    throttle:     float = 0.0
    brake_active: bool  = False
    coolant_temp: float = 25.0
    timestamp:    float = field(default_factory=time.time)

    def gear_label(self) -> str:
        labels = {0: 'P', 1: 'R', 2: 'N'}
        if self.gear in labels:
            return labels[self.gear]
        return f'D{self.gear - 2}'

    def __str__(self) -> str:
        return (f"Speed:{self.speed_kmh:6.1f}km/h  "
                f"RPM:{self.rpm:5d}  "
                f"Gear:{self.gear_label()}  "
                f"Fuel:{self.fuel_pct:5.1f}%  "
                f"Throttle:{self.throttle*100:4.0f}%  "
                f"Brake:{'ON ' if self.brake_active else 'off'}  "
                f"Coolant:{self.coolant_temp:5.1f}°C")


# ─── SOME/IP Message Builder ──────────────────────────────────────────────────
class SomeIpMessage:
    """Build và parse SOME/IP messages theo format chuẩn."""

    @staticmethod
    def build(service_id: int, instance_id: int, method_id: int,
              client_id: int, session_id: int, msg_type: int,
              return_code: int, payload: bytes = b'') -> bytes:
        """
        SOME/IP Header format (16 bytes):
          [0:2]  Service ID
          [2:4]  Method ID
          [4:8]  Length (payload + 8)
          [8:10] Client ID
          [10:12] Session ID
          [12]   Protocol version = 0x01
          [13]   Interface version = 0x01
          [14]   Message Type
          [15]   Return Code
        """
        length = len(payload) + 8
        header = struct.pack(
            '>HHIHHBBBB',
            service_id,
            method_id,
            length,
            client_id,
            session_id,
            0x01,       # protocol version
            0x01,       # interface version
            msg_type,
            return_code
        )
        return header + payload

    @staticmethod
    def parse(data: bytes) -> Optional[dict]:
        if len(data) < SOMEIP_HEADER_LEN:
            return None
        service_id, method_id, length, client_id, session_id, \
            proto_ver, iface_ver, msg_type, return_code = \
            struct.unpack('>HHIHHBBBB', data[:16])
        payload = data[16:16 + length - 8] if length > 8 else b''
        return {
            'service_id': service_id,
            'method_id':  method_id,
            'length':     length,
            'client_id':  client_id,
            'session_id': session_id,
            'msg_type':   msg_type,
            'return_code':return_code,
            'payload':    payload,
        }

    @staticmethod
    def pack_float(value: float) -> bytes:
        """Big-endian float32 (SOME/IP network byte order)."""
        return struct.pack('>f', value)

    @staticmethod
    def unpack_float(data: bytes, offset: int = 0) -> float:
        return struct.unpack('>f', data[offset:offset+4])[0]

    @staticmethod
    def unpack_uint16(data: bytes, offset: int = 0) -> int:
        return struct.unpack('>H', data[offset:offset+2])[0]


# ─── SOME/IP Client ───────────────────────────────────────────────────────────
class SomeIpClient:
    def __init__(self, server_host: str = '192.168.1.200',
                 server_port: int = 30501,
                 local_port: int = 30500):
        self.server_host  = server_host
        self.server_port  = server_port
        self.local_port   = local_port
        self._session_id  = 1
        self._client_id   = 0xABCD

        self._sock: Optional[socket.socket] = None
        self._tcp_sock: Optional[socket.socket] = None
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None

        self.vehicle_data = VehicleData()
        self._data_callbacks: list[Callable[[VehicleData], None]] = []
        self._lock = threading.Lock()

    def add_data_callback(self, cb: Callable[[VehicleData], None]):
        self._data_callbacks.append(cb)

    def connect(self) -> bool:
        try:
            # UDP socket for events + requests
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(('', self.local_port))
            self._sock.settimeout(1.0)

            # TCP socket for ThrottleService (reliable methods)
            self._tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_sock.settimeout(5.0)
            self._tcp_sock.connect((self.server_host, 30502))
            log.info(f"TCP connected to {self.server_host}:30502")

            self._running = True
            self._recv_thread = threading.Thread(
                target=self._recv_loop, daemon=True, name='someip-recv')
            self._recv_thread.start()

            log.info(f"UDP bound on port {self.local_port}")
            return True

        except Exception as e:
            log.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        self._running = False
        if self._sock:
            self._sock.close()
        if self._tcp_sock:
            self._tcp_sock.close()

    def subscribe_events(self):
        """Subscribe to all vehicle event groups."""
        for eg_id in [EG_SPEED_RPM, EG_FUEL_GEAR, EG_BRAKE]:
            self._send_subscribe(SVC_VEHICLE, INSTANCE_ID, eg_id)
            time.sleep(0.05)

        # Subscribe to RPM from EngineService
        self._send_subscribe(SVC_ENGINE, INSTANCE_ID, EG_SPEED_RPM)
        log.info("Subscribed to all event groups")

    def _send_subscribe(self, service_id: int, instance_id: int, eventgroup_id: int):
        """
        SOME/IP-SD Subscribe Entry.
        Gửi tới server unicast port 30490 (SD).
        """
        # SD Header: Flags (1B) + Reserved (3B) + Entries Array Length (4B)
        # Entry: Type(1) + Index1(1) + Index2(1) + #Options(1) + ServiceID(2)
        #        + InstanceID(2) + MajorVersion(1) + TTL(3) + MinorVersion(4)
        entry = struct.pack('>BBBBHHBIBH',
            0x06,           # Type: Subscribe Eventgroup
            0x00,           # Index 1st options
            0x00,           # Index 2nd options
            0x00,           # Num options
            service_id,
            instance_id,
            0x01,           # Major version
            0x00FFFFFF,     # TTL (infinite)
            0x00000000,     # Minor version
            eventgroup_id
        )
        entries_len = len(entry)
        sd_payload = struct.pack('>BBBBI', 0xC0, 0, 0, 0, entries_len) + entry + struct.pack('>I', 0)

        msg = SomeIpMessage.build(
            SD_SERVICE_ID, SD_INSTANCE_ID, SD_METHOD_ID,
            SD_CLIENT_ID, self._next_session(),
            MSG_NOTIFY, 0x00, sd_payload
        )
        try:
            self._sock.sendto(msg, (self.server_host, SD_PORT))
        except Exception as e:
            log.warning(f"Subscribe send failed: {e}")

    def set_throttle(self, throttle: float) -> bool:
        """Gửi SetThrottle command qua TCP (reliable)."""
        throttle = max(0.0, min(1.0, throttle))
        payload = SomeIpMessage.pack_float(throttle)
        msg = SomeIpMessage.build(
            SVC_THROTTLE, INSTANCE_ID, METHOD_SET_THROTTLE,
            self._client_id, self._next_session(),
            MSG_REQUEST, 0x00, payload
        )
        return self._tcp_send(msg)

    def set_brake(self, brake: float) -> bool:
        """Gửi SetBrake command qua TCP."""
        payload = SomeIpMessage.pack_float(max(0.0, min(1.0, brake)))
        msg = SomeIpMessage.build(
            SVC_THROTTLE, INSTANCE_ID, METHOD_SET_BRAKE,
            self._client_id, self._next_session(),
            MSG_REQUEST, 0x00, payload
        )
        return self._tcp_send(msg)

    def emergency_stop(self) -> bool:
        """Gửi EmergencyStop."""
        msg = SomeIpMessage.build(
            SVC_THROTTLE, INSTANCE_ID, METHOD_EMERG_STOP,
            self._client_id, self._next_session(),
            MSG_REQUEST, 0x00
        )
        return self._tcp_send(msg)

    def get_vehicle_info(self) -> Optional[VehicleData]:
        """Request full VehicleInfo struct."""
        msg = SomeIpMessage.build(
            SVC_VEHICLE, INSTANCE_ID, METHOD_GET_INFO,
            self._client_id, self._next_session(),
            MSG_REQUEST, 0x00
        )
        try:
            self._sock.sendto(msg, (self.server_host, self.server_port))
            # Response sẽ đến qua _recv_loop
            time.sleep(0.2)
            return self.vehicle_data
        except Exception as e:
            log.error(f"GetVehicleInfo failed: {e}")
            return None

    # ─── Receive loop ─────────────────────────────────────────────────────────
    def _recv_loop(self):
        log.info("Receive loop started")
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
                self._handle_message(data, addr)
            except socket.timeout:
                continue
            except OSError:
                break
        log.info("Receive loop stopped")

    def _handle_message(self, data: bytes, addr: tuple):
        msg = SomeIpMessage.parse(data)
        if not msg:
            return

        svc_id     = msg['service_id']
        method_id  = msg['method_id']
        msg_type   = msg['msg_type']
        payload    = msg['payload']

        # Notifications (events)
        if msg_type == MSG_NOTIFY:
            if svc_id == SVC_VEHICLE and method_id == EVENT_SPEED:
                if len(payload) >= 4:
                    speed = SomeIpMessage.unpack_float(payload)
                    with self._lock:
                        self.vehicle_data.speed_kmh = speed
                    self._notify_callbacks()

            elif svc_id == SVC_ENGINE and method_id == EVENT_RPM:
                if len(payload) >= 2:
                    rpm = SomeIpMessage.unpack_uint16(payload)
                    with self._lock:
                        self.vehicle_data.rpm = rpm
                    self._notify_callbacks()

            elif svc_id == SVC_VEHICLE and method_id == EVENT_FUEL:
                if len(payload) >= 4:
                    fuel = SomeIpMessage.unpack_float(payload)
                    with self._lock:
                        self.vehicle_data.fuel_pct = fuel

            elif svc_id == SVC_VEHICLE and method_id == EVENT_GEAR:
                if len(payload) >= 1:
                    with self._lock:
                        self.vehicle_data.gear = payload[0]

            elif svc_id == SVC_VEHICLE and method_id == EVENT_BRAKE:
                if len(payload) >= 1:
                    with self._lock:
                        self.vehicle_data.brake_active = (payload[0] != 0)

        # Response to GetVehicleInfo
        elif msg_type == MSG_RESPONSE and method_id == METHOD_GET_INFO:
            self._parse_vehicle_info(payload)

    def _parse_vehicle_info(self, payload: bytes):
        """Parse VehicleInfoStruct (20 bytes)."""
        if len(payload) < 20:
            return
        with self._lock:
            self.vehicle_data.speed_kmh    = SomeIpMessage.unpack_float(payload, 0)
            self.vehicle_data.rpm          = SomeIpMessage.unpack_uint16(payload, 4)
            self.vehicle_data.gear         = payload[6]
            self.vehicle_data.fuel_pct     = SomeIpMessage.unpack_float(payload, 7)
            self.vehicle_data.throttle     = SomeIpMessage.unpack_float(payload, 11)
            self.vehicle_data.brake_active = bool(payload[15])
            self.vehicle_data.coolant_temp = SomeIpMessage.unpack_float(payload, 16)
            self.vehicle_data.timestamp    = time.time()
        self._notify_callbacks()

    def _notify_callbacks(self):
        with self._lock:
            data_copy = VehicleData(**self.vehicle_data.__dict__)
        for cb in self._data_callbacks:
            try:
                cb(data_copy)
            except Exception as e:
                log.warning(f"Callback error: {e}")

    def _tcp_send(self, data: bytes) -> bool:
        try:
            if self._tcp_sock:
                self._tcp_sock.sendall(data)
                return True
        except Exception as e:
            log.error(f"TCP send failed: {e}")
        return False

    def _next_session(self) -> int:
        sid = self._session_id
        self._session_id = (self._session_id % 0xFFFF) + 1
        return sid


# ─── CLI mode ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='SOME/IP Vehicle Client')
    parser.add_argument('--host', default='192.168.1.200', help='Pi4 IP address')
    parser.add_argument('--port', type=int, default=30501, help='SOME/IP server port')
    parser.add_argument('--local-port', type=int, default=30500)
    args = parser.parse_args()

    client = SomeIpClient(args.host, args.port, args.local_port)

    print(f"\n{'═'*70}")
    print(f"  SOME/IP Vehicle Client — Pi4 @ {args.host}:{args.port}")
    print(f"{'═'*70}\n")

    if not client.connect():
        print("[ERROR] Cannot connect to Pi4")
        return

    print("[OK] Connected. Subscribing to events...")
    client.subscribe_events()
    print("[OK] Subscribed. Receiving vehicle data...\n")
    print(f"{'─'*70}")

    update_count = [0]

    def on_data(data: VehicleData):
        update_count[0] += 1
        if update_count[0] % 5 == 0:  # Print every 5th update (~2Hz)
            print(f"\r  {data}", end='', flush=True)

    client.add_data_callback(on_data)

    # Interactive command loop
    print("\n[Commands: t=throttle, b=brake, e=emergency, i=info, q=quit]\n")
    try:
        while True:
            cmd = input().strip().lower()
            if cmd == 'q':
                break
            elif cmd.startswith('t'):
                val = float(cmd[1:]) / 100.0 if len(cmd) > 1 else 0.5
                ok = client.set_throttle(val)
                print(f"  → SetThrottle({val:.2f}): {'OK' if ok else 'FAIL'}")
            elif cmd.startswith('b'):
                val = float(cmd[1:]) / 100.0 if len(cmd) > 1 else 1.0
                ok = client.set_brake(val)
                print(f"  → SetBrake({val:.2f}): {'OK' if ok else 'FAIL'}")
            elif cmd == 'e':
                ok = client.emergency_stop()
                print(f"  → EmergencyStop: {'OK' if ok else 'FAIL'}")
            elif cmd == 'i':
                info = client.get_vehicle_info()
                if info:
                    print(f"\n  {info}\n")
    except KeyboardInterrupt:
        pass

    print("\n\nDisconnecting...")
    client.disconnect()
    print("Bye.")


if __name__ == '__main__':
    main()
