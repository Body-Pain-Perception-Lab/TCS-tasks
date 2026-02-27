"""
Configuration for fMRI tprf thermode experiment.
All configurable parameters in one place.
"""

CONFIG = {
    # Thermal
    'baseline_temp': 30.0,       # degrees C
    'temp_min': 10.0,            # degrees C (safety clamp lower bound)
    'temp_max': 50.0,            # degrees C (safety clamp upper bound)
    'max_delta': 17.5,           # degrees C amplitude
    'ramp_rate': 50.0,           # degrees C/s (TCS hardware ramp speed in follow mode)
                                 # Must be >> waveform rate (~2.5 C/s peak) so the hardware
                                 # can reach each 10Hz micro-step within 100ms.
                                 # 50 C/s accounts for the MRI filter on the TCS cable.
    'cycle_duration': 28.0,      # seconds per full bipolar sinusoidal cycle (0.0357 Hz)
    'cycles_per_block': 25,      # 25 full cycles
    'baseline_buffer': 3.5,      # seconds of baseline before/after block

    # Update rate
    'update_hz': 10,             # thermode update frequency

    # MR
    'trigger_key': 't',          # scanner trigger key
    'TR': 1.5,                   # seconds
    'dummy_volumes': 4,
    'emulate': False,            # True = use space instead of trigger

    # Mask selection
    'nontgi_mask': 'P1',        # which NonTGI mask: 'P1' (zones 1,2) or 'P3' (zones 3,4)
                                # counterbalanced across participants
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
