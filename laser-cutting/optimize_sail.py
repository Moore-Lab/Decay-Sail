"""
Optimize sail wing size for maximum angular acceleration of the
disk + sail assembly.

Figure of merit:
    alpha = tau / I_total
    tau   = 2 * F * r_c        (pinwheel; F per wing fixed by the
                                activity, NOT by wing area)
    r_c   = bar_width/2 + s/2   (wing center from spin axis)
    I_total = I_disk_cut + I_sail(s, t, rho)

Sweeps wing side s for various foil thicknesses and materials so
we can pick a thicker / stiffer / insulating foil that still gives
acceptable angular acceleration.

Edit the constants at the top to refit a different disk geometry,
sail geometry, or material list.
"""

import numpy as np
import matplotlib.pyplot as plt


# ── Disk parameters (slotted_disk_3p5, cut & sanded) ──────────────
DISK = dict(
    OD          = 3.50e-3,   # m
    hole_R      = 0.55e-3,
    thickness   = 0.50e-3,
    N_slots     = 16,
    slot_in     = 0.877e-3,
    slot_out    = 1.750e-3,
    slot_w_top  = 0.20e-3,   # kerf width at laser entry (top)
    slot_w_bot  = 0.05e-3,   # kerf width at exit (bottom)
    rho         = 2200,      # kg/m^3 (graphite)
)


# ── Sail mechanical geometry (everything except wing size s) ──────
SAIL = dict(
    tab_inside  = 1.75e-3,    # = 2 * disk slot inner radius
    tab_w       = 0.75e-3,
    tab_d       = 0.40e-3,
    strut_h     = 0.50e-3,
)
SAIL["bar_w"]   = SAIL["tab_inside"] + 2 * SAIL["tab_w"]    # = 3.25 mm


# ── Material presets: (rho [kg/m^3], E [GPa], one-line note) ──────
MATERIALS = {
    "Al":       (2700,  70,   "current; bends easily at 1.5 mil"),
    "Cu":       (8960,  110,  "conductive, heavy"),
    "SS304":    (8000,  195,  "stiff, heavy"),
    "Be":       (1850,  287,  "best stiff/mass but TOXIC dust"),
    "Mylar":    (1400,    4,  "insulator, very flexible"),
    "Kapton":   (1420,  2.5,  "insulator, flexible, common as foil"),
    "Si":       (2330,  160,  "insulator(ish), brittle"),
    "Glass":    (2230,   70,  "insulator, brittle"),
    "Sapphire": (3980,  350,  "insulator, very stiff, expensive"),
    "Mica":     (2880,  170,  "insulator, naturally layered foil"),
}


# ── Disk MoI & mass (slotted, kerf-correct, taper-correct) ────────
def disk_I_M():
    R, rh = DISK["OD"] / 2, DISK["hole_R"]
    rho, t = DISK["rho"], DISK["thickness"]
    rsi, rso = DISK["slot_in"], DISK["slot_out"]
    w_avg = (DISK["slot_w_top"] + DISK["slot_w_bot"]) / 2

    M_solid = rho * np.pi * R**2 * t
    I_solid = 0.5 * M_solid * R**2
    M_hole  = rho * np.pi * rh**2 * t
    I_hole  = 0.5 * M_hole * rh**2
    I_slot  = rho * t * w_avg * (rso**3 - rsi**3) / 3
    M_slot  = rho * t * w_avg * (rso - rsi)
    I = I_solid - I_hole - DISK["N_slots"] * I_slot
    M = M_solid - M_hole - DISK["N_slots"] * M_slot
    return I, M


# ── Sail MoI & mass about the disk spin axis ──────────────────────
def sail_I_M(s, t, rho):
    """
    s   = wing side length [m]
    t   = foil thickness   [m]
    rho = material density [kg/m^3]

    Returns (I_sail, M_sail, r_c) where r_c is the wing center radius.
    """
    a   = SAIL["bar_w"] / 2
    is2 = SAIL["tab_inside"] / 2
    tw, td = SAIL["tab_w"], SAIL["tab_d"]
    sh  = SAIL["strut_h"]

    # For each rectangle x in [x0, x1], y in [y0, y1]:
    #     int x^2 dA = (x1^3 - x0^3)/3 * (y1 - y0)
    # I_z (about spin axis) ≈ rho * t * int x^2 dA  (foil thin in y_disk)
    Ix  = 0.0
    A   = 0.0
    # Two wings, x in [a, a+s], y in [0, s] (and mirror x in [-(a+s), -a])
    Ix += 2 * ((a + s) ** 3 - a ** 3) / 3 * s
    A  += 2 * s * s
    # Bar, x in [-a, a], y in [0, strut_h]
    Ix += 2 * a ** 3 / 3 * sh
    A  += 2 * a * sh
    # Two tabs, x in [is2, is2+tw], y in [-tab_d, 0] (and mirror)
    Ix += 2 * ((is2 + tw) ** 3 - is2 ** 3) / 3 * td
    A  += 2 * tw * td

    return rho * t * Ix, rho * t * A, a + s / 2


def alpha_per_F(s, t, rho, I_disk):
    """alpha / F  (F = force per wing in N).  Pinwheel: tau = 2 F r_c."""
    I_sail, _, r_c = sail_I_M(s, t, rho)
    return 2 * r_c / (I_disk + I_sail)


