# -*- coding: utf-8 -*-
"""
NIDAQMonitor.py

part of the Hybrid Parameter Monitor by Juan Bohorquez
based on similar code from the CsPy interface written by Donald Booth

handles reading analog data from an NI-DAQmx interface


Created on Wed Jun 06 12:22:07 2018
"""
__author__ = 'Juan Bohorquez'

import ctypes
import numpy
import time
from Monitor import Monitor
import nidaqmx as daq
import nidaqmx.constants as daq_constants
from nidaqmx import stream_readers, error_codes, DaqError

class NIDAQmxPy(Monitor):

    # TODO : Set this up to work with a config file
    version = '2020.03.02'

    Acquisition_Type = daq_constants.AcquisitionType.FINITE
    Terminal_Config = daq_constants.TerminalConfiguration.RSE
    DeviceName = 'PXI1Slot6'
    samples_per_measurement = 1
    sample_rate = 500
    triggerSource = 'PFI0'
    triggerEdge = 'Rising'
    convert = False
    timeout = 1.0

    def __init__(self, channels, channel_names, conversion=None):

        Monitor.__init__(self, channels, channel_names)

        # Not sure what these two lines do ...
        self.task = None
        self.task_in_stream = None
        self.reader = None

        # Are we making a conversion from voltage to some other unit here?
        self.convert = isinstance(conversion, type({}))
        # print "NIDAQ self.convert  = {}".format(self.convert)
        # print "NIDAQ conversions = {}".format(conversion)
        # If so let's make sure the conversion dictionary is going to work
        err_type = "Error: Conversion should have lambda function at lowest level"
        if self.convert:
            err_shp = "Error: Conversion should have the same shape as channels"
            ch1 = self.channels.keys()
            ch2 = conversion.keys()
            assert set(ch1) == set(ch2), err_shp
            if self.many_channels:
                for key, value in self.channels.iteritems():
                    ch3 = value.keys()
                    assert isinstance(conversion[key], type({})), err_shp
                    ch4 = conversion[key].keys()
                    assert set(ch3) == set(ch4), err_shp
                for key, value in conversion.iteritems():
                    for func in value.values():
                        assert isinstance(func, type(lambda x: x + 1)), err_type
            else:
                for key, value in conversion.iteritems():
                    assert isinstance(value, type(lambda x: x + 1)), err_type

        self.conversion = conversion

        # List the analog in channels we will be monitoring on the DAQ
        if self.many_channels:  # For Issue
            self.channels_to_open = []
            print self.channels.values()
            for channel in self.channels.values():
                # make a list of all unique channels being opened
                self.channels_to_open = list(
                    set(self.channels_to_open) | set(channel.values()))
        else:
            self.channels_to_open = channels.values()

        self.channels_to_open.sort()
        print self.channels_to_open
        self.mychans = self.channel_string()

        # initialize data location
        self.data = numpy.zeros(len(self.channels_to_open))

        self.prepare_task()

    def channel_string(self):
        mychans = ""
        for i, chan in enumerate(self.channels_to_open):
            if i < len(self.channels_to_open) - 1:
                mychans += self.DeviceName + "/" + chan + ", "
            else:
                mychans += self.DeviceName + "/" + chan

        print "mychans : " + mychans
        return mychans

    def prepare_task(self, trig=True):

        try:
            if self.task is not None:
                self.close()
                # time.sleep(2) # Necessary??

            # Open the measurement task
            self.task = daq.Task("Monitor")

            # print "Task Handle: {}".format(self.task.name)

            add_ai_chan = self.task.ai_channels.add_ai_voltage_chan
            add_ai_chan(self.mychans,
                        terminal_config=self.Terminal_Config)

            set_timing = self.task.timing.cfg_samp_clk_timing
            set_timing(self.sample_rate,
                       sample_mode=self.Acquisition_Type)

            if trig:
                set_trig = self.task.triggers.start_trigger.cfg_dig_edge_start_trig
                set_trig("PFI0")

            self.task.start()

            self.task_in_stream = daq._task_modules.in_stream.InStream(self.task)
            self.reader = stream_readers.AnalogMultiChannelReader(self.task_in_stream)

            return
        except KeyboardInterrupt:
            self.close()
            # TODO : Proper traceback here
            raise KeyboardInterrupt

    def readout_auto(self):

        self.task.stop()
        self.task.triggers.start_trigger.disable_start_trig()
        dat = self.task.read()
        self.task.stop()
        self.task.triggers.start_trigger.cfg_dig_edge_start_trig("PFI0")
        return dat

    def measure(self, channel_name=None):
        try:
            # This reads out in triggered mode, as set above.
            try:
                # print self.data
                self.reader.read_one_sample(self.data,
                                            timeout=self.timeout)
            except DaqError as daq_err:
                daq_err_code = daq_err.error_code
                if daq_err_code == -200284:
                    print "Timeout waiting for trigger, reading out in auto mode"
                    time.sleep(1)
                    self.data = numpy.array(self.readout_auto())
                else:
                    raise daq_err

            # put all of the data in a dictionary mapping analog input channels to the corresponding voltages
            powers_usort = {}
            for i, chan in enumerate(self.channels_to_open):
                powers_usort.update({chan: self.data[i]})
            # print powers_usort

            if channel_name is not None:
                assert channel_name in self.channels.keys(), "channel_name is not a Monitor Channel"

            # place the (possibly) converted data, into a dictionary to be returned.
            powers = {}  # For the love of GNU choose better variable names!
            # print self.channels
            # if there are many_channels, check if a channel_name has been specified, if so return data from that
            # channel. Otherwise return all of the data in a large dictionary.
            if self.many_channels:
                if channel_name is None:
                    for chan in self.channels.keys():
                        powers[chan] = {}
                        for key, value in self.channels[chan]:
                            if self.convert:
                                func = self.conversion[chan][key]
                                powers[chan].update(
                                    {key: func(powers_usort[value])})
                            else:
                                powers[chan].update({key: powers_usort[value]})
                else:
                    # print self.channels[channel_name].keys()
                    for key in self.channels[channel_name].keys():
                        value = self.channels[channel_name][key]
                        if self.convert:
                            # print self.channels[channel_name]
                            # print channel_name
                            # print key, value
                            func = self.conversion[channel_name][key]
                            powers.update({key: func(powers_usort[value])})
                        else:
                            powers.update({key: powers_usort[value]})
            # if there is only one channel return the simple dictionary
            else:
                for key, value in self.channels.iteritems():
                    if self.convert:
                        func = self.conversion[key]
                        powers.update({key: func(powers_usort[value])})
                    else:
                        powers.update({key: powers_usort[value]})
            self.prepare_task()
            return powers
        except KeyboardInterrupt:
            self.close()
            raise KeyboardInterrupt

    def close(self):
        if self.task is None:
            return
        #print 'Closing DAQmx task'
        self.task.close()
        self.task = None
