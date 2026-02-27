# Session Guide — fMRI Thermal pRF Experiment

Step-by-step instructions for running a full session (8 runs) with the live QC monitor.

## Pre-Session Setup

### 1. Configure participant parameters

Edit `config_v2.py` before launching:

```python
# Assign NonTGI mask for this participant (counterbalanced across participants)
'nontgi_mask': 'P1',       # Options: P1 (zones 1-2) or P3 (zones 3-4)
'tgi_mask': 'TGI',         # Same for all participants

# Run order counterbalancing
'nontgi_warm_first': True,  # True = Group A, False = Group B
```

### 2. Set hardware mode

For **simulation** (testing without thermode/scanner):

```python
'simulation': True,
'emulate': True,        # space bar instead of scanner trigger
'fullscreen': False,
```

For **real scanning**:

```python
'simulation': False,
'emulate': False,
'com_port': 'COM3',     # adjust to your serial port
'fullscreen': True,
'screen_index': 1,      # projector screen
```

## Running a Run

### Terminal 1 — Experiment

```bash
cd fMRI_triangular_wave
python run_experiment.py
```

1. **Dialog 1**: enter participant ID (e.g. `0001`) and session (`01`)
2. **Dialog 2**: review 8-run plan with timing info (236 volumes, 5m 54s per run), select run, confirm hardware settings
3. **Trigger**: press space (emulation) or wait for scanner trigger (`t` key)
4. **Stimulation**: 6s baseline → 12 x 28s cycles → 6s baseline (5 min 54s)
5. **Ratings**: 3 VAS questions if enabled (8s timeout each)
6. Script exits — run again for the next run

### Terminal 2 — QC Monitor (open before starting the run)

```bash
cd fMRI_triangular_wave
python qc_monitor.py
```

The monitor auto-detects the most recent thermode TSV in `data/`. To target a specific file:

```bash
python qc_monitor.py data/sub-0001/ses-01/func/sub-0001_ses-01_task-tprf_run-01_thermode_*.tsv
```

The dashboard shows two live panels updated every 2 seconds:

| Panel | What to look for |
|-------|-----------------|
| **Zone temperatures** | Actual readings (solid) closely following commanded (faint dotted) |
| **Temperature error** | All zones below the red 2 C warning line |

### Timing reference

| Phase | Duration |
|-------|----------|
| Dummy volumes | 6.0 s |
| Pre-baseline | 6.0 s |
| Stimulation (12 x 28s cycles) | 336.0 s |
| Post-baseline | 6.0 s |
| **Total per run** | **354 s (5 min 54s) = 236 volumes** |

## Full 8-Run Session

Run each run as a separate invocation of `run_experiment.py`. The run plan auto-tracks completion.

**Group A** (`nontgi_warm_first = True`):

| Run | Condition | Direction |
|-----|-----------|-----------|
| 1 (`run-01`) | NonTGI | warm-first |
| 2 (`run-02`) | NonTGI | cool-first |
| 3 (`run-03`) | NonTGI | warm-first |
| 4 (`run-04`) | NonTGI | cool-first |
| 5 (`run-05`) | TGI | warm-first |
| 6 (`run-06`) | TGI | cool-first |
| 7 (`run-07`) | TGI | warm-first |
| 8 (`run-08`) | TGI | cool-first |

**Group B**: same but cool-first before warm-first in each pair.

**Total scanning time: 8 x 354s = 47 min 12s** (plus inter-run gaps).

Between runs:
- The QC monitor window can stay open — it will pick up the new file on next launch, or you can restart it
- Take breaks as needed; there is no inter-run timer
- Check the console QC output for each cycle (ramp rate, temp error, flags)

## Output Files

After each run, four files are saved to `data/sub-{ID}/ses-{session}/func/`:

```
sub-0001_ses-01_task-tprf_run-01_events_20260227T140000.tsv     # BIDS events
sub-0001_ses-01_task-tprf_run-01_thermode_20260227T140000.tsv   # 10 Hz thermode recording
sub-0001_ses-01_task-tprf_run-01_thermode_20260227T140000.json  # JSON sidecar (metadata)
sub-0001_ses-01_task-tprf_run-01_qc_20260227T140000.tsv         # per-cycle QC metrics
```

Re-running a run creates new files with a different timestamp (never overwrites).

## QC Checklist

After each run, verify in the console output:

- [ ] `onset_lat` is consistent across cycles (hardware response delay)
- [ ] `ramp` is close to 2.50 deg/s (expected ramp rate)
- [ ] `warm` and `cool` rates are similar (no large asymmetry)
- [ ] `err` stays below 2.0 C (mean temperature error)
- [ ] `flags=0` or very low (ramp rate deviation count)

In the QC monitor dashboard:

- [ ] Actual temperatures (solid) closely follow commanded (faint dotted)
- [ ] Temperature error stays below the 2 C red warning line
- [ ] Only active zones are plotted (inactive zones hidden)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| QC monitor shows "No thermode TSV files found" | Start the experiment first — the TSV is created at launch |
| QC monitor shows stale data | Close and reopen `qc_monitor.py` to pick up the latest file |
| Monitor picks up wrong file | Pass the file path explicitly: `python qc_monitor.py path/to/file.tsv` |
| High temperature error in QC | Check thermode connections; may indicate hardware lag or communication issue |
| Escape pressed during run | Run aborts; thermode returns to baseline; data up to that point is saved |
