# DAQ chain feeding the HV amp: public LIGO schematics

The lab's DAQ is a LIGO **cymac**, a single-crate build of the Advanced LIGO CDS
real-time system (`advligorts`, git.ligo.org/cds/software/advligorts; overview
arXiv:2005.00219). So the analog chain between the DAC and the HV amp is documented on
the public LIGO DCC. Compiled 2026-09-21; links worked then.

- **[LIGO-D070081](https://dcc.ligo.org/LIGO-D070081/public)**: aLIGO AA/AI filter board,
  8 channels, 3rd-order 10 kHz low-pass with a 65536 Hz notch; THS4131 fully differential
  driver + AD8622 buffers. Differential in and out, 4 channels per DB9 (pins 1/6, 2/7,
  3/8, 4/9). Flat far above any stator drive frequency.
- **[LIGO-D070101](https://dcc.ligo.org/LIGO-D070101/public)**: 16-bit DAC AI rear
  interface board. **Relays in the output path** (Omron G6K-2F-Y, rev v4, watchdog),
  with a `DAC WD MON` readback and a local WD-override jumper. Drawing note: "WD readback
  not implemented on 16b DAC adapter D0902496-v1", so a channel can read fine in EPICS
  while its relay is open. Check this if an electrode looks dead with sane readbacks.
- **[LIGO-T1000523](https://dcc.ligo.org/LIGO-T1000523-v3/public)**: I/O chassis and
  DAC/ADC card layout (context).
- DAC card: General Standards 16AO16-16-F0-DF, differential, ±10 V, one 68-pin connector.

**Open (2026-09-21, unresolved):** the LIGO chain is differential end to end, but the HV
amp inputs (`VIN1–4`) are four single-ended BNCs on a board with one ground net. Nothing
public shows how the differential pair becomes single-ended; if the N leg is simply
grounded, the amplitude halves and one driver output is loaded. If electrode
troubleshooting resumes, trace the cable or breakout between the DAQ chassis and the amp
BNCs. (`aaronmarkowitz/labutils` is software only; no wiring docs there.)
