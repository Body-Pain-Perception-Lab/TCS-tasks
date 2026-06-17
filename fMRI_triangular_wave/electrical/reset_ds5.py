#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency reset for the Digitimer DS5: set the stimulator output to 0 mV.

Use this after a crash, abort, or fault to make sure the DS5 is not left
holding a non-zero amplitude.

Usage:
    python reset_ds5.py                 # default port COM8 (Windows)
    python reset_ds5.py --port COM3
    python reset_ds5.py --port /dev/ttyUSB0
"""

import argparse
import os
import sys

# Make the shared driver in PythonHelpers/ importable regardless of cwd.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'PythonHelpers'))

from DS5Control_python3_BPPlab import DS5Controller
from io_utils import detect_serial_port


def main():
    _, default_port = detect_serial_port()
    parser = argparse.ArgumentParser(
        description='Reset the Digitimer DS5 output to 0 mV.')
    parser.add_argument('--port', default=default_port,
                        help='DS5 serial port (default: %(default)s)')
    args = parser.parse_args()

    print('Opening DS5 on {} ...'.format(args.port))
    try:
        ds5 = DS5Controller(port=args.port)
    except Exception as e:
        print('ERROR: could not open {}: {}'.format(args.port, e))
        sys.exit(1)

    try:
        ds5.reset()
        print('DS5 reset to 0 mV.')
    finally:
        ds5.close()


if __name__ == '__main__':
    main()
