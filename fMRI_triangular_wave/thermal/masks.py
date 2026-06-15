"""
Spatial mask definitions for TGI and Non-TGI conditions.

Each participant receives one NonTGI mask and one TGI mask.
Each mask is presented for an entire run with the same waveform.
Warm-first and cool-first runs reverse the waveform direction,
which handles polarity — so each spatial configuration only needs
one mask (no _W/_C variants).

NonTGI mask (P1 vs P3) is counterbalanced across participants via config.
"""

# Non-TGI masks: 2 spatial positions (4-bar thermode, zones 1-4)
# P1 = zones 1,2 (proximal)  P3 = zones 3,4 (distal)
NONTGI_MASKS = {
    'P1': [+1, +1,  0,  0,  0],
    'P3': [ 0,  0, +1, +1,  0],
}

# TGI mask: alternating warm/cool pattern
TGI_MASKS = {
    'TGI': [+1, -1, +1, -1,  0],
}

# Combined lookup for convenience
ALL_MASKS = {**NONTGI_MASKS, **TGI_MASKS}


def get_mask(name):
    """Look up a mask by name.

    Returns
    -------
    list of int
        5-element mask array.

    Raises
    ------
    KeyError
        If mask name is not found.
    """
    return ALL_MASKS[name]
