# `y1rds` model change: ±1 fan-out replaced with a mux matrix

> ## ✅ DONE AND VERIFIED — 2026-09-08
>
> Built on cymac1 at 17:31, installed and restarted the same evening. Verified
> from `V{n}_OUT_DQ` with the oscillator at `DRV_FREQ = 0.32 Hz`, gains 2000,
> **output switches still disabled** so nothing reached the chamber:
>
> | | amplitude | phase | relative |
> |---|---|---|---|
> | V2 (A) | **2000.0** | −43.07° | 0.00° |
> | V4 (B) | **2000.0** | −163.07° | **−120.00°** |
> | V3 (C) | **2000.0** | +76.93° | **+120.00°** |
> | V1 (CTR) | 0.0 | — | silent, as specified |
>
> Amplitudes identical to five significant figures and equal to the commanded
> oscillator gain; relative phases exact to the hundredth of a degree; DC zero
> throughout. That clears the same bar as the verified 2026-08-24 and 08-28
> runs, **from the oscillator with no AWG involved**. Step sense is V2 → V4 → V3
> at −120° each, matching the 08-24 convention, so no sign flip was needed.
>
> ### Commissioning finding: the electrode input switch gates the matrix
>
> The matrix output is summed into `Sum*[2]`, upstream of each electrode filter
> module, so `V{n}` receives the matrix drive and the LES/MON signal as a single
> summed input. The module's SW1 input bit therefore gates both together. On the
> first test V3 and V4 responded (`SW1R = 12`) while V1 and V2 were silent
> (`SW1R = 8`, input bit clear); setting `V1_SW1S` and `V2_SW1S` to 12 restored
> them.
>
> The consequence for LES decoupling is that the electrode input switch is the
> wrong place to separate the two signals, since by that point they have already
> been added. Separation must occur at the source, upstream of the Sum.
>
> ### Isolating LES/MON: source output switch, not source gain
>
> Each source is isolated at its own **output switch**, with its gain left at the
> nominal value. Configuration verified 2026-09-09:
>
> | module | GAIN | SW2R | output |
> |---|---|---|---|
> | `LES_PIT` | 1.000 | 512 | off |
> | `LES_YAW` | 1.000 | 512 | off |
> | `LES_SUM` | 0.000 | 512 | off |
> | `MON` | 0.000 | 512 | off |
>
> The output switch is preferred to zeroing the gain for three reasons. Its state
> is a boolean and is unambiguous in `SW2R`. The gain is a calibration value
> worth preserving rather than overwriting and later having to restore. And gain
> changes are ramped over `TRAMP`, so they pass through intermediate values,
> whereas the switch acts cleanly within one sample.
>
> Sensing is unaffected by either method: `LES_*_IN1_DQ` records upstream of both
> the gain and the output switch.
>
> ### Record names — NOT what was predicted
>
> A ramp matrix does **not** use a `_GAIN` suffix (that was extrapolated from
> Aaron's `ACTS`, which is a *filter* matrix). The real interface:
>
> ```
> Y1:RDS-OUTS_DRVMTRX_SETTING_{r}_{c}    write the value here
> Y1:RDS-OUTS_DRVMTRX_LOAD_MATRIX        then trigger this -- all elements ramp in TOGETHER
> Y1:RDS-OUTS_DRVMTRX_{r}_{c}            readback of what is actually applied
> Y1:RDS-OUTS_DRVMTRX_RAMPING_{r}_{c}    1 while ramping
> Y1:RDS-OUTS_DRVMTRX_TRAMP              ramp time, seconds
> ```
>
> **Writing `_{r}_{c}` directly does nothing** — measured. Values only take
> effect via `SETTING_*` + `LOAD_MATRIX`, which is better than per-element
> writes: the phasing never passes through an inconsistent intermediate state.
> `TRAMP` came up at 0 after the build; set it (2 s works) or changes are steps.

The original pre-change proposal (drafted 2026-09-08, written for the side-post era
and the AWG route) was removed 2026-11-01 as stale; it is in git history before that date.
