"""
Monte Carlo simulation of the momentum transferred per Pb-212 decay
to a sail with the Pb-212 implanted on a Kapton tape laminated to a
stainless-steel backing.

Geometry (+z = into the sail):
    z = 0                : top surface (vacuum side; Po-216+ landed here)
    z in [0, t_K]        : Kapton tape, Pb-212 implanted within ~60 nm of the top
    z in [t_K, t_K+t_SS] : stainless steel sail
    z > t_K+t_SS         : vacuum below

For each Pb-212 -> Bi-212 -> {Po-212, Tl-208} -> Pb-208 chain we get
exactly one alpha + heavy daughter, going in opposite directions from
the implantation depth. Straight-line trajectories (no lateral scattering).

Momentum conservation:  p_foil = -(p_alpha_exit + p_daughter_exit)
                         with p_*_exit = 0 if the particle stops in the foil.

Run:    python sail_momentum_mc.py

Produces three plots in the same folder:
  - per_decay_distributions.png : histograms of p_z and |p| per decay
  - ss_thickness_sweep.png       : <p_z> and alpha-stopping vs SS thickness
  - depth_distribution.png       : sampled implantation depth distribution
"""

import os
import numpy as np
import matplotlib.pyplot as plt


# -- Physical constants ----------------------------------------------
MEV_C_KGMS  = 5.344e-22         # 1 MeV/c in SI (kg m / s)
M_ALPHA_MeV = 3727.379          # 4He nucleus rest energy


def alpha_p_MeVc(E_MeV):
    """Alpha kinetic momentum in MeV/c for non-rel kinetic energy."""
    return np.sqrt(2 * M_ALPHA_MeV * E_MeV)


# -- Decay branches (per Pb-212 chain) -------------------------------
# Prob, E_alpha [MeV], daughter
BRANCHES = [
    (0.6406, 8.78, "Pb-208"),       # Po-212 alpha
    (0.3594, 6.05, "Tl-208"),       # Bi-212 alpha
]


# -- Default geometry (m) -------------------------------------------
T_KAPTON_DEFAULT = 25.4e-6       # 1 mil
T_SS_DEFAULT     = 25.4e-6       # 1 mil


# -- Range-energy fits ----------------------------------------------
# R(E) = a * E^1.7. Calibrated to NIST ASTAR-like values at 8.78 MeV
# alpha: ~73 µm in Kapton (rho ~1.42 g/cm³), ~22 µm in stainless.
ALPHA_RANGE_COEFF = {"Kapton": 1.55e-6, "SS": 0.687e-6}
ALPHA_RANGE_EXP   = 1.7


def alpha_range(E_MeV, material):
    return ALPHA_RANGE_COEFF[material] * E_MeV ** ALPHA_RANGE_EXP


def alpha_E_from_range(R_m, material):
    return (R_m / ALPHA_RANGE_COEFF[material]) ** (1 / ALPHA_RANGE_EXP)


# Heavy-daughter ranges (m). Replace with SRIM output for precision.
DAUGHTER_R = {
    "Pb-208": {"Kapton": 90e-9, "SS": 28e-9},   # 169 keV recoil
    "Tl-208": {"Kapton": 70e-9, "SS": 22e-9},   # 116 keV recoil
}


# -- Implantation depth distribution (from Fig 7 of supp mat) -------
def sample_depths(N, rng=None):
    """Triangular distribution from 0 to 60 nm, peak at 30 nm."""
    rng = rng or np.random.default_rng()
    return rng.triangular(0, 30e-9, 60e-9, size=N)


# -- Exit-momentum calculations -------------------------------------
def alpha_exit_p(d, cos_t, sx, sy, E_MeV, t_K, t_SS):
    """Exit momentum vector (kg m/s) for one alpha. cos_t > 0 -> goes down."""
    if cos_t < 0:                                # UP toward top of Kapton
        path = d / abs(cos_t)
        R_K = alpha_range(E_MeV, "Kapton")
        if path >= R_K:
            return (0.0, 0.0, 0.0)
        E_exit = alpha_E_from_range(R_K - path, "Kapton")
        p = alpha_p_MeVc(E_exit) * MEV_C_KGMS
        return (p * sx, p * sy, p * cos_t)

    # DOWN: traverse Kapton, then SS
    path_K = (t_K - d) / cos_t
    R_K = alpha_range(E_MeV, "Kapton")
    if path_K >= R_K:
        return (0.0, 0.0, 0.0)
    E_at_iface = alpha_E_from_range(R_K - path_K, "Kapton")

    R_SS_at = alpha_range(E_at_iface, "SS")
    path_SS = t_SS / cos_t
    if path_SS >= R_SS_at:
        return (0.0, 0.0, 0.0)
    E_exit = alpha_E_from_range(R_SS_at - path_SS, "SS")
    p = alpha_p_MeVc(E_exit) * MEV_C_KGMS
    return (p * sx, p * sy, p * cos_t)


