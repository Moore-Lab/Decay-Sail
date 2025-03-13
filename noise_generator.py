import time
import random
import numpy as np
import pyvisa
from functiongenerator import AFG2225 

def apply_narrow_chirp_with_noise(device, channel=1, start_freq=20, end_freq=30, sweep_duration=120,
                                  amplitude=10.0, noise_interval=2.0, phase_noise_range=(-90, 90), continuous=False):
    """
    Applies a narrowband frequency chirp with phase noise.

    :param device: Instance of AFG2225 function generator
    :param channel: Channel to modify (1 or 2)
    :param start_freq: Starting frequency of chirp (Hz)
    :param end_freq: Ending frequency of chirp (Hz)
    :param sweep_duration: Time to complete one frequency sweep (seconds)
    :param amplitude: Amplitude of the drive signal (Vpp)
    :param noise_interval: Time interval (seconds) between random phase shifts
    :param phase_noise_range: Tuple (min_phase, max_phase) defining random phase noise range
    :param continuous: If True, runs indefinitely until interrupted
    """
    # rm = pyvisa.ResourceManager()
    # inst = rm.list_resources()
    
    try:
        device.set_wave(channel, wavetype="SIN", frequency=start_freq, amplitude=amplitude, phase=0)

        while True:
            start_time = time.time()
            print(f"Starting narrow chirp from {start_freq} Hz to {end_freq} Hz over {sweep_duration} sec.")

            last_noise_time = start_time

            while time.time() - start_time < sweep_duration:
                elapsed_time = time.time() - start_time

                # Linearly interpolate frequency within the chirp range
                current_freq = start_freq + (elapsed_time / sweep_duration) * (end_freq - start_freq)

                # Apply the current frequency
                device.set_frequency(channel, current_freq)

                # Apply random phase noise at irregular intervals (between 1.5 to 3 sec)
                if time.time() - last_noise_time > random.uniform(1.5, 3.0):
                    random_phase = random.uniform(*phase_noise_range)
                    device.set_phase(channel, random_phase)
                    print(f"Frequency: {current_freq:.2f} Hz | Phase shift: {random_phase:.2f}°")
                    last_noise_time = time.time()

                time.sleep(0.5)  # Update frequency smoothly to allow response

            if not continuous:
                break  # Exit after one chirp if not running continuously

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    finally:
        print("Restoring phase to 0° and stopping function generator.")
        device.set_phase(channel, 0)

# Main Execution
if __name__ == "__main__":
    afg = AFG2225(device_id=0)  # Update device ID if needed

    apply_narrow_chirp_with_noise(
        device=afg,
        channel=1,
        start_freq=20,        # Sweep starts at 20 Hz
        end_freq=30,          # Ends at 30 Hz
        sweep_duration=120,   # Completes sweep in 120 sec (2 min)
        amplitude=5.0,        # Set amplitude to 5 Vpp
        noise_interval=2.0,   # Change phase noise every ~1.5-3 sec
        phase_noise_range=(-90, 90),  # Random phase shifts within this range
        continuous=True       # Set to True for indefinite sweeping
    )

    afg.close()  # Close connection after execution