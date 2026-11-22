"""Controller variants for the Phase C sim (own copies; lab_utils untouched). All take the live choose_spin arguments plus
state (dict kept across calls), trail ([(t, th)] 0.1 s spaced, 30 s) and w_cap."""
import math
import numpy as np
import brake_offsets as B


def live(**vp):
    def f(hist, t, level, d, f_mean, f_t, tol, wpm, c_assumed, min_push, f_against, state=None, trail=None, w_cap=500.0):
        return B.choose_spin(hist, t, level, d, f_mean, f_t, tol, wpm, c_assumed, min_push, f_against=f_against)
    return f


def fast(wpm_pump=None, fr_min=0.05, w_turn=0.0, hold_s=1.0, **vp):
    """HANDOVER variant: stop braking as soon as rotation along -d has stopped (fitted w crosses zero, with the swing turning
    point; braking resumes only if the mean rate against d is still above fr_min AND the fitted w is against d at |w| > w_turn),
    without waiting for the 30 s mean. `wpm_pump`: optional separate push-speed gate while pumping (existing push map,
    chosen the same way) so large swings keep pumping. Safety: |w_p| gate when braking = w_push_max (never pushes above it),
    pump gate default = w_push_max too (the commutation limit at speed); w-cap and field-off-on-target are in the harness."""
    def f(hist, t, level, d, f_mean, f_t, tol, wpm, c_assumed, min_push, f_against, state=None, trail=None, w_cap=500.0):
        tt = np.array([h[0] for h in hist]) - t; yy = np.array([h[1] for h in hist])
        p2 = np.polyfit(tt, yy, 2)
        th_e, w_e, al = p2[2], p2[1], 2 * p2[0]
        h = c_assumed + B.INTAKE
        th_p = th_e + w_e * h + 0.5 * al * h * h; w_p = w_e + al * h
        want = 1 if f_mean < f_t * (1 - tol / 2) else (-1 if f_mean > f_t * (1 + tol / 2) else 0)
        # reversal flag: armed when the 30 s mean rate against d exceeds 0.05 Hz (as live); disarmed for good as soon as the fitted w
        # has been against d (< -30 deg/s) and then turns to along d (> w_turn): rotation has stopped, no waiting on the 30 s mean
        st = state
        flag = f_against > 0.05                              # the live reverse flag (30 s mean against d)
        if not flag:
            st['seen_against'] = False; st['off'] = False    # mean has caught up: back to the live rule
        else:
            if d * w_e < -30.0:
                st['seen_against'] = True
            elif st.get('seen_against') and d * w_e > w_turn:
                st['off'] = True                              # rotation along -d has stopped: stop braking now, pump from the swing
        if flag and not st.get('off'):
            want = -1
        gate = wpm if (want < 0 or wpm_pump is None or f_mean > 0.1) else wpm_pump      # larger gate only before the rotor is turning along d
        out = [0.0, 0.0, 0.0]; bq = None
        if want != 0 and abs(w_p) < gate:
            if want > 0 and w_p * d > 0:
                vals = [d * B.push(q, th_p) for q in range(3)]
            elif want < 0:
                vals = [-math.copysign(1.0, w_p) * B.push(q, th_p) for q in range(3)]
            else:
                vals = None
            if vals is not None:
                bq = int(np.argmax(vals))
                if vals[bq] > min_push:
                    out[bq] = level
                else:
                    bq = None
        return tuple(out), dict(q=-1 if bq is None else bq, want=want)
    return f


REG = dict(live=live, fast=fast)


def get(name, vp):
    return REG[name](**vp)
