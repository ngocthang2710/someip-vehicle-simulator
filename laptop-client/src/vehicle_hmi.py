#!/usr/bin/env python3
"""
vehicle_hmi.py — Graphical HMI Dashboard trên Laptop
Dùng tkinter + Canvas để vẽ speedometer/tachometer realtime.

Usage: python3 vehicle_hmi.py [--host 192.168.1.200]
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import time
import argparse
import threading
from someip_client import SomeIpClient, VehicleData

# ─── Gauge Canvas Widget ──────────────────────────────────────────────────────
class GaugeCanvas(tk.Canvas):
    def __init__(self, master, label: str, max_val: float, unit: str,
                 red_zone: float = None, size: int = 220, **kw):
        super().__init__(master, width=size, height=size,
                         bg='#0F0F1A', highlightthickness=0, **kw)
        self.label    = label
        self.max_val  = max_val
        self.unit     = unit
        self.red_zone = red_zone
        self.size     = size
        self.cx       = size / 2
        self.cy       = size / 2
        self.radius   = size * 0.42
        self._value   = 0.0
        self._draw_static()
        self._draw_dynamic(0.0)

    def _angle(self, value: float) -> float:
        """Map value [0, max_val] → angle in radians (225° → -45°)."""
        fraction = max(0.0, min(1.0, value / self.max_val))
        deg = 225 - fraction * 270
        return math.radians(deg)

    def _draw_static(self):
        cx, cy, r = self.cx, self.cy, self.radius
        # Background circle
        self.create_oval(cx-r*1.1, cy-r*1.1, cx+r*1.1, cy+r*1.1,
                         fill='#1A1A2E', outline='#2D2D44', width=2)
        # Arc track background
        self._draw_arc_segment(0, self.max_val, '#2D2D44', width=14)

        # Red zone
        if self.red_zone:
            self._draw_arc_segment(self.red_zone, self.max_val, '#7F1D1D', width=14)

        # Tick marks + labels
        ticks = 10
        for i in range(ticks + 1):
            frac = i / ticks
            deg  = 225 - frac * 270
            rad  = math.radians(deg)
            is_major = (i % 2 == 0)
            inner_r  = r * (0.75 if is_major else 0.82)
            outer_r  = r * 0.92
            x1 = cx + inner_r * math.cos(rad)
            y1 = cy - inner_r * math.sin(rad)
            x2 = cx + outer_r * math.cos(rad)
            y2 = cy - outer_r * math.sin(rad)
            color = '#6B7280' if not is_major else '#9CA3AF'
            self.create_line(x1, y1, x2, y2, fill=color,
                             width=2 if is_major else 1)
            if is_major:
                val_label = int(self.max_val * frac)
                lx = cx + r * 0.62 * math.cos(rad)
                ly = cy - r * 0.62 * math.sin(rad)
                self.create_text(lx, ly, text=str(val_label),
                                 fill='#6B7280', font=('Courier', 8))

        # Label top
        self.create_text(cx, cy - r * 0.55, text=self.label,
                         fill='#6B7280', font=('Courier', 10, 'bold'))
        # Unit bottom
        self.create_text(cx, cy + r * 0.65, text=self.unit,
                         fill='#4B5563', font=('Courier', 9))

    def _draw_arc_segment(self, v_start: float, v_end: float, color: str, width: int = 14):
        cx, cy, r = self.cx, self.cy, self.radius
        # Approximate arc with polyline
        steps = 60
        frac_start = v_start / self.max_val
        frac_end   = v_end   / self.max_val
        points = []
        for i in range(steps + 1):
            frac = frac_start + (frac_end - frac_start) * (i / steps)
            deg  = 225 - frac * 270
            rad  = math.radians(deg)
            points.extend([cx + r * math.cos(rad),
                            cy - r * math.sin(rad)])
        if len(points) >= 4:
            self.create_line(*points, fill=color, width=width,
                             smooth=True, capstyle=tk.ROUND)

    def _draw_dynamic(self, value: float):
        # Delete old dynamic elements
        self.delete('dynamic')
        cx, cy, r = self.cx, self.cy, self.radius

        # Active arc
        if value > 0:
            frac  = value / self.max_val
            color = '#FF3B30' if (self.red_zone and value >= self.red_zone) else '#00D4AA'
            self._draw_arc_segment(0, value, color, width=14)
            # Tag hack: re-tag last item — simplified, draw fresh each frame
            # (Canvas approach: delete all dynamic items, redraw)

        # Needle
        angle = self._angle(value)
        nx = cx + r * 0.72 * math.cos(angle)
        ny = cy - r * 0.72 * math.sin(angle)
        self.create_line(cx, cy, nx, ny, fill='#FF6B35', width=3,
                         capstyle=tk.ROUND, tags='dynamic')

        # Center dot
        dot_r = 8
        self.create_oval(cx-dot_r, cy-dot_r, cx+dot_r, cy+dot_r,
                         fill='#FF6B35', outline='#FF9F6B', width=2, tags='dynamic')

        # Value text
        self.create_text(cx, cy + r * 0.3,
                         text=f'{value:.0f}',
                         fill='#FFFFFF',
                         font=('Courier', 22, 'bold'),
                         tags='dynamic')

    def set_value(self, value: float):
        if abs(value - self._value) < 0.1:
            return
        self._value = value
        self.delete('all')
        self._draw_static()
        self._draw_dynamic(value)


# ─── Main HMI Window ──────────────────────────────────────────────────────────
class VehicleHMI:
    def __init__(self, host: str = '192.168.1.200'):
        self.host   = host
        self.client = SomeIpClient(host)
        self._running = False

        self.root = tk.Tk()
        self.root.title('Vehicle Dashboard — SOME/IP HMI')
        self.root.configure(bg='#0F0F1A')
        self.root.geometry('900x600')
        self.root.resizable(True, True)

        self._build_ui()
        self._connect()

    # ─── UI Construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(root, bg='#0F0F1A', pady=6)
        header.grid(row=0, column=0, sticky='ew', padx=16)

        tk.Label(header, text='VEHICLE DASHBOARD', bg='#0F0F1A',
                 fg='#00D4AA', font=('Courier', 14, 'bold'),
                 letterSpacing=4).pack(side='left')

        self.lbl_conn = tk.Label(header, text='● Connecting...',
                                  bg='#0F0F1A', fg='#FF9F0A',
                                  font=('Courier', 10))
        self.lbl_conn.pack(side='right')

        tk.Frame(root, bg='#2D2D44', height=1).grid(
            row=1, column=0, sticky='ew', padx=16)

        # ── Main content ────────────────────────────────────────────────────
        content = tk.Frame(root, bg='#0F0F1A')
        content.grid(row=2, column=0, sticky='nsew', padx=16, pady=8)
        root.rowconfigure(2, weight=1)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.columnconfigure(2, weight=1)

        # Speedometer
        self.speed_gauge = GaugeCanvas(content, 'SPEED', 200, 'km/h', size=240)
        self.speed_gauge.grid(row=0, column=0, pady=4)

        # Center info panel
        center = tk.Frame(content, bg='#1A1A2E', padx=16, pady=16,
                          relief='flat', bd=0)
        center.grid(row=0, column=1, padx=12, sticky='ns')

        # Gear
        self.lbl_gear = tk.Label(center, text='P', bg='#1A1A2E',
                                  fg='#00D4AA', font=('Courier', 40, 'bold'),
                                  width=3, relief='groove', bd=2)
        self.lbl_gear.pack(pady=(8, 16))

        for attr, label, color in [
            ('lbl_speed_num', 'SPEED (km/h)', '#9CA3AF'),
            ('lbl_rpm_num',   'RPM',          '#9CA3AF'),
            ('lbl_coolant',   'COOLANT',      '#FF9F0A'),
            ('lbl_fuel',      'FUEL',         '#00D4AA'),
        ]:
            tk.Label(center, text=label, bg='#1A1A2E',
                     fg='#6B7280', font=('Courier', 8)).pack()
            lbl = tk.Label(center, text='---', bg='#1A1A2E',
                           fg=color, font=('Courier', 14, 'bold'))
            lbl.pack(pady=(0, 8))
            setattr(self, attr, lbl)

        # Fuel bar
        self.fuel_bar = ttk.Progressbar(center, length=120, mode='determinate',
                                         maximum=100)
        self.fuel_bar.pack()

        # Tachometer
        self.rpm_gauge = GaugeCanvas(content, 'ENGINE', 8000, 'rpm',
                                      red_zone=6000, size=240)
        self.rpm_gauge.grid(row=0, column=2, pady=4)

        # ── Status bar ────────────────────────────────────────────────────
        self.lbl_status = tk.Label(root, text='Waiting for data...',
                                    bg='#1A1A2E', fg='#6B7280',
                                    font=('Courier', 9), anchor='w', padx=8)
        self.lbl_status.grid(row=3, column=0, sticky='ew', pady=4, padx=16)

        # ── Controls ──────────────────────────────────────────────────────
        ctrl = tk.Frame(root, bg='#0F0F1A')
        ctrl.grid(row=4, column=0, sticky='ew', padx=16, pady=4)
        ctrl.columnconfigure(1, weight=1)
        ctrl.columnconfigure(3, weight=1)

        tk.Label(ctrl, text='THROTTLE', bg='#0F0F1A', fg='#9CA3AF',
                 font=('Courier', 9), width=10, anchor='e').grid(row=0, column=0, padx=4)
        self.throttle_var = tk.DoubleVar()
        self.throttle_scale = tk.Scale(ctrl, from_=0, to=100, orient='horizontal',
                                        variable=self.throttle_var, bg='#0F0F1A',
                                        fg='#00D4AA', troughcolor='#2D2D44',
                                        highlightthickness=0, showvalue=False,
                                        command=self._on_throttle)
        self.throttle_scale.grid(row=0, column=1, sticky='ew', padx=4)

        tk.Label(ctrl, text='BRAKE', bg='#0F0F1A', fg='#9CA3AF',
                 font=('Courier', 9), width=10, anchor='e').grid(row=1, column=0, padx=4)
        self.brake_var = tk.DoubleVar()
        self.brake_scale = tk.Scale(ctrl, from_=0, to=100, orient='horizontal',
                                     variable=self.brake_var, bg='#0F0F1A',
                                     fg='#FF3B30', troughcolor='#2D2D44',
                                     highlightthickness=0, showvalue=False,
                                     command=self._on_brake)
        self.brake_scale.grid(row=1, column=1, sticky='ew', padx=4)

        self.btn_estop = tk.Button(ctrl, text='⚠ EMERGENCY STOP',
                                    bg='#7F1D1D', fg='#FFFFFF',
                                    font=('Courier', 11, 'bold'),
                                    activebackground='#FF3B30',
                                    relief='flat', bd=0, padx=20, pady=6,
                                    command=self._on_emergency)
        self.btn_estop.grid(row=0, column=2, rowspan=2, padx=16, pady=4)

    # ─── Controls ─────────────────────────────────────────────────────────────
    def _on_throttle(self, val):
        if self.client:
            self.client.set_throttle(float(val) / 100.0)

    def _on_brake(self, val):
        if self.client:
            self.client.set_brake(float(val) / 100.0)

    def _on_emergency(self):
        if self.client:
            self.client.emergency_stop()
            self.throttle_scale.set(0)
            self.brake_scale.set(100)

    # ─── Connection ───────────────────────────────────────────────────────────
    def _connect(self):
        def _bg():
            ok = self.client.connect()
            if ok:
                self.client.subscribe_events()
                self.client.add_data_callback(self._on_data)
                self.root.after(0, lambda: self.lbl_conn.configure(
                    text=f'● Connected ({self.host})', fg='#00D4AA'))
            else:
                self.root.after(0, lambda: self.lbl_conn.configure(
                    text='● Connection Failed', fg='#FF3B30'))
        threading.Thread(target=_bg, daemon=True).start()

    # ─── Data update ──────────────────────────────────────────────────────────
    def _on_data(self, data: VehicleData):
        # Schedule UI update on main thread
        self.root.after(0, lambda: self._update_ui(data))

    def _update_ui(self, d: VehicleData):
        try:
            self.speed_gauge.set_value(d.speed_kmh)
            self.rpm_gauge.set_value(float(d.rpm))
            self.lbl_gear.configure(text=d.gear_label())
            self.lbl_speed_num.configure(text=f'{d.speed_kmh:.1f}')
            self.lbl_rpm_num.configure(text=str(d.rpm))
            self.lbl_coolant.configure(text=f'{d.coolant_temp:.1f}°C')
            self.lbl_fuel.configure(text=f'{d.fuel_pct:.1f}%')
            self.fuel_bar['value'] = d.fuel_pct
            self.lbl_status.configure(
                text=f'  ◆  {d}  |  {time.strftime("%H:%M:%S")}')
        except tk.TclError:
            pass  # Window already closed

    # ─── Run ─────────────────────────────────────────────────────────────────
    def run(self):
        try:
            self.root.mainloop()
        finally:
            if self.client:
                self.client.disconnect()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Vehicle HMI Dashboard')
    parser.add_argument('--host', default='192.168.1.200', help='Pi4 IP')
    args = parser.parse_args()

    hmi = VehicleHMI(host=args.host)
    hmi.run()
