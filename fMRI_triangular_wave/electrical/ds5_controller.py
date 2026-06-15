"""
Digitimer DS5 isolated bipolar constant current stimulator — serial interface.

The DS5 delivers constant current pulses proportional to a voltage command.
Communication is via USB serial at 19200 baud.

Serial protocol (derived from collaborator reference script + DS5 manual):
    Command bytes:
        W + hByte + lByte  — set pulse width (value = duration_ms * 10)
        S + hByte + lByte  — set pulse voltage/amplitude (value = millivolts * 2)
        P                  — trigger one pulse
        N                  — zero the pulse counter
        E + electrode_num  — set electrode number
        0xFF               — enable/init

    Multi-byte values are encoded as 16-bit big-endian:
        value = hByte * 256 + lByte

Output current depends on the DS5 front panel range setting:
    ±1V  input → ±10mA output  (10 mA/V)
    ±2.5V input → ±25mA output (10 mA/V)
    ±5V  input → ±25mA output  ( 5 mA/V)
    ±10V input → ±50mA output  ( 5 mA/V)
"""

import time


def _encode_16bit(value):
    """Encode an integer value as two bytes (high, low)."""
    value = int(round(value))
    value = max(0, min(65535, value))
    high = value // 256
    low = value % 256
    return high, low


class DS5Controller:
    """Wrapper around the Digitimer DS5 serial interface."""

    def __init__(self, port='COM8', simulation=False):
        self.simulation = simulation
        self.port_name = port
        self._pulse_width_ms = 0
        self._amplitude_mv = 0

        if not self.simulation:
            import serial
            self.ser = serial.Serial(port, 19200,
                                     bytesize=8,
                                     parity='N',
                                     stopbits=1,
                                     timeout=2)
            time.sleep(0.1)
            # Zero pulse counter
            self.ser.write(bytearray([0x4E]))  # 'N'
            time.sleep(0.01)
            # Set electrode number
            self.ser.write(bytearray([0x45, 1]))  # 'E', 1
            time.sleep(0.01)
            # Enable
            self.ser.write(bytearray([0xFF]))
            time.sleep(0.01)

    def set_pulse_width(self, duration_ms):
        """Set pulse width in milliseconds.

        Parameters
        ----------
        duration_ms : float
            Pulse duration (e.g. 0.5, 1.0, 2.0 ms). Resolution: 0.1 ms.
        """
        self._pulse_width_ms = duration_ms
        if not self.simulation:
            value = duration_ms * 10  # 0.1 ms units
            h, l = _encode_16bit(value)
            self.ser.write(bytearray([0x57, h, l]))  # 'W'
            time.sleep(0.01)

    def set_amplitude(self, millivolts):
        """Set pulse amplitude as DS5 input voltage in millivolts.

        The actual output current depends on the DS5 front panel range:
            millivolts=1000 (1V) at ±10mA range → 10 mA
            millivolts=1000 (1V) at ±25mA/2.5V range → 10 mA
            millivolts=1000 (1V) at ±25mA/5V range → 5 mA

        Parameters
        ----------
        millivolts : float
            Input voltage in mV (e.g. 100 = 0.1V, 500 = 0.5V).
        """
        self._amplitude_mv = millivolts
        if not self.simulation:
            value = millivolts * 2  # DS5 encoding
            h, l = _encode_16bit(value)
            self.ser.write(bytearray([0x53, h, l]))  # 'S'
            time.sleep(0.005)

    def trigger(self):
        """Trigger a single pulse with the current amplitude and width."""
        if not self.simulation:
            self.ser.write(bytearray([0x50]))  # 'P'

    def close(self):
        """Close the serial connection."""
        if not self.simulation:
            self.ser.close()
