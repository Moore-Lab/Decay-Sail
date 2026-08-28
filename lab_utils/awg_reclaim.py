#!/usr/bin/env python3
"""Force-release leaked AWG slots on the stator electrodes.

RUN THIS AS ITS OWN PROCESS, then start a fresh drive. That two-step is what
actually recovered a stuck AWG on 2026-08-28; doing the same reclaim inside the
drive process, immediately before arming, appeared to make arming fail instead.

WHY SLOTS LEAK -- awg.py Excitation.stop():

    ret = awgbase.awgStopWaveform(self.slot, 0, 0)
    self.stopped = True
    if wait:
        self.clear()      # awgClearWaveforms -> awgRemoveChannel -> tpClearName

Only wait=True frees the slot. stop(wait=False) leaks it, and so does a process
that dies before reaching stop() at all -- which includes any drive launched
into the background, since the excitation dies with its client while the
_OFFSET pedestal persists in EPICS. Three electrodes per run against
MAX_NUM_AWG = 9 means about three runs before exhaustion.

awg.awg_cleanup() does NOT help: it only closes the client-side interfaces
(awgbase.awg_cleanup + testpoint_cleanup) and never touches the server's
per-channel slots.

READING THE OUTPUT -- this is the useful part:

  * DISTINCT slots (e.g. 13005 / 13006 / 13007 / 13008) = four real allocations
    are being held. They have now been freed, and a fresh drive should work.
  * The SAME slot for every channel = nothing was actually allocated. The
    failure is NOT slot exhaustion and reclaiming will not fix it. Look instead
    at DRVON, the module output switch (SW2 bit 1024), or another client
    (diaggui, awggui, a stale python) holding the EXC channels.
"""

import argparse
import sys

PREFIX = 'Y1:RDS-OUTS'


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--electrodes', default='1,2,3,4',
                   help='comma-separated V{n} to reclaim (default 1,2,3,4)')
    args = p.parse_args()

    import awgbase
    slots = {}
    for n in [int(s) for s in args.electrodes.split(',')]:
        chan = f'{PREFIX}_V{n}_EXC'
        try:
            awgbase.tpRequestName(chan, -1, None, None)
            slot = awgbase.awgSetChannel(chan)
            if slot >= 0:
                c = awgbase.awgClearWaveforms(slot)
                r = awgbase.awgRemoveChannel(slot)
                print(f'  V{n}  slot {slot}   clear={c} remove={r}')
                slots[n] = slot
            else:
                print(f'  V{n}  awgSetChannel returned {slot} (no slot)')
            awgbase.tpClearName(chan)
        except Exception as err:
            print(f'  V{n}  ERROR: {err}')

    vals = list(slots.values())
    print()
    if len(set(vals)) > 1:
        print('  Distinct slots -> real leaked allocations, now freed.')
        print('  Start a fresh drive; it should arm.')
    elif vals:
        print(f'  Every channel reported the same slot ({vals[0]}) -> nothing was')
        print('  actually allocated, so this was NOT slot exhaustion and this')
        print('  reclaim will not have fixed anything. Check DRVON, the output')
        print('  switch (SW2 bit 1024), and whether another client holds the')
        print('  EXC channels.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