def sweep(t, rho, I_disk, s_range=(0.3e-3, 4e-3), N=400):
    s = np.linspace(*s_range, N)
    a = np.array([alpha_per_F(si, t, rho, I_disk) for si in s])
    i = int(np.argmax(a))
    return s, a, s[i], a[i]


# ── Reporting ────────────────────────────────────────────────────
def main():
    I_disk, M_disk = disk_I_M()
    print(f"Disk:  I = {I_disk:.3e} kg.m^2,  M = {M_disk*1e6:.2f} mg\n")

    # Reference: current Al at 1.5 mil, s = 2 mm
    rho_Al = MATERIALS["Al"][0]
    t_ref  = 1.5 * 25.4e-6
    s_ref  = 2.0e-3
    I_ref, M_ref, _ = sail_I_M(s_ref, t_ref, rho_Al)
    a_ref = alpha_per_F(s_ref, t_ref, rho_Al, I_disk)
    print(f"Reference  Al 1.5 mil, 2x2 mm wings:")
    print(f"   I_sail = {I_ref:.3e} kg.m^2,  M_sail = {M_ref*1e6:.2f} mg")
    print(f"   alpha/F = {a_ref:.3e}   <-- ALL other values normalize to this")
    print()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # --- Plot 1: vary thickness for Al ----------------------------
    ax = axes[0]
    print("Al, thickness sweep:")
    print(f"  {'mil':>5} {'um':>6}    {'s_opt (mm)':>12}    "
          f"{'alpha/F':>12}   x ref")
    for mil in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        t = mil * 25.4e-6
        s, alphas, s_opt, a_opt = sweep(t, rho_Al, I_disk)
        ax.plot(s * 1e3, alphas, label=f"{mil:.1f} mil ({t*1e6:.1f} um)")
        ax.axvline(s_opt * 1e3, ls=":", alpha=0.3)
        print(f"  {mil:5.1f} {t*1e6:6.1f}    {s_opt*1e3:12.2f}    "
              f"{a_opt:12.3e}   {a_opt/a_ref:.2f}")
    print()
    ax.set_xlabel("wing side s (mm)")
    ax.set_ylabel(r"$\alpha / F$  (1 / (N$\cdot$s$^2$))")
    ax.set_title("Al at various thicknesses")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)

    # --- Plot 2: vary material at 1.5 mil -------------------------
    ax = axes[1]
    print("Materials at 1.5 mil:")
    print(f"  {'name':>9}  {'rho':>5}  {'E':>5}    {'s_opt (mm)':>12}    "
          f"{'alpha/F':>12}   x ref    notes")
    for name, (rho, E, note) in MATERIALS.items():
        s, alphas, s_opt, a_opt = sweep(t_ref, rho, I_disk)
        ax.plot(s * 1e3, alphas, label=name)
        # stiffness/mass FoM (cantilever deflection under self-weight
        # scales as rho/(E*t^2); inverse is a "rigidity" figure)
        rigidity = E * 1e9 * t_ref**2 / rho     # m^2 * Pa / (kg/m^3) -> m^4/s^2
        print(f"  {name:>9}  {rho:5d}  {E:5.1f}    {s_opt*1e3:12.2f}    "
              f"{a_opt:12.3e}   {a_opt/a_ref:.2f}    {note}")
    ax.set_xlabel("wing side s (mm)")
    ax.set_ylabel(r"$\alpha / F$  (1 / (N$\cdot$s$^2$))")
    ax.set_title(f"Materials @ {t_ref*1e6:.1f} um (1.5 mil)")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig("optimize_sail.png", dpi=160, bbox_inches="tight")
    plt.close()
    print("\nSaved optimize_sail.png")

    # --- Bonus: rigidity for picking a stiffer foil ---------------
    # Cantilever tip deflection of a wing (square plate b=L=s) under
    # its own weight:   delta = 3 rho g s^4 / (2 E t^2)
    # Reported below as "stiffness x ref" (ratio of rigidity E*t^2/rho
    # to Al at 1.5 mil baseline -- larger means less floppy at the
    # same s).  Self-weight bending is tiny for all of these (~nm at
    # s = 2 mm), so the real driver of bending is handling forces,
    # gas flow during cutting, etc.; this FoM still ranks the options
    # the same way.
    t_baseline = 1.5 * 25.4e-6
    rho_b, E_b, _ = MATERIALS["Al"]
    FoM_baseline = E_b * t_baseline**2 / rho_b   # arbitrary units, ratio-only
    print("\nRigidity vs Al-1.5-mil baseline (larger = less floppy at "
          "given wing size):")
    print(f"  {'material':>9}  {'1.0 mil':>10}  {'1.5 mil':>10}  "
          f"{'2.0 mil':>10}  {'3.0 mil':>10}  {'5.0 mil':>10}")
    for name, (rho, E, _) in MATERIALS.items():
        row = []
        for mil in (1.0, 1.5, 2.0, 3.0, 5.0):
            t = mil * 25.4e-6
            FoM = E * t**2 / rho
            row.append(f"{FoM / FoM_baseline:10.2f}")
        print(f"  {name:>9}  " + "  ".join(row))


if __name__ == "__main__":
    main()
