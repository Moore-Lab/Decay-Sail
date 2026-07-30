"""Planar under-rotor electrode drive: torque estimates.

Geometry: thin patterned electrode layer (flex PCB / metallized kapton) on top
of the magnet, rotor floating h_gap above it.  Two mechanisms:

  A. Variable-capacitance synchronous motor: rotor bottom-surface asymmetry
     (slots, wings) makes rotor-electrode capacitance angle-dependent;
     tau = (1/2) dC/dtheta V^2.  Deterministic, charge-independent.
  B. Induction (asynchronous) motor: lossy dielectric layer on rotor bottom;
     induced charge lags the traveling potential wave by the charge-relaxation
     time; peak tangential stress ~ (1/2) eps0 E^2 exp(-2kh) * 1/2 at
     omega_slip * tau_relax = 1.  Self-starting at any drive frequency.
"""

import numpy as np

eps0 = 8.854e-12
I_tot = 1.88e-11
m = 7.0e-6
g = 9.8

h_lev = 0.41e-3       # m, current levitation height above magnet face
t_pcb = 0.1e-3        # m, flex-PCB thickness eating into the gap
h = h_lev - t_pcb     # m, rotor-to-electrode gap
V0 = 100.0

A_disk = np.pi * (1.75e-3) ** 2
E_n = V0 / h          # normal field under a driven sector

print(f"gap h = {h*1e3:.2f} mm, E_normal ~ {E_n:.2e} V/m")

# ---- A. variable-capacitance torque ----
# angular modulation of C from the slot cutouts (slotted_disk_3p5 geometry,
# rough numbers: two slots ~2 x 0.3 mm) and/or sail wing footprint
A_asym = 1.2e-6        # m^2 total angle-dependent bottom area
dtheta = 0.5           # rad, angular scale over which it sweeps an electrode edge
dCdth = eps0 * A_asym / h / dtheta
tau_sync = 0.5 * dCdth * V0**2 * 0.5   # x0.5 for floating-rotor reduction
print(f"\nA. capacitance motor: dC/dtheta ~ {dCdth:.1e} F/rad, "
      f"tau ~ {tau_sync:.1e} N m at {V0:.0f} V")

om_lib = np.sqrt(2 * tau_sync / I_tot)
print(f"   capture bandwidth ~ {om_lib/2/np.pi:.2f} Hz")
print(f"   0 -> 10 Hz ramp at 50% margin: {2*np.pi*10/(0.5*tau_sync/I_tot):.1f} s")
print(f"   full-torque reversal from 10 Hz: {2*I_tot*2*np.pi*10/tau_sync:.1f} s")
gamma = 1 / 600.0
print(f"   max locked speed @ 10-min gas damping: "
      f"{tau_sync/(I_tot*gamma)/2/np.pi:.0f} Hz")

# ---- B. induction torque with lossy coating ----
k = np.pi / 2e-3       # /m, lateral wavenumber of sector pattern (~2 mm scale)
stress_peak = 0.5 * eps0 * E_n**2 * np.exp(-2 * k * h) * 0.5
tau_ind = stress_peak * A_disk * 1.2e-3     # lever arm ~ 1.2 mm
print(f"\nB. induction (matched loss): stress ~ {stress_peak:.2f} N/m^2, "
      f"tau ~ {tau_ind:.1e} N m")
for f_slip in [1, 10]:
    sig = eps0 * 2 * np.pi * f_slip
    print(f"   matched conductivity for {f_slip} Hz slip: sigma ~ {sig:.1e} S/m "
          f"(rho ~ {1/sig:.1e} ohm m)")

# ---- vertical-force safety ----
# quadrature drive: sum of V^2 over sectors is constant in time -> static pull
F_down = 0.5 * eps0 * E_n**2 * A_disk / 2   # ~half the disk over driven area
print(f"\nvertical pull at {V0:.0f} V: {F_down:.1e} N = "
      f"{F_down/(m*g)*100:.0f}% of rotor weight (mg = {m*g:.1e} N)")
V_half = V0 * np.sqrt(0.5 * m * g / F_down)
print(f"voltage where pull = 50% of weight: ~{V_half:.0f} V")