def daughter_exit_p(d, cos_t_a, sx, sy, p_init_kgms, daughter, t_K, t_SS):
    """Daughter exit momentum vector. Daughter direction is -alpha direction."""
    cos_t_d = -cos_t_a
    sx_d, sy_d = -sx, -sy
    R_K = DAUGHTER_R[daughter]["Kapton"]
    R_SS = DAUGHTER_R[daughter]["SS"]

    if cos_t_d < 0:                              # daughter going UP
        path = d / abs(cos_t_d)
        if path >= R_K:
            return (0.0, 0.0, 0.0)
        # heavy-ion: p ~ sqrt(E), E ~ R -> p_exit/p = sqrt(1 - path/R)
        p = p_init_kgms * np.sqrt(1 - path / R_K)
        return (p * sx_d, p * sy_d, p * cos_t_d)

    # daughter DOWN -- essentially always stops in Kapton (R << t_K)
    path_K = (t_K - d) / cos_t_d
    if path_K >= R_K:
        return (0.0, 0.0, 0.0)
    p_at_iface = p_init_kgms * np.sqrt(1 - path_K / R_K)
    R_SS_at = R_SS * (1 - path_K / R_K)
    path_SS = t_SS / cos_t_d
    if path_SS >= R_SS_at:
        return (0.0, 0.0, 0.0)
    p = p_at_iface * np.sqrt(1 - path_SS / R_SS_at)
    return (p * sx_d, p * sy_d, p * cos_t_d)


# -- Monte Carlo driver ---------------------------------------------
def simulate(N=300_000, t_K=T_KAPTON_DEFAULT, t_SS=T_SS_DEFAULT, rng=None):
    """Returns (p_foil_x, p_foil_y, p_foil_z) in kg m/s, length N."""
    rng = rng or np.random.default_rng()

    r = rng.random(N)
    pick_po = r < BRANCHES[0][0]
    E_alpha    = np.where(pick_po, BRANCHES[0][1], BRANCHES[1][1])
    daughter_n = np.where(pick_po, BRANCHES[0][2], BRANCHES[1][2])
    depths     = sample_depths(N, rng)
    cos_t      = rng.uniform(-1, 1, size=N)
    sin_t      = np.sqrt(1 - cos_t**2)
    phi        = rng.uniform(0, 2 * np.pi, size=N)
    sx, sy     = sin_t * np.cos(phi), sin_t * np.sin(phi)

    px = np.empty(N); py = np.empty(N); pz = np.empty(N)
    for i in range(N):
        E = E_alpha[i]
        p_a = alpha_exit_p(depths[i], cos_t[i], sx[i], sy[i], E, t_K, t_SS)
        p_init = alpha_p_MeVc(E) * MEV_C_KGMS
        p_d = daughter_exit_p(depths[i], cos_t[i], sx[i], sy[i],
                              p_init, str(daughter_n[i]), t_K, t_SS)
        px[i] = -(p_a[0] + p_d[0])
        py[i] = -(p_a[1] + p_d[1])
        pz[i] = -(p_a[2] + p_d[2])
    return px, py, pz


def alpha_through_fraction(N=200_000, t_K=T_KAPTON_DEFAULT,
                           t_SS=T_SS_DEFAULT, rng=None):
    """Fraction of all decays whose alpha punches through the bottom of the stack."""
    rng = rng or np.random.default_rng()
    r = rng.random(N)
    pick_po = r < BRANCHES[0][0]
    E_alpha = np.where(pick_po, BRANCHES[0][1], BRANCHES[1][1])
    depths = sample_depths(N, rng)
    cos_t  = rng.uniform(-1, 1, size=N)
    sin_t  = np.sqrt(1 - cos_t**2)
    phi    = rng.uniform(0, 2*np.pi, size=N)
    sx, sy = sin_t * np.cos(phi), sin_t * np.sin(phi)

    out = 0
    for i in range(N):
        if cos_t[i] <= 0:
            continue                             # alphas going UP can't leak
        p = alpha_exit_p(depths[i], cos_t[i], sx[i], sy[i],
                         E_alpha[i], t_K, t_SS)
        if any(p):
            out += 1
    return out / N


# -- Plot helpers ---------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))


