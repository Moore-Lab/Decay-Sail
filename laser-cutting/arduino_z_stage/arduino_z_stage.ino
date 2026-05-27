// Z-stage stepper control for laser cutter
// Hardware: Arduino Uno + Adafruit Motor Shield v2.3 + Kysan 1124090 NEMA 17
// Lead screw: ~0.5 mm/rev (no absolute calibration needed)
//
// Serial commands (115200 baud, newline-terminated):
//   +N      step +N steps (e.g. "+50")        single steps, FORWARD
//   -N      step -N steps                      single steps, BACKWARD
//   Z<f>    move <f> mm (signed, e.g. "Z0.1", "Z-0.05")
//   R       release coils (deactivate holding torque)
//   S<n>    set RPM (e.g. "S30")
//   ?       print status
//
// All commands echo "OK <info>" or "ERR <reason>".

#include <Adafruit_MotorShield.h>

#define STEPS_PER_REV   200      // Kysan 1124090: 1.8°/step
#define LEADSCREW_MMREV 0.5      // approximate
#define DEFAULT_RPM     30
#define STEPPER_PORT    2        // M3/M4 on the shield (port 1 = M1/M2)

Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_StepperMotor *stepper = AFMS.getStepper(STEPS_PER_REV, STEPPER_PORT);

long total_steps = 0;   // running tally since reset (relative origin)
int current_rpm = DEFAULT_RPM;

void doSteps(long n) {
  if (n == 0) {
    Serial.println("OK 0");
    return;
  }
  if (n > 0) {
    stepper->step(n, FORWARD, SINGLE);
  } else {
    stepper->step(-n, BACKWARD, SINGLE);
  }
  total_steps += n;
  Serial.print("OK ");
  Serial.print(n);
  Serial.print(" steps, total=");
  Serial.println(total_steps);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }
  if (!AFMS.begin()) {
    Serial.println("ERR motor shield not found");
    while (1) delay(100);
  }
  stepper->setSpeed(current_rpm);
  Serial.println("READY z_stage v1");
  Serial.print("  steps/rev=");  Serial.println(STEPS_PER_REV);
  Serial.print("  mm/rev=");     Serial.println(LEADSCREW_MMREV);
  Serial.print("  rpm=");        Serial.println(current_rpm);
}

void loop() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  char c = cmd.charAt(0);

  if (c == '+' || c == '-' || isDigit(c)) {
    long n = cmd.toInt();
    doSteps(n);
  } else if (c == 'Z' || c == 'z') {
    float mm = cmd.substring(1).toFloat();
    long n = lround(mm * STEPS_PER_REV / LEADSCREW_MMREV);
    Serial.print("# ");  Serial.print(mm, 4);  Serial.print(" mm -> ");
    Serial.print(n);     Serial.println(" steps");
    doSteps(n);
  } else if (c == 'R' || c == 'r') {
    stepper->release();
    Serial.println("OK released");
  } else if (c == 'S' || c == 's') {
    int rpm = cmd.substring(1).toInt();
    if (rpm < 1 || rpm > 300) {
      Serial.println("ERR rpm out of range (1-300)");
      return;
    }
    current_rpm = rpm;
    stepper->setSpeed(current_rpm);
    Serial.print("OK rpm=");  Serial.println(current_rpm);
  } else if (c == '?') {
    Serial.print("STATUS total_steps=");  Serial.print(total_steps);
    Serial.print(" mm_approx=");
    Serial.print(total_steps * LEADSCREW_MMREV / STEPS_PER_REV, 4);
    Serial.print(" rpm=");  Serial.println(current_rpm);
  } else {
    Serial.print("ERR unknown command: ");  Serial.println(cmd);
  }
}
