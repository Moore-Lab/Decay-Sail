# y1rds model change: Simulink edits for the commutation block (DRAFT for Molly)

Approved 2026-11-02 (`docs/DECISIONS.md`); Molly builds it. Design: `y1rds_model_change_commutation.md`.
- **C function:** `lab_utils/rcg/commutate.c`; tests: `lab_utils/rcg/test_commutate.py` (all pass on the Mac).
- **Read from:** `/opt/rtcds/userapps/mastqg/y1rds.mdl` (2026-09-08 version). An unchanged copy is on Dropbox
  `Microspheres/TFINER/data/models/y1rds.mdl`.
- **Where to edit:** MATLAB R2019a on worker2 (`/usr/local/MATLAB/R2019a/bin/matlab`). `MATLABPATH` in
  `~/.bashrc` already includes `mastqg` and the CDS libraries.

## What changes, and what doesn't

Only inside the subsystem **`OUTS`**:
- A new path computes SIN/COS from the camera angle.
- A new selector **`COMMSEL`** picks it or the existing oscillator `DRV`. Its default, 0, is the oscillator.
- Everything after that is untouched: DRVON's switches (`Choice`, `Choice1`), MUX → `DRVMTRX` → DEMUX,
  the sums with LES/MON, V1–V4 and their limits.
- After the restart, with all new channels at their default 0, **the drive behaves exactly as today**.

### Today (read from `y1rds.mdl`)

```
Ground ─► DRV (cdsOsc) ─ port 2 (SIN) ─► Choice  (in1) ─┐
                       └ port 3 (COS) ─► Choice1 (in1) ─┤      DRVON ─► Choice/Choice1 (in2, u2 >= 0.5)
                         Constant 0 ─► Choice/Choice1 (in3)  └─► Mux(2) ─► DRVMTRX ─► Demux(4) ─► Sum ─► V1..V4
```

### After

```
COMM_THETA ┐
COMM_OMEGA │
COMM_SEQ   │
COMM_M     │
COMM_SIGN  │
COMM_LEAD  ├─► COMM_MUX (12) ─► COMM (cdsFunctionCall) ─► COMM_DEMUX (4) ─ 1 SIN ─► SELS (in1)
COMM_LATENCY                                                              ├ 2 COS ─► SELC (in1)
COMM_ENABLE│                                                              ├ 3 PSI ─► COMM_PSI (cdsEpicsOutput)
COMM_WDOG  │                                                              └ 4 GAIN ► COMM_GAIN (cdsEpicsOutput)
COMM_VMIN  │
COMM_ALPHA │
COMM_AMP   ┘
DRV port 2 (SIN) ─► SELS (in3)      Ground ─► COMMSEL (cdsEpicsBinIn) ─► SELS (in2), SELC (in2)
DRV port 3 (COS) ─► SELC (in3)
SELS ─► Choice (in1)      SELC ─► Choice1 (in1)      (rest unchanged)
```

## Steps

1. **Put the C file where the build looks** (it is `#include`d by absolute path):
   `cp lab_utils/rcg/commutate.c /opt/rtcds/userapps/mastqg/src/commutate.c` (make `src/` if needed).
   `/opt/rtcds` on worker2 is cymac1's share, so the path is the same on cymac1.
2. **Open the model:** start MATLAB, run `open_system('y1rds')`, then double-click **`OUTS`**.
3. **Add the 12 inputs, in this order** (the order is the C function's `argin[0..11]`). From the CDS_PARTS
   library, **`cdsEpicsIn`**, named exactly:
   `COMM_THETA, COMM_OMEGA, COMM_SEQ, COMM_M, COMM_SIGN, COMM_LEAD, COMM_LATENCY, COMM_ENABLE, COMM_WDOG, COMM_VMIN, COMM_ALPHA, COMM_AMP`
   The channels become `Y1:RDS-OUTS_COMM_THETA` and so on.
4. **Mux:** a Simulink **Mux** named `COMM_MUX` with **Number of inputs = 12**. Wire the 12 inputs to its
   ports 1–12 in the order above.
5. **Function block:** a **`cdsFunctionCall`** named `COMM`. Right-click → Properties → **Description**:
   `inline COMMUTATE /opt/rtcds/userapps/mastqg/src/commutate.c`
   That is exactly three fields separated by spaces; FunctionCall.pm rejects anything else.
   Wire `COMM_MUX` → `COMM`.
6. **Demux:** a Simulink **Demux** named `COMM_DEMUX` with **Number of outputs = 4**. Wire `COMM` → `COMM_DEMUX`.
7. **Monitors:** two **`cdsEpicsOutput`** blocks, `COMM_PSI` (from Demux port 3) and `COMM_GAIN` (from Demux port 4).
8. **Selector:** a **`cdsEpicsBinIn`** named `COMMSEL`, its input from a new **Ground**, as DRVON is wired.
9. **Switches:** two Simulink **Switch** blocks, `SELS` and `SELC`. Set Criteria `u2 >= Threshold` and
   **Threshold 0.5**, the same as `Choice`.
   - `SELS`: in1 ← `COMM_DEMUX` port 1, in2 ← `COMMSEL`, in3 ← `DRV` port 2.
   - `SELC`: in1 ← `COMM_DEMUX` port 2, in2 ← `COMMSEL`, in3 ← `DRV` port 3.
10. **Re-wire:** delete the two lines `DRV` port 2 → `Choice` in1 and `DRV` port 3 → `Choice1` in1. Then connect
    `SELS` → `Choice` in1 and `SELC` → `Choice1` in1.
11. **Check before saving:** Ctrl+D (Update Diagram) should show no unconnected ports. Save.
12. **Build, install and restart on cymac1** as for the 2026-09-08 DRVMTRX change.
    - If the build reports *"C function has wrong number of inputs/outputs"*, the Mux size or the input order
      doesn't match the 12 inputs above.
    - If it reports *"needs three fields in Description"*, check step 5.

## Defaults and safety after the restart

| channel | default | meaning |
|---|---|---|
| `COMMSEL` | 0 | oscillator path, as today |
| `COMM_ENABLE` | 0 | commutation output gain ramps to 0 |
| `COMM_WDOG` | 0 | the C refuses to drive (trips) until a watchdog time is set |
| `COMM_AMP` | 0 | zero amplitude (the C clamps it to 0..6400 anyway) |

- To use the commutation path, worker2 sets the settings, starts sending THETA/OMEGA/ALPHA/SEQ, sets
  `COMMSEL` 1, then `COMM_ENABLE` 0 → 1 (the edge re-arms the watchdog). The pedestal and output switches
  are handled as by `feedback_drive.py` today.
- If worker2 stops updating `COMM_SEQ` for `COMM_WDOG` seconds, the output ramps to 0 in 0.5 s and stays off
  until `COMM_ENABLE` is toggled again.

## Not checked on the Mac

- **The build itself.** The C was compiled as a plain function with clang. The RCG `#include`s it inside the
  model's cycle code, which makes it a GCC nested function. GCC accepts that and clang does not, so only the
  cymac1 build checks it.
- **`sincos`.** It comes from the RCG's math header in the build (the oscillator parts use it); the Mac tests
  used libm.
- **Block port numbering in R2019a.** The port numbers above follow the saved `.mdl`.
