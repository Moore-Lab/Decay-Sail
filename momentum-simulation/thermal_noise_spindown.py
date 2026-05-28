"""
Thermal-noise floor and spin-down-signal model for the Pb-212-driven
rotational measurement of the slotted graphite disk + Al sail.

Setup:
    - Rotor in equilibrium with its bath at T = 300 K
    - Rotational damping rate gamma = 1/(10 min)  ->  tau_damp = 10 min
    - Activity on the sail produces a constant torque whose magnitude
      decays exponentially with the Pb-212 half-life (10.64 hr)
    - With gamma >> lambda_Pb212 (10 min vs 10.6 hr -> ratio ~92),
      the rotor tracks the slowly-decaying source adiabatically:
              omega_ss(t) = alpha_signal(t) / gamma

We compute:
    (a) Thermal PSD of omega (one-sided)
    (b) RMS of omega averaged over a measurement window T_obs
    (c) The expected omega(t) curve for various initial activities
        over several Pb-212 half-lives, with the noise floor shown
    (d) Minimum detectable activity vs integration time (SNR = 1)
"""

import os
import numpy as np
import matplotlib.pyplot as plt


# -- Constants ------------------------------------------------------
KB         = 1.380649e-23                     # J/K
T_KELVIN   = 300.0                            # bath temperature

# Damping rate (assumed) -- this would come from a measurement of the
# rotor's free spin-down with no activity, in the vacuum and trap
# conditions being used.
GAMMA      = 1.0 / (10 * 60)                  # 1/s   (10-min damping time)

# Moment of inertia of disk + sail (from earlier calcs)
I_TOTAL    = 1.88e-11                         # kg m^2

# Per-decay momentum to the sail (from sail_momentum_mc.py result)
PZ_PER_DECAY = 5.08e-20                       # N per Bq  (per active face)

# Sail wing center radial position
R_C        = 2.625e-3                         # m

# Pb-212 decay constant
T_HALF_PB212 = 10.64 * 3600                   # s
LAMBDA_PB212 = np.log(2) / T_HALF_PB212

# Angular acceleration per Bq (per active face).  Pinwheel: 2 wings
# combine to give torque tau = 2 F r_c.  Activity here refers to the
# activity on EACH wing.
ALPHA_PER_BQ_PER_WING = 2 * PZ_PER_DECAY * R_C / I_TOTAL


# -- Thermal-noise expressions --------------------------------------
def thermal_psd_omega(f_Hz):
    """One-sided PSD of omega at frequency f (Hz).
    Damped rotator driven by FD theorem white torque noise:
        S_omega(f) = (4 k_B T gamma) / (I (gamma^2 + (2 pi f)^2))
    """
    return (4 * KB * T_KELVIN * GAMMA
            / (I_TOTAL * (GAMMA**2 + (2 * np.pi * f_Hz) ** 2)))


def sigma_omega_inst():
    """Instantaneous RMS of omega from equipartition: sqrt(k_B T / I)."""
    return np.sqrt(KB * T_KELVIN / I_TOTAL)


def sigma_omega_avg(T_obs_s):
    """RMS of omega averaged over a window of length T_obs (s).

    For an OU process with correlation time 1/gamma:
        Var(<omega>_T) = (2 sigma_inst^2 / (gamma T)^2)
                         * (gamma T - 1 + exp(-gamma T))
    Reduces to sigma_inst * sqrt(2 / gamma T_obs) for T_obs >> 1/gamma.
    """
    s2 = sigma_omega_inst() ** 2
    g, T = GAMMA, T_obs_s
    return np.sqrt(2 * s2 * (g * T - 1 + np.exp(-g * T)) / (g * T) ** 2)


# -- Signal model ---------------------------------------------------
def omega_signal(t_s, activity_per_wing_Bq):
    """Adiabatic steady-state omega(t) for activity A0 at t=0, valid
    since gamma >> lambda_Pb212."""
    alpha_0 = ALPHA_PER_BQ_PER_WING * activity_per_wing_Bq
    return (alpha_0 / GAMMA) * np.exp(-LAMBDA_PB212 * t_s)


# -- Plot helpers ---------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))


