#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 20 10:08:29 2023

@author: grunert
"""
from tkinter import *
import os,time
import sys
import serial
import numpy as np



hBV = 0
lBV = 0
# Control voltage in mV. On the 10V:10mA range, 1000 mV = 1 mA.
# Ramps 1.0 -> 5.0 mA in 0.5 mA steps, then back down. STOP as soon as you feel it.
#volt=[100,150,200,250,300,350,400,450,500,450,400,350,300,250,200,150,100]
#volt=[500, 500, 1000, 1000, 1500, 1500, 2000, 2000, 2500, 2500, 3000, 3000, 2500, 2500, 2000, 2000, 1500, 1500, 1000, 1000, 500, 500]

# ---- Waveform parameters (rate and peak are the knobs; step size is automatic) ----
TARGET_DURATION = 28.0   # seconds per triangular wave cycle
RATE_HZ = 8              # pulses per second (continuity / temporal summation)
PEAK = 2000              # mV peak amplitude
FLOOR = 250              # mV ramp floor (skip imperceptible sub-threshold below this)

# One cycle: 0 (neutral) -> FLOOR..PEAK..FLOOR triangle -> 0 (neutral).
# Pulse count = RATE_HZ * TARGET_DURATION; the amplitude step is whatever that implies.
n_ramp = int(round(TARGET_DURATION * RATE_HZ)) - 2   # 2 samples reserved for 0 endpoints
half = n_ramp // 2
up = np.linspace(FLOOR, PEAK, half, endpoint=False)  # FLOOR -> just below PEAK
down = np.linspace(PEAK, FLOOR, n_ramp - half)       # PEAK -> FLOOR
volt = [0] + np.concatenate([up, down]).round().astype(int).tolist() + [0]

# Serial port depends on the operating system:
#   Linux   -> /dev/ttyUSB0
#   Windows -> COM8 (Silicon Labs CP210x USB to UART Bridge)
if sys.platform.startswith('win'):
    DS5_PORT = 'COM8'
else:
    DS5_PORT = '/dev/ttyUSB0'

print(f'Opening DS5 on {DS5_PORT} ...')
try:
    ser = serial.Serial(DS5_PORT, 19200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)
except serial.SerialException as e:
    print(f'ERROR: could not open {DS5_PORT}: {e}')
    sys.exit(1)
print('Port open.')

def voltage(value):
    global hBV,lBV
    tmp=value*2/256
    hBV=int(tmp)
    lBV =int((tmp-hBV)*256)


PW=20 #in ms
tmp=PW*10/256
hBW=int(tmp)
lBW =int((tmp-hBW)*256)
ser.write(bytearray([87, hBW, lBW])) #pulse width
time.sleep(0.01)

ser.write(bytearray([78])) #zeroing PulsCount	
time.sleep(0.01)

ser.write(bytearray([69, 1 ])) #set elektrodennummer
time.sleep(0.01)

ser.write(bytearray([255])) #set elektrodennummer
time.sleep(0.01)

N_CYCLES = 12           # cycles per block (each block = 12 x 28 s)
PAUSE_DURATION = 30.0   # seconds rest between the two blocks
samples_per_cycle = len(volt)
period = TARGET_DURATION / samples_per_cycle  # time per pulse to hit exactly 28 s


def deliver_block(block_label, t_block_start):
    """Deliver N_CYCLES cycles, drift-compensated against t_block_start.

    Each cycle stays on its own continuous schedule so there is no gap or
    accumulated drift between cycles within the block.
    """
    for cycle in range(N_CYCLES):
        for v in range(samples_per_cycle):
            voltage(volt[v])
            ser.write(bytearray([83, hBV, lBV]))  # set amplitude
            time.sleep(0.005)
            ser.write(bytearray([80]))            # trigger pulse
            idx = cycle * samples_per_cycle + v
            next_time = t_block_start + (idx + 1) * period
            wait = next_time - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
        print(f'  {block_label} cycle {cycle + 1}/{N_CYCLES} done '
              f'(t = {time.perf_counter() - t_run_start:.2f} s)')


total_s = 2 * N_CYCLES * TARGET_DURATION + PAUSE_DURATION
print(f'Delivering 2 blocks x {N_CYCLES} cycles x {samples_per_cycle} pulses '
      f'({TARGET_DURATION:.1f} s/cycle, {period*1000:.1f} ms/pulse) '
      f'with a {PAUSE_DURATION:.0f} s pause between blocks '
      f'({total_s:.0f} s total)...')
t_run_start = time.perf_counter()

# --- Block 1 ---
deliver_block('block 1', time.perf_counter())

# --- 30 s pause: hold 0 mV, no pulses (lets the electrode de-polarize) ---
voltage(0)
ser.write(bytearray([83, hBV, lBV]))  # set amplitude to 0
print(f'  --- {PAUSE_DURATION:.0f} s pause, no stimulation '
      f'(t = {time.perf_counter() - t_run_start:.2f} s) ---')
pause_until = time.perf_counter() + PAUSE_DURATION
while time.perf_counter() < pause_until:
    time.sleep(0.1)

# --- Block 2 ---
deliver_block('block 2', time.perf_counter())

t_end = time.perf_counter()
elapsed = t_end - t_run_start
print(f'Total duration: {elapsed:.3f} s '
      f'(2 x {N_CYCLES} cycles + {PAUSE_DURATION:.0f} s pause)')

ser.close()
print('Done. Port closed.')