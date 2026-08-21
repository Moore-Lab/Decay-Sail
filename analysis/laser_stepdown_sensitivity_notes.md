# Laser step-down: power sensitivity

Rotor spins at steady state where laser torque balances drag. Nudge the
torque — a small laser power change ΔP, or equivalently a tiny force on the
sail — and the frequency relaxes toward a new steady state. Section 6 of the
settling notebook works out: watching for some time T after the nudge, what's
the smallest ΔP we'd actually see above the noise?

γ = 1/τ is fixed everywhere to τ = 67.65 min, the free-decay time measured
separately (laser off, pure decay) in:

> `spindown_20260702.ipynb`

That's a different measurement — it's what calibrates γ, which the sensitivity
numbers below all depend on.

**The model:**

I dΩ/dt = τ_laser(P) − IγΩ

so a power step ΔP relaxes the frequency toward a new steady state along the
same γ set by drag alone:

Δf(t) = Δf_ss (1 − e^(−γt)),  Δf_ss = κΔP / (2πIγ)

where κ is the torque calibration (N·m per unit power), I is the rotor's
moment of inertia, and γ = 1/τ the drag rate. At t = τ that's already
1 − e⁻¹ ≈ 63% developed; at 1 hour (just under τ) it's ~60%.

**Noise:**

σ_f(T) is measured, not assumed — from fit residuals on the three long
steady holds (the 1600/1300/1000-count steps). It's flat from 30 s out to
~20 min (8.7e-4 → 8.2e-4 Hz) and only drops to 5.9e-4 Hz by 1 hour, nowhere
near the ~11x a white-noise process would give averaging over that span. So
it's wander-limited: mostly slow drift (shows up as a rising ~1/f continuum
in the residual PSDs, plus a persistent ~10-min oscillation on the high-power
plateau), and it just doesn't average down by watching longer.

**5σ detection:**

Converting the frequency noise into a power threshold via κ_PD = 7.35e-16
N·m/PD count (the forward-model global fit) and 16.3 PD counts/mW (the
2026-07-20 power calibration), then into force via the sail wing radius
(2.625 mm, one wing): watch for 1 minute and the threshold is ~720 µW / 3.3
pN. Watch for 10 minutes and it's ~75 µW / 340 fN. Watch for an hour and it
tightens to ~12 µW / 56 fN.

(The acceleration channel — watching df/dt instead of Δf — responds faster
but is noisier; the frequency channel wins at every T checked here, so
that's the one quoted.)

An hour isn't arbitrary: it's close to τ, so the signal's basically done
developing, and because the noise is wander-limited it's basically done
averaging down too — past that you're not buying much on either side. The
real ceiling is how long the laser power and cell pressure actually hold
still, which is the whole point of the per-step noise characterization in:

> `laser_stepdown_stability.ipynb`

and the pressure-logging work.

Worth noting: at 1 hour the 12 µW threshold still sits ~250x above the
thermal (fluctuation-dissipation) floor — so there's a lot of
technical-noise headroom to chase before hitting anything fundamental.
