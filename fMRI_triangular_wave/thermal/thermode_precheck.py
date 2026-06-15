"""
Pre-check thermode tracking before committing the scanner.

Runs a short test ramp (~12s) without the scanner to confirm all zones
can track setpoints. If actuals can't follow commanded temperatures,
the thermode hasn't recovered from overheating.

Usage:
    python thermode_precheck.py              # uses config.py settings
    python thermode_precheck.py --sim        # simulation mode (dry run)

Pass/fail criteria:
    - Mean tracking error across active zones must be < 1.5 °C
    - Max tracking error must be < 4.0 °C
    - No zone may show zero responsiveness (flat actual despite changing setpoint)
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

from config_v3 import CONFIG
from thermode import ThermodeController


# Test ramp parameters
RAMP_DELTA = 5.0        # °C above baseline (modest — enough to test tracking)
RAMP_DURATION = 6.0     # seconds to ramp up
HOLD_DURATION = 2.0     # seconds to hold at peak
RETURN_DURATION = 6.0   # seconds to ramp back down
UPDATE_HZ = 10

# Pass/fail thresholds
MAX_MEAN_ERROR = 1.5    # °C — mean |cmd - actual| across the ramp
MAX_PEAK_ERROR = 4.0    # °C — worst single-sample error
MIN_RESPONSIVENESS = 1.0  # °C — minimum actual temp change required


def _get_config_source():
    """Return the filename that CONFIG was imported from."""
    for name, mod in sys.modules.items():
        if name == __name__ or mod is None:
            continue
        if hasattr(mod, 'CONFIG') and mod.CONFIG is CONFIG:
            src = getattr(mod, '__file__', None)
            if src:
                return os.path.basename(src)
            return name
    return 'unknown'


def _save_report(passed, zone_results, config, simulation=False):
    """Save precheck results + full config to a timestamped JSON file."""
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'precheck_{timestamp}.json')

    report = {
        'timestamp': timestamp,
        'result': 'PASS' if passed else 'FAIL',
        'simulation': simulation,
        'config_source': _get_config_source(),
        'config': config,
        'test_ramp': {
            'ramp_delta': RAMP_DELTA,
            'ramp_duration': RAMP_DURATION,
            'hold_duration': HOLD_DURATION,
            'return_duration': RETURN_DURATION,
            'update_hz': UPDATE_HZ,
        },
        'thresholds': {
            'max_mean_error': MAX_MEAN_ERROR,
            'max_peak_error': MAX_PEAK_ERROR,
            'min_responsiveness': MIN_RESPONSIVENESS,
        },
        'zones': zone_results,
    }

    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'Report saved: {out_path}')


def run_precheck(simulation=False):
    """Run the thermode pre-check and return (passed, details_dict)."""
    config = dict(CONFIG)
    config['simulation'] = simulation

    baseline = config['baseline_temp']
    peak = baseline + RAMP_DELTA
    dt = 1.0 / UPDATE_HZ

    # Build setpoint trajectory: ramp up → hold → ramp down
    n_up = int(RAMP_DURATION * UPDATE_HZ)
    n_hold = int(HOLD_DURATION * UPDATE_HZ)
    n_down = int(RETURN_DURATION * UPDATE_HZ)
    n_total = n_up + n_hold + n_down

    setpoints = []
    for i in range(n_up):
        frac = i / n_up
        setpoints.append(baseline + frac * RAMP_DELTA)
    for _ in range(n_hold):
        setpoints.append(peak)
    for i in range(n_down):
        frac = i / n_down
        setpoints.append(peak - frac * RAMP_DELTA)

    total_time = n_total * dt
    print(f'Thermode pre-check: {total_time:.0f}s test ramp '
          f'({baseline:.0f} → {peak:.0f} → {baseline:.0f} °C)')
    print(f'Connecting to thermode (simulation={simulation})...')

    thermode = ThermodeController(config)
    print('Connected. Starting test ramp...\n')

    # Collect data
    errors_per_zone = [[] for _ in range(5)]
    actuals_per_zone = [[] for _ in range(5)]
    clock_start = time.monotonic()

    try:
        for sample_idx in range(n_total):
            target_time = sample_idx * dt
            temp = setpoints[sample_idx]
            temps_cmd = [temp] * 5

            thermode.set_temperatures(temps_cmd)
            actuals = thermode.get_temperatures()

            for z in range(5):
                a = actuals[z]
                if not math.isnan(a):
                    errors_per_zone[z].append(abs(temp - a))
                    actuals_per_zone[z].append(a)

            # Progress bar
            pct = (sample_idx + 1) / n_total * 100
            phase = ('ramp-up' if sample_idx < n_up
                     else 'hold' if sample_idx < n_up + n_hold
                     else 'ramp-down')
            print(f'\r  [{pct:5.1f}%] {phase:>10s}  '
                  f'cmd={temp:.1f}°C  '
                  f'act=[{actuals[0]:5.1f} {actuals[1]:5.1f} '
                  f'{actuals[2]:5.1f} {actuals[3]:5.1f} {actuals[4]:5.1f}]',
                  end='', flush=True)

            # Timing
            elapsed = time.monotonic() - clock_start - target_time
            wait = dt - elapsed
            if wait > 0:
                time.sleep(wait)

    finally:
        print('\n\nReturning to baseline...')
        thermode.set_baseline()
        time.sleep(0.5)
        thermode.close()

    # --- Evaluate results ---
    print('\n--- Results ---')

    if simulation:
        print('SIMULATION MODE — no real tracking data.')
        print('Pre-check logic verified OK. Run without --sim for real test.')
        _save_report(True, [], config, simulation=True)
        return True, {}

    zone_results = []
    any_fail = False

    for z in range(5):
        errs = errors_per_zone[z]
        acts = actuals_per_zone[z]
        if not errs:
            print(f'  Zone {z+1}: NO DATA (NaN readings)')
            zone_results.append({'zone': z + 1, 'status': 'NO_DATA'})
            any_fail = True
            continue

        mean_err = sum(errs) / len(errs)
        max_err = max(errs)
        temp_range = max(acts) - min(acts)

        status = 'PASS'
        issues = []
        if mean_err > MAX_MEAN_ERROR:
            issues.append(f'mean error {mean_err:.2f}°C > {MAX_MEAN_ERROR}°C')
            status = 'FAIL'
        if max_err > MAX_PEAK_ERROR:
            issues.append(f'max error {max_err:.2f}°C > {MAX_PEAK_ERROR}°C')
            status = 'FAIL'
        if temp_range < MIN_RESPONSIVENESS:
            issues.append(f'actual range {temp_range:.2f}°C < {MIN_RESPONSIVENESS}°C (unresponsive)')
            status = 'FAIL'

        if status == 'FAIL':
            any_fail = True

        issue_str = '; '.join(issues) if issues else ''
        print(f'  Zone {z+1}: {status}  '
              f'mean_err={mean_err:.2f}°C  max_err={max_err:.2f}°C  '
              f'range={temp_range:.2f}°C'
              f'{"  !! " + issue_str if issue_str else ""}')

        zone_results.append({
            'zone': z + 1, 'status': status,
            'mean_error': mean_err, 'max_error': max_err,
            'actual_range': temp_range,
        })

    passed = not any_fail
    print(f'\n{"=" * 50}')
    if passed:
        print('RESULT: PASS — all zones tracking normally. Safe to start run.')
    else:
        print('RESULT: FAIL — thermode not tracking. Wait and retry.')
    print(f'{"=" * 50}')

    _save_report(passed, zone_results, config)
    return passed, {'zones': zone_results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Thermode tracking pre-check')
    parser.add_argument('--sim', action='store_true',
                        help='Run in simulation mode (no hardware)')
    args = parser.parse_args()

    passed, _ = run_precheck(simulation=args.sim)
    sys.exit(0 if passed else 1)
