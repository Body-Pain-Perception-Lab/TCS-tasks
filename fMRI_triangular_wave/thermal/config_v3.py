"""
Configuration for fMRI tprf thermode experiment — v3.
Same timing as v2. NonTGI mask changed to all 4 zones (P1: zones 1-4 all +1).

Run timing:
    Dummy volumes:   4 x 1.5s =   6.0s
    Pre-baseline:                  6.0s
    Stimulation:    12 x  28s = 336.0s
    Post-baseline:                 6.0s
    ─────────────────────────────────────
    Total:                       354.0s = 5 min 54s = 236 volumes

8 runs per session (each unique run presented twice):
    Group A (nontgi_warm_first = True):
        Run 1: NonTGI warm-first
        Run 2: NonTGI cool-first
        Run 3: NonTGI warm-first
        Run 4: NonTGI cool-first
        Run 5: TGI warm-first
        Run 6: TGI cool-first
        Run 7: TGI warm-first
        Run 8: TGI cool-first
    Group B (nontgi_warm_first = False):
        Run 1: NonTGI cool-first
        Run 2: NonTGI warm-first
        Run 3: NonTGI cool-first
        Run 4: NonTGI warm-first
        Run 5: TGI cool-first
        Run 6: TGI warm-first
        Run 7: TGI cool-first
        Run 8: TGI warm-first

Total scanning time: 8 x 354s = 2832s = 47 min 12s (plus inter-run gaps)
"""

CONFIG = {
    # Thermal
    'baseline_temp': 30.0,       # degrees C
    'temp_min': 10.0,            # degrees C (safety clamp lower bound)
    'temp_max': 50.0,            # degrees C (safety clamp upper bound)
    'max_delta': 17.5,           # degrees C amplitude
    'ramp_rate': 50.0,           # degrees C/s (TCS hardware ramp speed in follow mode)
                                 # Must be >> waveform rate (2.5 C/s) so the hardware
                                 # can reach each 10Hz micro-step within 100ms.
                                 # 50 C/s accounts for the MRI filter on the TCS cable.
    'cycle_duration': 28.0,      # seconds per full bipolar triangle cycle (0.0357 Hz)
                                 # ramp rate = 4 * 17.5 / 28 = 2.5 C/s
    'cycles_per_block': 12,      # 12 full cycles per run
    'baseline_buffer': 6.0,      # seconds of baseline before/after block

    # Update rate
    'update_hz': 10,             # thermode update frequency

    # MR
    'trigger_key': 't',          # scanner trigger key
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
    'com_port': 'COM3',          # serial port
    'simulation': False,         # True = no thermode commands

    # VAS ratings
    'vas_enabled': False,            # disabled for pilot
    'vas_max_duration': 8.0,         # seconds per question
    'vas_labels': ['Not at all', 'Extremely'],

    # Display
    'fullscreen': True,          # True for scanner
    'screen_index': 1,           # 0 = primary, 1 = extended display
}
