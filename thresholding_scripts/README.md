# Thermal Thresholding Scripts

MATLAB scripts for determining individual thermal detection and pain thresholds using a TCS II thermode. Implements three psychophysical methods: **Method of Limits**, **Yes/No detection**, and **Two-Interval Forced Choice (2IFC)**.

Used as a pre-scan calibration step to establish participant-specific CDT (cold detection), WDT (warm detection), and HPT (heat pain) thresholds.

Author: Arthur S. Courtin (MIT License)

## Requirements

- MATLAB
- [Psychtoolbox-3](http://psychtoolbox.org/)
- [Palamedes toolbox](https://www.palamedestoolbox.org/) (for Yes/No and 2IFC adaptive methods)
- TCS II thermode connected via serial port
- Windows (serial port uses COM naming)

## Quick Start

```matlab
cd thresholding_scripts
AUD_thresholding_wrapper('all')         % run all three methods
```

A GUI dialog will prompt for participant info and hardware settings. The TCS thermode initialises automatically.

## Task Types

The wrapper accepts a `task_type` argument to select which tasks to run:

| `task_type` | Tasks |
|-------------|-------|
| `'all'` | Method of Limits + Yes/No (CDT, WDT, HPT) + 2IFC (CDT, WDT) |
| `'limits_all'` | Method of Limits only (CDT, WDT, HPT) |
| `'yes_no_all'` | Yes/No for CDT, WDT, HPT |
| `'yes_no_cdt'` | Yes/No CDT only |
| `'yes_no_wdt'` | Yes/No WDT only |
| `'yes_no_hpt'` | Yes/No HPT only |
| `'2ifc_all'` | 2IFC for CDT, WDT |
| `'2ifc_cdt'` | 2IFC CDT only |
| `'2ifc_wdt'` | 2IFC WDT only |
| `'limits_yes_no'` | Method of Limits + Yes/No (CDT, WDT, HPT) |
| `'limits_2ifc'` | Method of Limits + 2IFC (CDT, WDT) |
| `'yes_no_2ifc'` | Yes/No (CDT, WDT, HPT) + 2IFC (CDT, WDT) |

## The Three Methods

### 1. Method of Limits (MLi)

Temperature ramps continuously from baseline toward an extreme (cooling for CDT, heating for WDT/HPT) at 1 C/s. The participant presses a key the moment they detect the sensation. The temperature at button-press is recorded as the threshold.

- All 5 thermode zones active simultaneously
- 3 practice + 3 test trials per modality (CDT, WDT, HPT)
- 60s habituation wait between practice and test
- Return speed 5 C/s (faster than ramp)
- Simple and fast, but susceptible to reaction time bias

### 2. Yes/No Detection (YN)

A brief 2s stimulus is delivered, then the participant reports "Yes I felt it" or "No I didn't". Uses Bayesian adaptive stimulus placement (Palamedes `PAL_AMPM`) to efficiently converge on threshold.

- 30 adaptive trials per modality
- Zones [1,2] and [4,5] alternate across trials
- 30% catch trials (delta=0) for CDT/WDT to estimate false alarm rate
- For pain thresholds (HPT): 10 up-down staircase warm-up trials before the Bayesian phase
- Psychometric function: Cumulative Normal
- Estimates alpha (threshold), beta (slope), gamma (guess rate), lambda (lapse rate)
- Measures CDT, WDT, HPT

### 3. Two-Interval Forced Choice (2IFC)

Two temporal intervals presented sequentially. One contains the stimulus, the other is baseline only. The participant chooses which interval had the stronger thermal sensation.

- 30 trials per modality
- Two 5s intervals per trial, 4s ITI
- Active interval randomised and counterbalanced
- Psychometric function: Weibull, gamma fixed at 0.5 (chance)
- Estimates alpha (threshold), beta (slope), lambda (lapse rate)
- CDT and WDT only (no pain thresholds)
- Criterion-free (controls for response bias)

## Session Workflow

1. **Connect hardware**: attach thermode to participant, connect TCS to PC via serial port
2. **Launch**: `AUD_thresholding_wrapper('all')` (or a subset)
3. **GUI dialog**: enter participant code, status (control/patient), site (LL/UL), COM port, stimulate flag, baseline temperature
4. **TCS initialises**: serial connection opens, baseline temperature set
5. **Method of Limits**: instructions -> habituation (60s) -> practice (3 trials x 3 modalities) -> habituation -> test (3 trials x 3 modalities)
6. **Yes/No**: runs CDT, then WDT, then HPT sequentially. Each: instructions -> 30 adaptive trials (+ 10 up-down warm-up for HPT)
7. **2IFC**: runs CDT, then WDT. Each: instructions -> 30 trials
8. **Done**: results saved as `.mat`, summary plots as `.png`

Press **Escape** to abort any task between trials.

## Configuration

Defaults are set in the wrapper and the `set_params_*.m` files.

**Wrapper defaults** (edit at top of `AUD_thresholding_wrapper.m`):
- `language`: `'FR'` (French) or `'EN'` (English)
- `response_type`: `'keyboard'`, `'mouse'`, or `'button box'`
- `probe`: thermode probe model (`'t03'`, `'t06'`, `'t11'`) — affects ramp speed

**GUI dialog fields**:
- Participant code, status (0=control, 1=patient), site (0=lower limb, 1=upper limb)
- COM port number, stimulate flag (0=no hardware, 1=real), baseline temperature (default 32 C)

**Key task parameters** (in `scripts/set_params_*.m`):

| Parameter | MLi | Yes/No | 2IFC |
|-----------|-----|--------|------|
| Ramp speed | 1 C/s | probe-dependent (t06: 50 C/s) | probe-dependent |
| Return speed | 5 C/s | probe-dependent | probe-dependent |
| Stimulus duration | until response | 2s | 2s |
| Trials per modality | 3+3 | 30 (+10 up-down for pain) | 30 |
| ITI | 5s (10s for HPT) | 4s | 4s |
| CDT range | 0 C floor | 0 to baseline-15 C | 0.2 to 10 C |
| WDT range | 50 C ceiling | 0 to 45-baseline C | 0.2 to 10 C |
| HPT range | 50 C ceiling | 0 to 50-baseline C | n/a |

## Output

All output is saved to `data/<date>/sub-<status><code>/site_<site>/`.

### `.mat` files

| File | Contents |
|------|----------|
| `*_session_info.mat` | GUI dialog responses |
| `*_mli.mat` | Method of Limits: `results` struct (thresholds + temperature recordings), `params` |
| `*_mle_yn_cdt.mat` | Yes/No CDT: `PM` (Palamedes state + threshold convergence), `params` |
| `*_mle_yn_wdt.mat` | Yes/No WDT: same |
| `*_mle_yn_hpt.mat` | Yes/No HPT: same, plus `UD` (up-down staircase state) |
| `*_mle_fc_cdt.mat` | 2IFC CDT: `PM`, `params` |
| `*_mle_fc_wdt.mat` | 2IFC WDT: same |

### Summary plots (`.png`)

| File | Contents |
|------|----------|
| `*_mli.png` | MLi thresholds (delta from baseline) for CDT, WDT, HPT |
| `*_mli_temp.png` | MLi raw temperature recordings per trial |
| `*_yn_*.png` | YN psychometric function fit + parameter convergence (alpha, beta, gamma, lambda) |
| `*_yn_*_temp.png` | YN temperature recordings |
| `*_mle_fc_*.png` | 2IFC psychometric function + convergence |
| `*_mle_fc_*_temp.png` | 2IFC temperature recordings |

## File Structure

```
thresholding_scripts/
  AUD_thresholding_wrapper.m          -- Main entry point
  scripts/
    collect_aud_session_info.m        -- GUI dialog for participant/hardware info
    TCS_initialize.m                  -- Open serial connection, set baseline
    TCS_set_simple_stimulation_parameters.m  -- Configure one TCS stimulation
    stimulate_and_record_temperature.m       -- Fixed-duration stimulation + temp recording
    stimulate_until_resp.m                   -- Stimulate until keypress (Method of Limits)
    collect_binary_response.m         -- Left/right or yes/no response collection
    make_fixation_cross.m             -- Psychtoolbox fixation cross texture
    make_response_type_images.m       -- Load button/key images for response prompts
    set_params_method_of_limits_thresholding_task.m   -- MLi parameters + instructions
    set_params_yes_no_thresholding_task.m              -- YN parameters + instructions
    set_params_performance_2ifc_thresholding_task.m    -- 2IFC parameters + instructions
    run_method_of_limits_thresholding_task.m   -- MLi task execution
    run_yes_no_thresholding_task.m              -- YN task execution
    run_performance_2ifc_thresholding_task.m    -- 2IFC task execution
    make_summary_plot_MLi.m           -- MLi threshold plot
    make_summary_plot_MLi_temp.m      -- MLi temperature recording plot
    make_summary_plot_yes_no.m        -- YN psychometric + convergence plot
    make_summary_plot_performance_2ifc.m  -- 2IFC psychometric + convergence plot
    make_summary_plot_temp_recordings.m   -- Temperature recording overlay plot
    LK.mat, LC.mat, LB.mat           -- Button/key image masks
```

## Call Graph

```
AUD_thresholding_wrapper
  ├── collect_aud_session_info
  ├── TCS_initialize
  │
  ├── run_method_of_limits_thresholding_task
  │     ├── set_params_method_of_limits_thresholding_task
  │     ├── make_response_type_images
  │     ├── collect_binary_response
  │     └── stimulate_until_resp
  ├── make_summary_plot_MLi
  ├── make_summary_plot_MLi_temp
  │
  ├── run_yes_no_thresholding_task  (x3: CDT, WDT, HPT)
  │     ├── set_params_yes_no_thresholding_task
  │     ├── PAL_AMPM_*  (Palamedes)
  │     ├── TCS_set_simple_stimulation_parameters
  │     ├── stimulate_and_record_temperature
  │     ├── make_fixation_cross
  │     ├── make_response_type_images
  │     └── collect_binary_response
  ├── make_summary_plot_yes_no  (x3)
  ├── make_summary_plot_temp_recordings  (x3)
  │
  ├── run_performance_2ifc_thresholding_task  (x2: CDT, WDT)
  │     ├── set_params_performance_2ifc_thresholding_task
  │     ├── PAL_AMPM_*  (Palamedes)
  │     ├── TCS_set_simple_stimulation_parameters
  │     ├── stimulate_and_record_temperature
  │     ├── make_fixation_cross
  │     ├── make_response_type_images
  │     └── collect_binary_response
  ├── make_summary_plot_performance_2ifc  (x2)
  └── make_summary_plot_temp_recordings  (x2)
```
