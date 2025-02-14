import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import time
from datetime import datetime
import random

from functiongenerator import AFG2225

'''
Development mode for setting electrode parameters with arb function generator
'''

# might want the ability to change parameters on fxn generator and scope as arguments in a fxn from a notebook

func = AFG2225('ASRL19::INSTR') ## first function generator
func2 = AFG2225('ASRL20::INSTR') ## second function generator


# set the electrode parameters
'''function generator (func or func2), 
    channel (1n[0] or 2[1]), 
    voltage amplitude (V), 
    signal frequency (Hz) - pulse or sweep
    pulse width (ns):
    ''' 

func.set_output_onoff(synth_channel, 0) ## turn off channel
func.set_wavetype(synth_channel, "PULS")  # may need to set to noise or sinusoid
func.set_pulse_width(synth_channel, pulse_width) 
func.set_frequency(synth_channel, signal_frequency)
func.set_amplitude(synth_channel, pulse_amplitude)
func.set_offset(synth_channel, amplitude_offset)
func.set_output_load(synth_channel, "HZ") ## make sure the channel is set for high impedance
func.set_output_onoff(synth_channel, 1) ## turn on channel