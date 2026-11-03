// commutate.c -- y1rds front-end commutation for the stator feedback drive (DRAFT, branch feedback-drive).
// RCG cdsFunctionCall, inline form. Block Description:
//   inline COMMUTATE /opt/rtcds/userapps/mastqg/src/commutate.c
// Called every model cycle (FE_RATE, 2048 Hz for y1rds). Inputs arrive through a MUX, outputs leave
// through a DEMUX, in the index order below. The RCG build counts argin[k]/argout[k] uses with literal
// indices (FunctionCall.pm), so every input and output index is used literally, exactly once in order.
//
// Inputs (MUX order; each from a cdsEpicsIn except where noted):
//   argin[0]  THETA    rotor angle at the last camera frame, image deg (unwrapped by worker2)
//   argin[1]  OMEGA    rotor angular velocity at that frame, deg/s (worker2's line fit)
//   argin[2]  SEQ      frame counter written by worker2 with each update (watchdog)
//   argin[3]  M        electrical/mechanical ratio (8)
//   argin[4]  SIGN     -1 or +1: image angle -> field angle
//   argin[5]  LEAD     electrical deg ahead along the motion
//   argin[6]  LATENCY  s: camera exposure -> this model sees THETA (prediction horizon offset)
//   argin[7]  ENABLE   1 = run; a 0 -> 1 edge also clears a latched watchdog trip
//   argin[8]  WDOG_S   s without a new SEQ before the output ramps to 0 and latches off
//   argin[9]  VMIN     deg/s hysteresis for the motion direction
//   argin[10] ALPHA    rotor angular acceleration at that frame, deg/s^2 (worker2's quadratic fit)
//   argin[11] AMP      drive amplitude, counts (clamped to 0..6400 here: amp + 6400 pedestal <= 12800)
// Outputs (DEMUX order):
//   argout[0] SIN      gain * AMP * sin(psi)  -> DRVMTRX input 1 (in place of the oscillator SIN)
//   argout[1] COS      gain * AMP * cos(psi)  -> DRVMTRX input 2 (in place of the oscillator COS)
//   argout[2] PSI      psi, electrical deg in [0, 360) (monitor)
//   argout[3] GAIN     0..1 output gain after enable/watchdog ramps (monitor)
// SIN/COS carry the amplitude like the oscillator's SINGAIN/COSGAIN do, so DRVMTRX and the V{n}
// modules are used unchanged (forward matrix, V{n}_LIMIT 12800, pedestal on V{n}_OFFSET).
// Law (same as lab_utils/feedback_drive.py Controller): psi = SIGN*M*theta_pred + dir*LEAD,
// theta_pred = THETA + OMEGA*tau + ALPHA*tau^2/2, tau = time since SEQ last changed + LATENCY;
// dir = sign of the predicted velocity OMEGA + ALPHA*tau, with hysteresis.
// No libm: sincos() is provided by the RCG build (inlineMath); the test harness supplies its own.
void COMMUTATE(double *argin, int nargin, double *argout, int nargout)
{
    static double t_now = 0.0;         // s since model start (cycle count / FE_RATE)
    static double t_upd = 0.0;         // time SEQ last changed
    static double seq_prev = -1.0e300;
    static double gain = 0.0;
    static double dir = 1.0;
    static double en_prev = 0.0;
    static int tripped = 0;
    double theta = argin[0];
    double omega = argin[1];
    double seq = argin[2];
    double m = argin[3];
    double sgn = argin[4];
    double lead = argin[5];
    double lat = argin[6];
    double enable = argin[7];
    double wdog = argin[8];
    double vmin = argin[9];
    double alpha = argin[10];
    double amp = argin[11];
    double dt, tau, w_p, th_p, psi, turns, s, c, target, step;

    t_now += 1.0 / (double) FE_RATE;
    if (seq != seq_prev) {
        seq_prev = seq;
        t_upd = t_now;
    }
    if (enable > 0.5 && en_prev <= 0.5) {
        tripped = 0;                   // re-arm on a fresh enable
        t_upd = t_now;
    }
    en_prev = enable;
    dt = t_now - t_upd;
    if (wdog > 0.0 && dt > wdog) {
        tripped = 1;
    }
    if (wdog > 0.0 && dt > wdog) {
        dt = wdog;                     // never extrapolate past the watchdog horizon
    }
    if (wdog <= 0.0) {
        tripped = 1;                   // no watchdog set: refuse to drive
    }
    tau = dt + lat;
    w_p = omega + alpha * tau;         // predicted velocity now
    if (w_p > vmin) {
        dir = 1.0;
    }
    if (w_p < -vmin) {
        dir = -1.0;
    }
    th_p = theta + omega * tau + 0.5 * alpha * tau * tau;
    psi = sgn * m * th_p + dir * lead;
    turns = psi / 360.0;
    turns = turns - (double) ((long) turns);
    if (turns < 0.0) {
        turns += 1.0;
    }
    psi = 360.0 * turns;
    // gain ramps (0.5 s full scale) towards 1 when enabled and not tripped, else towards 0
    target = (enable > 0.5 && tripped == 0) ? 1.0 : 0.0;
    step = 2.0 / (double) FE_RATE;
    if (gain < target) {
        gain += step;
        if (gain > target) gain = target;
    }
    if (gain > target) {
        gain -= step;
        if (gain < target) gain = target;
    }
    if (amp > 6400.0) amp = 6400.0;
    if (amp < 0.0) amp = 0.0;
    sincos(psi * 0.017453292519943295, &s, &c);
    argout[0] = gain * amp * s;
    argout[1] = gain * amp * c;
    argout[2] = psi;
    argout[3] = gain;
}
