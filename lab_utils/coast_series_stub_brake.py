#!/usr/bin/env python3
"""TEST STUB for coast_series.py --brake-script: writes NOTHING (no EPICS, no electrodes), only reports a stop line.
Used to test --laser-pattern live with the rotor at rest (2026-11-16): the only live writes are then the laser offset.
    python3 lab_utils/coast_series.py --pairs 2 --coast 20 --laser-pattern off,on --laser-settle 30 --live \
        --brake-script lab_utils/coast_series_stub_brake.py --outdir DIR
"""
print('stub brake_offsets: nothing written')
print('stop: on target (stub) (0.5000, 0.5000, 0.5000)')