def plot_thermal_psd():
    f = np.logspace(-5, 2, 800)
    asd = np.sqrt(thermal_psd_omega(f))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(f, asd, lw=2)
    f_corner = GAMMA / (2 * np.pi)
    ax.axvline(f_corner, color="gray", ls="--",
               label=fr"$\gamma / (2\pi)$ = {f_corner:.2e} Hz")
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel(r"$\sqrt{S_\omega(f)}$  (rad/s / $\sqrt{\rm Hz}$)")
    ax.set_title(rf"Thermal noise on $\omega$  (T = {T_KELVIN:.0f} K, "
                 rf"$\tau_{{\rm damp}}$ = {1/GAMMA/60:.0f} min, "
                 rf"$I$ = {I_TOTAL:.2e} kg m$^2$)")
    ax.grid(which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "omega_psd.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def plot_spindown_signal():
    """omega vs time for various activities, with averaged-noise bands."""
    t_h = np.linspace(0, 80, 800)         # 80 hr ~ 7.5 half-lives
    t_s = t_h * 3600

    activities = [1e2, 1e3, 1e4, 1e5, 1e6]
    fig, ax = plt.subplots(figsize=(10, 6))

    for A in activities:
        w = omega_signal(t_s, A)
        ax.semilogy(t_h, w, lw=1.8, label=rf"{A:.0e} Bq/wing")

    # Noise bands for several integration windows
    T_obs_list_label = [
        (60,     "1 min"),
        (600,    "10 min"),
        (3600,   "1 hr"),
        (86400,  "1 day"),
    ]
    for T_obs, lab in T_obs_list_label:
        s = sigma_omega_avg(T_obs)
        ax.axhline(s, color="gray", ls="--", alpha=0.6, lw=0.9,
                   label=fr"$\sigma_\omega$ avg over {lab} = {s:.2e} rad/s")

    ax.set_xlabel("time since t = 0 (hr)")
    ax.set_ylabel(r"steady-state $\langle\omega\rangle$ (rad/s)")
    ax.set_title("Spin-down signal: $\\omega(t) = \\omega_0\\,e^{-\\lambda_{\\rm Pb212} t}$ "
                 "vs thermal noise floor")
    ax.grid(which="both", alpha=0.3)
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.set_ylim(1e-9, 1e-1)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "spindown_signal.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def plot_detectability():
    """Minimum activity to give SNR = 1 vs integration time."""
    T_obs = np.logspace(1, 6, 200)       # 10 s to ~12 days
    sigma = np.array([sigma_omega_avg(T) for T in T_obs])
    # Detection at SNR = 1: omega_signal(t=0, A) = sigma
    # alpha_0/gamma = sigma  ->  A = sigma * gamma / alpha_per_Bq
    A_min = sigma * GAMMA / ALPHA_PER_BQ_PER_WING

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(T_obs, A_min, lw=2)
    # Mark useful Bq levels
    for ref_Bq, label in [(200, "supp. ~200 Bq/mm²"),
                          (1e3, "1 kBq"),
                          (1e5, "100 kBq"),
                          (1e6, "1 MBq")]:
        ax.axhline(ref_Bq, color="gray", ls=":", alpha=0.5)
        ax.text(T_obs[-1]*0.7, ref_Bq*1.15, label,
                fontsize=8, color="gray")
    ax.set_xlabel("integration time $T_{\\rm obs}$ (s)")
    ax.set_ylabel("min detectable activity per wing (Bq)")
    ax.set_title("SNR = 1 detection threshold vs integration time\n"
                 "(at $t = 0$; threshold rises as activity decays)")
    ax.grid(which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "detectability.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def main():
    print(f"System parameters")
    print(f"  T                = {T_KELVIN} K")
    print(f"  gamma (damping)  = {GAMMA:.4e}/s   "
          f"({1/GAMMA:.1f} s = {1/GAMMA/60:.1f} min)")
    print(f"  I_total          = {I_TOTAL:.3e} kg m^2")
    print(f"  T_half(Pb-212)   = {T_HALF_PB212/3600:.2f} hr")
    print(f"  lambda(Pb-212)   = {LAMBDA_PB212:.4e}/s")
    print(f"  gamma/lambda     = {GAMMA/LAMBDA_PB212:.0f}   (adiabatic OK)")
    print(f"  alpha per Bq/wing = {ALPHA_PER_BQ_PER_WING:.3e} rad/s^2 per Bq")
    print()

    print("Thermal noise")
    print(f"  sigma_omega (instantaneous, equipartition) = "
          f"{sigma_omega_inst():.3e} rad/s")
    for T_obs, lab in [(60, "1 min"), (600, "10 min"),
                       (3600, "1 hr"), (86400, "1 day"),
                       (5*86400, "5 days")]:
        s = sigma_omega_avg(T_obs)
        A_min = s * GAMMA / ALPHA_PER_BQ_PER_WING
        print(f"  sigma_omega (avg over {lab:7s}) = {s:.3e} rad/s   "
              f"-> min A = {A_min:.2e} Bq/wing")
    print()

    print("Signal at t = 0 (steady-state omega vs activity)")
    for A in [200, 1e3, 1e4, 1e5, 1e6]:
        w0 = omega_signal(0.0, A)
        print(f"  A = {A:8.0f} Bq/wing  ->  omega_ss = {w0:.3e} rad/s  "
              f"= {w0/(2*np.pi)*60:.3e} rpm")
    print()

    plot_thermal_psd()
    plot_spindown_signal()
    plot_detectability()
    print("Saved omega_psd.png, spindown_signal.png, detectability.png")


if __name__ == "__main__":
    main()
