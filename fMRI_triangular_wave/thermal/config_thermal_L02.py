"""
Configuration for fMRI tprf thermode experiment — Leipzig session 02.
Slower ramp rate (2.0 C/s vs 2.5 C/s) for better temperature resolution
(3.0 C per TR instead of 3.75 C), with 10 cycles per half.

Run timing (each run = two halves with mid-run pause):
    Dummy volumes:   4 x 1.5s =   6.0s
    Pre-baseline:                  6.0s
    Half 1:         10 x  35s = 350.0s
    Mid-run pause:                30.0s  (baseline temperature)
    Half 2:         10 x  35s = 350.0s
    Post-baseline:                 6.0s
    ─────────────────────────────────────
    Total:                       742.0s = 12 min 22s ≈ 495 volumes

4 runs per session (each run combines two halves with opposite direction):
    Group A (nontgi_warm_first = True):
        Run 1: NonTGI  [warm-first → pause → cool-first]
        Run 2: NonTGI  [cool-first → pause → warm-first]
        Run 3: TGI     [warm-first → pause → cool-first]
        Run 4: TGI     [cool-first → pause → warm-first]
    Group B (nontgi_warm_first = False):
        Run 1: NonTGI  [cool-first → pause → warm-first]
        Run 2: NonTGI  [warm-first → pause → cool-first]
        Run 3: TGI     [cool-first → pause → warm-first]
        Run 4: TGI     [warm-first → pause → cool-first]

Total scanning time: 4 x 742s = 2968s ≈ 49 min 28s (plus inter-run gaps)
"""

CONFIG = {
    # Thermal
    'baseline_temp': 30.0,       # degrees C
    'temp_min': 10.0,            # degrees C (safety clamp lower bound)
    'temp_max': 50.0,            # degrees C (safety clamp upper bound)
    'max_delta': 17.5,           # degrees C amplitude
    'ramp_rate': 50.0,           # degrees C/s (TCS hardware ramp speed in follow mode)
                                 # Must be >> waveform rate (2.0 C/s) so the hardware
                                 # can reach each 10Hz micro-step within 100ms.
                                 # 50 C/s accounts for the MRI filter on the TCS cable.
    'cycle_duration': 35.0,      # seconds per full bipolar triangle cycle (0.0286 Hz)
                                 # ramp rate = 4 * 17.5 / 35 = 2.0 C/s
    'cycles_per_half': 10,       # 10 full cycles per half (20 total per run)
    'mid_run_pause': 30.0,       # seconds at baseline between the two halves
    'baseline_buffer': 6.0,      # seconds of baseline before/after run

    # Update rate
    'update_hz': 10,             # thermode update frequency

    # MR
    'trigger_mode': 'parallel',  # 'keyboard' (key press) or 'parallel' (parallel port)
    'trigger_key': 't',          # scanner trigger key (keyboard mode)
    'parallel_port': 0,          # parallel port address (parallel mode, Leipzig 7T)
    'TR': 1.5,                   # seconds
    'dummy_volumes': 4,
    'emulate': False,            # True = use space instead of trigger

    # Mask selection
    'nontgi_mask': 'P1',        # single NonTGI mask: all 4 zones (+1,+1,+1,+1,0)
    'tgi_mask': 'TGI',          # TGI mask (same for all participants)

    # Block order counterbalancing
    # True  = Group A: NonTGI warm-first, NonTGI cool-first, TGI warm, TGI cool
    # False = Group B: NonTGI cool-first, NonTGI warm-first, TGI warm, TGI cool
    'nontgi_warm_first': True,

    # Thermode
    'com_port': '/dev/ttyACM0',          # serial port (Windows: 'COM7'; Linux: '/dev/ttyACM0')
    'tcs_filter': 'medium',          # TCS MRI cable filter: None, 'low', 'medium', 'high'
                                 # Set to 'medium' at Leipzig 7T (reduces MRI interference)
    'simulation': False,         # True = no thermode commands

    # VAS ratings
    'vas_enabled': False,            # disabled for pilot
    'vas_max_duration': 8.0,         # seconds per question
    'vas_labels': ['Not at all', 'Extremely'],

    # Display
    'fullscreen': False,         # True for scanner
    'screen_index': 0,           # 0 = primary, 1 = extended display
}
