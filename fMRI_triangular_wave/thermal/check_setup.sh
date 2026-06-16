#!/usr/bin/env bash
# Check that the environment is ready to run the thermal pRF experiment.
# Usage: bash check_setup.sh [--thermode]
#   --thermode  also run the thermode pre-check (requires hardware or --sim)

set -uo pipefail

PASS=0
FAIL=0
WARN=0

RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}[FAIL] $1${NC}"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}[WARN] $1${NC}"; ((WARN++)); }

echo "=== Environment check ==="
echo

# --- 0. Check for active conda/venv environment ---
if [ -n "${CONDA_DEFAULT_ENV:-}" ]; then
    pass "Conda environment active: $CONDA_DEFAULT_ENV"
elif [ -n "${VIRTUAL_ENV:-}" ]; then
    pass "Virtual environment active: $(basename "$VIRTUAL_ENV")"
else
    warn "No conda/venv active — packages may not be found. Try: conda activate psychopy"
fi

# --- 1. Find a working Python 3 command ---
PYTHON=""
for cmd in python3 python py; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        if echo "$ver" | grep -q "Python 3"; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3 not found. Tried: python3, python, py"
    echo "       Install from https://www.python.org/downloads/"
    echo
    echo "=== Cannot continue without Python. ==="
    exit 1
else
    ver=$("$PYTHON" --version 2>&1)
    pass "Python found: $PYTHON ($ver)"
fi

# --- 2. Check Python version >= 3.8 ---
if "$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
    pass "Python >= 3.8"
else
    fail "Python too old — need 3.8+"
fi

# --- 3. Check required packages ---
for pkg in psychopy numpy scipy matplotlib; do
    if "$PYTHON" -c "import $pkg" 2>/dev/null; then
        pass "$pkg installed"
    else
        fail "$pkg not installed — run: $PYTHON -m pip install $pkg"
    fi
done

# --- 4. Check TcsControl library (only needed for real hardware) ---
if "$PYTHON" -c "import TcsControl_python3_BPPlab" 2>/dev/null; then
    pass "TcsControl_python3_BPPlab installed"
else
    warn "TcsControl_python3_BPPlab not found (only needed when simulation = False)"
fi

# --- 5. Detect serial ports and access (platform-specific) ---
if [[ "$OSTYPE" == linux* ]]; then
    ports=$(ls /dev/ttyACM* 2>/dev/null || true)
    if [ -n "$ports" ]; then
        pass "Serial port(s) found: $ports"
        echo "       Set com_port in config_v3.py to the correct one"
    else
        warn "No /dev/ttyACM* ports found (thermode not connected or not powered on)"
    fi
    if groups | grep -q dialout; then
        pass "User is in dialout group (serial port access)"
    else
        warn "User not in dialout group — run: sudo usermod -aG dialout \$USER"
    fi
elif [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* || "$OSTYPE" == win* ]]; then
    ports=$(powershell.exe -Command "[System.IO.Ports.SerialPort]::GetPortNames()" 2>/dev/null | tr -d '\r' || true)
    if [ -n "$ports" ]; then
        pass "COM port(s) found: $(echo $ports | tr '\n' ' ')"
        echo "       Set com_port in config_v3.py to the correct one"
    else
        warn "No COM ports found (thermode not connected or not powered on)"
    fi
elif [[ "$OSTYPE" == darwin* ]]; then
    ports=$(ls /dev/tty.usbmodem* /dev/cu.usbmodem* 2>/dev/null || true)
    if [ -n "$ports" ]; then
        pass "Serial port(s) found: $ports"
        echo "       Set com_port in config_v3.py to the correct one"
    else
        warn "No USB serial ports found (thermode not connected or not powered on)"
    fi
fi

# --- 6. Check that config and key scripts exist ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in config_v3.py run_experiment.py thermode_precheck.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        pass "$f found"
    else
        fail "$f missing from $SCRIPT_DIR"
    fi
done

# --- 7. Thermode pre-check (optional) ---
if [[ "${1:-}" == "--thermode" ]]; then
    echo
    echo "=== Thermode pre-check ==="
    "$PYTHON" "$SCRIPT_DIR/thermode_precheck.py" && pass "Thermode responsive" || fail "Thermode pre-check failed"
fi

# --- Summary ---
echo
echo "=== Summary: $PASS passed, $FAIL failed, $WARN warnings ==="
[ "$FAIL" -eq 0 ] && echo "Ready to run." || echo "Fix the failures above before running."
exit "$FAIL"
