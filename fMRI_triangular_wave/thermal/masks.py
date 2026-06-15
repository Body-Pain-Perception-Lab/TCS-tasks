"""
Spatial mask definitions for TGI and Non-TGI conditions.

Each participant receives one NonTGI mask and one TGI mask.
Each mask is presented for an entire run with the same waveform.
Warm-first and cool-first runs reverse the waveform direction,
which handles polarity — so each spatial configuration only needs
one mask (no _W/_C variants).
"""

# Non-TGI mask: all 4 active zones in phase (zone 5 unused)
NONTGI_MASKS = {
    'P1': [+1, +1, +1, +1,  0],
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