def plot_depth_distribution():
    d = sample_depths(200_000) * 1e9              # nm
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(d, bins=80, color="tab:blue", alpha=0.7)
    ax.set_xlabel("Pb-212 implantation depth (nm)")
    ax.set_ylabel("counts")
    ax.set_title("Pb-212 implantation depth distribution\n"
                 "(triangular fit to supp Fig 7; peak 30 nm, max 60 nm)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "depth_distribution.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def plot_per_decay_distributions(px, py, pz):
    px_MeV = px / MEV_C_KGMS
    py_MeV = py / MEV_C_KGMS
    pz_MeV = pz / MEV_C_KGMS
    pmag   = np.sqrt(px_MeV**2 + py_MeV**2 + pz_MeV**2)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax = axes[0]
    ax.hist(pz_MeV, bins=80, color="tab:blue", alpha=0.7)
    ax.axvline(pz_MeV.mean(), color="k", ls="--",
               label=f"<p_z> = {pz_MeV.mean():.1f} MeV/c")
    ax.set_xlabel("p_foil,z (MeV/c) per decay\n(+ = into sail)")
    ax.set_ylabel("counts")
    ax.set_title("Per-decay signed z-momentum")
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.hist(pmag, bins=80, color="tab:orange", alpha=0.7)
    ax.axvline(pmag.mean(), color="k", ls="--",
               label=f"<|p|> = {pmag.mean():.1f} MeV/c")
    ax.set_xlabel("|p_foil| (MeV/c) per decay")
    ax.set_ylabel("counts")
    ax.set_title("Per-decay foil momentum magnitude")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.suptitle(
        f"Pb-212 decay momentum -> sail  "
        f"(Kapton {T_KAPTON_DEFAULT*1e6:.0f} µm + SS {T_SS_DEFAULT*1e6:.0f} µm)"
    )
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "per_decay_distributions.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def plot_ss_thickness_sweep():
    """How much SS do we need? Sweep t_SS, plot <p_z> and alpha leakage."""
    t_SS_um = np.array([5, 10, 15, 20, 25, 30, 50, 75, 100])
    avg_pz_MeV = []
    leak_frac  = []
    print(f"\nSS-thickness sweep (Kapton {T_KAPTON_DEFAULT*1e6:.1f} um):")
    print(f"  {'t_SS (um)':>10}  {'<p_z> (MeV/c)':>15}  "
          f"{'alpha leak %':>14}")
    for t_um in t_SS_um:
        t_SS = t_um * 1e-6
        _, _, pz = simulate(N=80_000, t_SS=t_SS)
        pz_MeV = pz.mean() / MEV_C_KGMS
        leak = alpha_through_fraction(N=80_000, t_SS=t_SS) * 100
        avg_pz_MeV.append(pz_MeV)
        leak_frac.append(leak)
        print(f"  {t_um:10.1f}  {pz_MeV:15.2f}  {leak:14.2f}")

    fig, ax1 = plt.subplots(figsize=(8, 5))
    color1 = "tab:blue"
    ax1.plot(t_SS_um, avg_pz_MeV, "o-", color=color1, lw=2,
             label=r"$\langle p_z\rangle$ per decay")
    ax1.set_xlabel("Stainless-steel thickness (um)")
    ax1.set_ylabel(r"$\langle p_z\rangle$ per decay (MeV/c)",
                   color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(alpha=0.3)
    ax1.axvline(25.4, color="gray", ls=":", label="1 mil SS")

    ax2 = ax1.twinx()
    color2 = "tab:red"
    ax2.plot(t_SS_um, leak_frac, "s--", color=color2, lw=2,
             label="alpha leakage out the bottom")
    ax2.set_ylabel("alpha leakage out the bottom (%)", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(bottom=-1)

    ax1.set_title("SS backing thickness sensitivity\n"
                  f"(Kapton {T_KAPTON_DEFAULT*1e6:.0f} um fixed)")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "ss_thickness_sweep.png"),
                dpi=160, bbox_inches="tight")
    plt.close()


def main():
    print(f"Geometry: Kapton {T_KAPTON_DEFAULT*1e6:.1f} um "
          f"+ stainless {T_SS_DEFAULT*1e6:.1f} um")
    print(f"Branches: {BRANCHES}")
    print()

    px, py, pz = simulate(N=300_000)
    px_MeV = px / MEV_C_KGMS
    py_MeV = py / MEV_C_KGMS
    pz_MeV = pz / MEV_C_KGMS
    print(f"<p_x>  = {px_MeV.mean():+8.2f} MeV/c  (~0 by symmetry)")
    print(f"<p_y>  = {py_MeV.mean():+8.2f} MeV/c")
    print(f"<p_z>  = {pz_MeV.mean():+8.2f} MeV/c  per decay")
    print(f"std(p_z) = {pz_MeV.std():8.2f} MeV/c")
    print()
    pz_SI = pz.mean()
    print(f"Force per Bq:  F = {pz_SI:.3e} N/Bq")
    for A in (1e3, 1e6, 1e9):
        print(f"   {A:.0e} Bq  ->  F = {pz_SI * A:.3e} N")
    print()

    plot_depth_distribution()
    plot_per_decay_distributions(px, py, pz)
    plot_ss_thickness_sweep()
    print("Saved depth_distribution.png, per_decay_distributions.png, "
          "ss_thickness_sweep.png")


if __name__ == "__main__":
    main()
