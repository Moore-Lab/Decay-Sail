import numpy as np
from numpy.fft import irfft, rfftfreq
import matplotlib.pyplot as plt
from cdsutils import awg
from time import sleep

# set parameters
fs = 2048 # CDS model sample rate.
T = 60 # loop length (s) - bin spacing = 1/T
f_lo, f_hi = 1e-5, 20 # frequency band (Hz)
ramp_time = 0.25 # time to ramp up/down (s)

chan1 = 'Y1:RDS-OUTS_V1_EXC'
chan2 = 'Y1:RDS-OUTS_V2_EXC'
chan3 = 'Y1:RDS-OUTS_V3_EXC'
chan4 = 'Y1:RDS-OUTS_V4_EXC'

# set DAC counts/ V for each channel
dac_v_rms = [0.5, 0.5, 0.5, 0.5] # V RMS

# set distinct seeds for each channel
seeds = [11, 13, 17, 19]

npts = int(round(fs * T))
freqs = rfftfreq(npts, d=1.0/fs)
mask  = (freqs >= f_lo) & (freqs <= f_hi)

bufs = []

for i in range(4):
    rng = np.random.default_rng(seeds[i]) # random number generator
    ph = rng.random(freqs.size) * 2 * np.pi
    spec = np.zeros(freqs.size, dtype=np.complex128)
    spec[mask] = np.exp(1j * ph[mask])

    buf = irfft(spec, n=npts)
    buf *= dac_v_rms[i] / np.sqrt(np.mean(buf**2))  # normalize to target RMS
    bufs.append(buf.astype(np.float32))


Loop = getattr(awg, "ArbitraryLoop", None) or getattr(awg, "Arbitraryloop", None)
if Loop is None:
    raise RuntimeError("cdsutils.awg has no ArbitraryLoop/Arbitraryloop")

l1 = Loop(chan1, bufs[0], rate=fs)
l2 = Loop(chan2, bufs[1], rate=fs)
l3 = Loop(chan3, bufs[2], rate=fs)
l4 = Loop(chan4, bufs[3], rate=fs)

l1.start(); l2.start(); l3.start(); l4.start()
print("Four independent noise injections are running. Press Ctrl+C to stop.")

try:
    while True:
        sleep(1.0)
except KeyboardInterrupt:
    print("\nStopping...")
    for L in (l1, l2, l3, l4):
        try: L.stop()
        except Exception: pass
    print("Stopped.")

