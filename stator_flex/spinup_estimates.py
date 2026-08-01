"""Order-of-magnitude estimates for electric spin-up of the levitated rotor.

Mechanisms considered for a uniform in-plane E field rotating at f_d
(4 posts driven sin/cos/-sin/-cos):

  1. Induced-dipole shape anisotropy (SS sail dominates): synchronous
     torque  tau = (1/2) * dalpha * E^2 * sin(2*delta), two stable lock
     angles per turn.  Scales as V^2, independent of rotor charge.
  2. Permanent charge dipole p = q*d (net charge q with centroid offset d
     from the rotation axis, or patch potentials): synchronous torque
     tau = p * E * sin(delta).  Scales as V^1, depends on charge state.
  3. Ohmic-lag "induction motor" torque on homogeneous graphite:
     tau ~ alpha * E^2 * omega_slip * eps0/sigma  -> utterly negligible
     (eps0/sigma ~ 1e-16 s).  Only a lossy interface (e.g. RC contact
     between SS sail and graphite through Kapton/adhesive) could give a
     usable asynchronous torque.

Both viable mechanisms are SYNCHRONOUS: time-averaged torque is zero
unless the rotor co-rotates with the field, so starting at fixed f_d
only works if f_d is inside the tiny capture (pull-in) bandwidth.
"""

import numpy as np

eps0 = 8.854e-12

# ---- rotor (SGD03 + pinwheel sail) ----
I_tot = 1.88e-11      # kg m^2, disk + sail (from momentum-simulation README)
m = 7.0e-6            # kg
r_disk = 1.75e-3      # m
h_lev = 0.41e-3       # m, levitation height above magnet plane

# ---- sail as conducting prolate spheroid (tip-to-tip wing span) ----
L_tip = 5.25e-3       # m, tip-to-tip span (2 * r_c = 2*2.625 mm)
w = 1.0e-3            # m, wing width (transverse scale)
a = L_tip / 2
b = w / 2
xi = a / b
La = (np.log(2 * xi) - 1) / xi**2          # depolarization, long axis
Lb = (1 - La) / 2
V_sph = 4 / 3 * np.pi * a * b * b
alpha_a = eps0 * V_sph / La                # conductor: alpha = eps0*V/L
alpha_b = eps0 * V_sph / Lb
dalpha = alpha_a - alpha_b

# ---- charge-dipole parameters (illustrative) ----
q = 2e-13             # C  (~1 V on ~0.2 pF plate, ~1e6 e)
d_off = 0.3e-3        # m, charge-centroid offset from spin axis

# ---- gas damping ----
gamma_10min = 1 / 600.0   # 1/s, damping rate used in thermal-noise note

print(f"sail polarizability: alpha_par={alpha_a:.2e}, alpha_perp={alpha_b:.2e},"
      f" dalpha={dalpha:.2e} F m^2")
print(f"charge dipole p = q*d = {q * d_off:.2e} C m  (q={q:.1e} C, d={d_off*1e3:.1f} mm)")
print()

hdr = (f"{'E (V/m)':>9} {'tau_ind (N m)':>14} {'tau_dip (N m)':>14} "
       f"{'f_capture':>10} {'t(0->1Hz)':>10} {'f_max@10min':>12} {'t_rev(1Hz)':>11}")
print(hdr)
print("-" * len(hdr))

for E in [100, 300, 1000, 3000, 1e4]:
    tau_ind = 0.5 * dalpha * E**2          # max synchronous torque, 2-theta
    tau_dip = q * d_off * E                # max synchronous torque, 1-theta
    tau = max(tau_ind, tau_dip)
    # libration ("pendulum") frequency in the lock well -> capture bandwidth
    #   2-theta well: omega_lib = sqrt(2*tau/I); use dominant mechanism
    om_lib = np.sqrt(2 * tau / I_tot)
    f_capture = om_lib / (2 * np.pi)
    # open-loop ramp at 50% torque margin
    alpha_dot = 0.5 * tau / I_tot
    t_1Hz = 2 * np.pi * 1.0 / alpha_dot
    # max locked speed against gas drag (also async terminal speed)
    om_max = tau / (I_tot * gamma_10min)
    # full-torque reversal from 1 Hz to -1 Hz
    t_rev = 2 * I_tot * 2 * np.pi / tau
    print(f"{E:9.0f} {tau_ind:14.2e} {tau_dip:14.2e} {f_capture:9.3f}Hz "
          f"{t_1Hz/60:8.1f}min {om_max/2/np.pi:10.2f}Hz {t_rev:9.1f}s")

print()
# ---- field scale at the rotor ----
# free-space rotating-field amplitude from two rod pairs at radius R_p,
# then screening by the grounded magnet plane at h << R_p
R_p = 12.7e-3        # m, assumed post radius from center
a_rod = 1.6e-3       # m, assumed rod radius
V0 = 100.0
E_free = 2 * V0 / (R_p * np.log(2 * R_p / a_rod))
for screen in [1.0, 2 * h_lev / R_p]:
    print(f"E at rotor, screen={screen:5.3f}: {E_free * screen:8.0f} V/m"
          f"  (E_free={E_free:.0f} V/m, posts at {R_p*1e3:.0f} mm)")

print()
# ---- closed-loop latency budget: keep commutation phase error < 20 deg ----
for f_spin in [0.1, 1, 5, 10]:
    t_lat = np.deg2rad(20) / (2 * np.pi * f_spin)
    print(f"f_spin={f_spin:5.1f} Hz: max control latency {t_lat*1e3:6.0f} ms")
