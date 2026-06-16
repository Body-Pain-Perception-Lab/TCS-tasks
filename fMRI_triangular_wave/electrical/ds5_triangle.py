#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone DS5 triangle test.

Runs a 28 s unipolar triangle (0 -> peak -> 0) as a continuous 10 Hz pulse
train, modulating the per-pulse amplitude along the triangle envelope so the
stimulation feels like a smooth, continuously changing intensity (the way the
real eprf task does).

It plays the triangle once per pulse width in PULSE_WIDTHS_MS so you can
compare how "continuous" each setting feels. Press Enter to advance between
runs. Ctrl+C stops safely (amplitude ramped to 0, port closed).

Amplitude on the 10V:10mA DS5 range: 1000 mV = 1 mA.
"""

import sys
import time
import serial

from waveform import generate_amplitude_waveform

# ---- Test parameters -------------------------------------------------------
CYCLE_DURATION = 28.0        # seconds for one full 0 -> peak -> 0 triangle
UPDATE_HZ      = 5           # carrier pulse rate (pulses per second)
MAX_AMPLITUDE  = 1200.0      # peak amplitude in mV (1200 mV = 1.2 mA)
PULSE_WIDTHS_MS = [0.5]  # pulse widths to test, in order
# ---------------------------------------------------------------------------

# Serial port depends on the operating system:
#   Linux   -> /dev/ttyUSB0
#   Windows -> COM8 (Silicon Labs CP210x USB to UART Bridge)
if sys.platform.startswith('win'):
    DS5_PORT = 'COM8'
else:
    DS5_PORT = '/dev/ttyUSB0'


def encode_16bit(value):
    """Encode an integer as (high, low) bytes, big-endian, clamped to 16 bit."""
    value = int(round(value))
    value = max(0, min(65535, value))
    return value // 256, value % 256


def set_pulse_width(ser, duration_ms):
    """W command: value = duration_ms * 10 (0.1 ms units)."""
    h, l = encode_16bit(duration_ms * 10)
    ser.write(bytearray([87, h, l]))   # 'W'
    time.sleep(0.01)


def set_amplitude(ser, millivolts):
    """S command: value = millivolts * 2."""
    h, l = encode_16bit(millivolts * 2)
    ser.write(bytearray([83, h, l]))   # 'S'


def trigger(ser):
    """P command: deliver one pulse."""
    ser.write(bytearray([80]))         # 'P'


def run_triangle(ser, pulse_width_ms):
    """Play one 28 s triangle as a 10 Hz amplitude-modulated pulse train."""
    waveform = generate_amplitude_waveform(CYCLE_DURATION, UPDATE_HZ,
                                           MAX_AMPLITUDE)
    sample_interval = 1.0 / UPDATE_HZ

    set_pulse_width(ser, pulse_width_ms)

    print(f'  Running 28 s triangle @ {UPDATE_HZ} Hz, '
          f'pulse width {pulse_width_ms} ms, peak {MAX_AMPLITUDE:.0f} mV '
          f'({MAX_AMPLITUDE/1000:.1f} mA)')

    start = time.perf_counter()
    for i, amplitude in enumerate(waveform):
        set_amplitude(ser, amplitude)
        time.sleep(0.005)              # let amplitude settle before trigger
        trigger(ser)

        # Progress every second
        if i % UPDATE_HZ == 0:
            print(f'    t={i / UPDATE_HZ:4.0f}s  amp={amplitude:6.0f} mV '
                  f'({amplitude/1000:.2f} mA)')

        # Drift-compensated wait to the next 100 ms sample boundary
        next_time = start + (i + 1) * sample_interval
        wait = next_time - time.perf_counter()
        if wait > 0:
            time.sleep(wait)

    set_amplitude(ser, 0)              # return to zero at end of cycle


def main():
    print(f'Opening DS5 on {DS5_PORT} ...')
    try:
        ser = serial.Serial(DS5_PORT, 19200, serial.EIGHTBITS,
                            serial.PARITY_NONE, serial.STOPBITS_ONE)
    except serial.SerialException as e:
        print(f'ERROR: could not open {DS5_PORT}: {e}')
        sys.exit(1)
    print('Port open.')

    try:
        # Init sequence (same as ds5.py)
        ser.write(bytearray([78]))         # 'N' zero pulse counter
        time.sleep(0.01)
        ser.write(bytearray([69, 1]))      # 'E' set electrode number 1
        time.sleep(0.01)
        ser.write(bytearray([255]))        # enable
        time.sleep(0.01)

        for idx, pw in enumerate(PULSE_WIDTHS_MS):
            print(f'\n=== Run {idx + 1}/{len(PULSE_WIDTHS_MS)}: '
                  f'pulse width {pw} ms ===')
            run_triangle(ser, pw)
            if idx < len(PULSE_WIDTHS_MS) - 1:
                input('  Done. Press Enter for the next pulse width '
                      '(Ctrl+C to stop)...')
    except KeyboardInterrupt:
        print('\nStopped by user.')
    finally:
        try:
            set_amplitude(ser, 0)
        except Exception:
            pass
        ser.close()
        print('Amplitude zeroed. Port closed.')


if __name__ == '__main__':
    main()
