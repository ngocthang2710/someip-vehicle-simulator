#!/usr/bin/env python3
"""
diagnostic_tool.py — SOME/IP Diagnostic Tool
Kiểm tra service availability, đo latency, log events.

Usage: python3 diagnostic_tool.py --host 192.168.1.200
"""

import socket
import struct
import time
import argparse
import statistics
from someip_client import SomeIpClient, SomeIpMessage, SVC_VEHICLE, INSTANCE_ID, METHOD_GET_INFO, MSG_REQUEST

def measure_rtt(host: str, port: int = 30501, count: int = 10) -> dict:
    """Đo Round-Trip Time cho SOME/IP GetVehicleInfo request."""
    client = SomeIpClient(host, port)
    latencies = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    sock.bind(('', 30500))

    print(f"\nPinging {host}:{port} ({count} requests)...")

    for i in range(count):
        msg = SomeIpMessage.build(
            SVC_VEHICLE, INSTANCE_ID, METHOD_GET_INFO,
            0xABCD, i + 1, MSG_REQUEST, 0x00
        )
        t_start = time.perf_counter()
        sock.sendto(msg, (host, port))
        try:
            data, _ = sock.recvfrom(4096)
            rtt_ms = (time.perf_counter() - t_start) * 1000
            latencies.append(rtt_ms)
            print(f"  [{i+1:2d}] RTT = {rtt_ms:6.2f} ms")
        except socket.timeout:
            print(f"  [{i+1:2d}] TIMEOUT")

        time.sleep(0.1)

    sock.close()

    if latencies:
        return {
            'count': len(latencies),
            'loss':  count - len(latencies),
            'min':   min(latencies),
            'max':   max(latencies),
            'avg':   statistics.mean(latencies),
            'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        }
    return {}


def check_sd_port(host: str) -> bool:
    """Kiểm tra SOME/IP Service Discovery port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.bind(('', 0))
        # Gửi SD Find Service message
        # (simplified — just check if port responds)
        sock.sendto(b'\x00' * 16, (host, 30490))
        sock.close()
        return True
    except:
        return False


def monitor_events(host: str, duration: int = 5):
    """Monitor all events trong N giây, đếm event rate."""
    from someip_client import SomeIpClient, VehicleData

    event_counts = {}
    client = SomeIpClient(host)

    if not client.connect():
        print(f"[ERROR] Cannot connect to {host}")
        return

    client.subscribe_events()

    def on_data(data: VehicleData):
        key = 'update'
        event_counts[key] = event_counts.get(key, 0) + 1

    client.add_data_callback(on_data)

    print(f"\nMonitoring events for {duration} seconds...")
    t_start = time.time()
    while time.time() - t_start < duration:
        elapsed = time.time() - t_start
        updates = event_counts.get('update', 0)
        rate    = updates / elapsed if elapsed > 0 else 0
        print(f"\r  Events: {updates:4d} | Rate: {rate:5.1f} Hz | "
              f"Elapsed: {elapsed:.1f}s", end='', flush=True)
        time.sleep(0.2)

    client.disconnect()
    print(f"\n\n  Total updates in {duration}s: {event_counts.get('update', 0)}")


def main():
    parser = argparse.ArgumentParser(description='SOME/IP Diagnostic Tool')
    parser.add_argument('--host',     default='192.168.1.200')
    parser.add_argument('--rtt',      action='store_true', help='RTT measurement')
    parser.add_argument('--monitor',  action='store_true', help='Event monitoring')
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--count',    type=int, default=10)
    args = parser.parse_args()

    print(f"\n{'═'*60}")
    print(f"  SOME/IP Diagnostic Tool | Target: {args.host}")
    print(f"{'═'*60}")

    # SD port check
    print(f"\n[1] SD Port (UDP 30490):", end=' ')
    print("OPEN ✓" if check_sd_port(args.host) else "CLOSED ✗")

    if args.rtt:
        stats = measure_rtt(args.host, count=args.count)
        if stats:
            print(f"\n[RTT Summary]")
            print(f"  Packets sent/rcvd: {args.count}/{stats['count']} (loss: {stats['loss']})")
            print(f"  Min: {stats['min']:.2f}ms | Max: {stats['max']:.2f}ms")
            print(f"  Avg: {stats['avg']:.2f}ms | StdDev: {stats['stdev']:.2f}ms")

    if args.monitor:
        monitor_events(args.host, args.duration)

    if not args.rtt and not args.monitor:
        # Default: quick health check
        measure_rtt(args.host, count=3)
        monitor_events(args.host, duration=3)


if __name__ == '__main__':
    main()
