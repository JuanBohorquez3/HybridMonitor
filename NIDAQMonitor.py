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
from Monitor import Monitor as Mon
import logging
logger = logging.getLogger(__name__)


class NIDAQmxAI(Mon):

    # TODO : Set this up to work with a config file
    version = '2018.11.02'

    allow_evaluation = True
    enable = False
    DAQmx_Val_RSE = 10083
    DAQmx_Val_NRSE = 10078
    DAQmx_Val_Diff = 10106
    DAQmx_Val_PseudoDiff = 12529
    DAQmx_Val_Volts = 10348
    DAQmx_Val_Rising = 10280
    DAQmx_Val_Falling = 10171
    DAQmx_Val_FiniteSamps = 10178
    DAQmx_Val_GroupByChannel = 0
    DAQmx_Val_GroupByScanNumber = 1
    DAQmx_Val_ChanPerLine = 0
    convert = False

    def __init__(self, channels, conversion=None):

        Mon.__init__(self, channels)
        self.DeviceName = "PXI2Slot6"
        self.samples_per_measurement = 10
        self.sample_rate = 1000
        self.triggerSource = '/PXI2Slot6/PFI0'
        self.triggerEdge = 'Rising'
        self.nidaq = ctypes.windll.nicaiu
        self.DAQmx_Val_Cfg_Default = ctypes.c_long(-1)
        self.taskHandle = ctypes.c_ulong(0)

        # Are we making a conversion from voltage to some other unit here?
        self.convert = isinstance(conversion, type({}))
        print "NIDAQ self.convert  = {}".format(self.convert)
        print "NIDAQ conversions = {}".format(conversion)
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
                        assert isinstance(func, type(lambda x: x+1)), err_type
            else:
                for key, value in conversion.iteritems():
                    assert isinstance(value, type(lambda x: x+1)), err_type

        self.conversion = conversion

        # List the analog in channels we will be monitoring on the DAQ
        if self.many_channels:
            self.channels_to_open = []
            print self.channels.values()
            for channel in self.channels.values():
                # make a list of all unique channels being opened
                self.channels_to_open = list(set(self.channels_to_open) | set(channel.values()))
        else:
            self.channels_to_open = channels.values()

        self.channels_to_open.sort()
        print self.channels_to_open
        self.mychans = self.channel_string()

        # initialize data location
        self.data = numpy.zeros((self.samples_per_measurement * len(self.channels_to_open),), dtype=numpy.float64)

        self.prepare_task()
        
    def channel_string(self):
        mychans = ""
        for i, chan in enumerate(self.channels_to_open):
            if i < len(self.channels_to_open) - 1:
                mychans += self.DeviceName+"/"+chan+", "
            else:
                mychans += self.DeviceName+"/"+chan
        
        print "mychans : " + mychans
        return mychans

    def CHK(self, err, func):
        if err < 0:
            buf_size = 1000
            buf = ctypes.create_string_buffer('\000'*buf_size)
            buf_v_size = 2000
            buf_v = ctypes.create_string_buffer('\000'*buf_v_size)
            self.nidaq.DAQmxGetErrorString(err, ctypes.byref(buf), buf_size)
            self.nidaq.DAQmxGetExtendedErrorInfo(ctypes.byref(buf_v), buf_v_size)
            print 'nidaq call %s failed with error %d: %s' % (func, err, repr(buf.value))
            print 'nidaq call %s failed with verbose error %d: %s' % (func, err, repr(buf_v.value))
            raise ValueError

    def prepare_task(self, trig=True):
        
        try:
            if self.taskHandle.value != 0:
                self.close()
                self.taskHandle = ctypes.c_ulong(0)
                time.sleep(2)

            # Open the measurement task
            self.CHK(self.nidaq.DAQmxCreateTask("", ctypes.byref(self.taskHandle)), "CreateTask")
            
            print "Task Handle: {}".format(self.taskHandle.value)

            # open the input voltage channels
            self.CHK(self.nidaq.DAQmxCreateAIVoltageChan(self.taskHandle,
                                                         ctypes.c_char_p(self.mychans),
                                                         "",
                                                         self.DAQmx_Val_RSE,
                                                         ctypes.c_double(-5.0),
                                                         ctypes.c_double(5.0),
                                                         self.DAQmx_Val_Volts,
                                                         None), "CreateAIVoltageChan")
            
            # configure the timing
            self.CHK(self.nidaq.DAQmxCfgSampClkTiming(self.taskHandle,
                                                      "",
                                                      ctypes.c_double(self.sample_rate),
                                                      self.DAQmx_Val_Rising,
                                                      self.DAQmx_Val_FiniteSamps,
                                                      ctypes.c_uint64(self.samples_per_measurement)),
                     "CfgSampClkTiming")
            
            if trig:
                self.CHK(self.nidaq.DAQmxCfgDigEdgeStartTrig(self.taskHandle,
                                                             ctypes.c_char_p(self.triggerSource),
                                                             ctypes.c_int32(self.DAQmx_Val_Rising)),
                         "CfgDigEdgeStartTrig_Rising")
                
            self.CHK(self.nidaq.DAQmxStartTask(self.taskHandle), "StartTask")
            
            return
        except KeyboardInterrupt:
            self.close()
            raise KeyboardInterrupt
    
    def measure(self, channel_name=None):
        try:
            read = ctypes.c_int32()
            print "reading out in triggered mode"
            self.nidaq.DAQmxReadAnalogF64(self.taskHandle,
                                          self.samples_per_measurement,
                                          ctypes.c_double(10.0),
                                          self.DAQmx_Val_GroupByScanNumber,
                                          self.data.ctypes.data,
                                          len(self.data),
                                          ctypes.byref(read), None)
            if self.nidaq.DAQmxWaitUntilTaskDone(self.taskHandle, ctypes.c_double(4.0)) < 0:
                print "reading out in auto mode"
                self.nidaq.DAQmxStopTask(self.taskHandle)
                self.nidaq.DAQmxDisableStartTrig(self.taskHandle)
                self.nidaq.DAQmxStartTask(self.taskHandle)
                self.CHK(self.nidaq.DAQmxReadAnalogF64(self.taskHandle,
                                                       self.samples_per_measurement,
                                                       ctypes.c_double(10.0),
                                                       self.DAQmx_Val_GroupByScanNumber,
                                                       self.data.ctypes.data,
                                                       len(self.data),
                                                       ctypes.byref(read), None), "ReadAnalogF64")
                if self.nidaq.DAQmxWaitUntilTaskDone(self.taskHandle, ctypes.c_double(4.0)) < 0:
                    print "Something went wrong."
                    raise ValueError
      
            self.nidaq.DAQmxStopTask(self.taskHandle)
            self.CHK(self.nidaq.DAQmxCfgDigEdgeStartTrig(self.taskHandle,
                                                         ctypes.c_char_p(self.triggerSource),
                                                         ctypes.c_int32(self.DAQmx_Val_Rising)),
                     "CfgDigEdgeStartTrig_Rising")
            self.CHK(self.nidaq.DAQmxStartTask(self.taskHandle), "Restarting triggered task")

            # put all of the data in a dictionary mapping analog input channels to the corresponding voltages
            powers_usort = {}
            for i, chan in enumerate(self.channels_to_open):
                powers_usort.update({chan: self.data[i]})
            #print powers_usort

            if channel_name is not None:
                assert channel_name in self.channels.keys(), "channel_name is not a Monitor Channel"

            # place the (possibly) converted data, into a dictionary to be returned.
            powers = {}
            #print self.channels
            # if there are many_channels, check if a channel_name has been specified, if so return data from that
            # channel. Otherwise return all of the data in a large dictionary.
            if self.many_channels:
                if channel_name is None:
                    for chan in self.channels.keys():
                        powers[chan] = {}
                        for key, value in self.channels[chan]:
                            if self.convert:
                                func = self.conversion[chan][key]
                                powers[chan].update({key: func(powers_usort[value])})
                            else:
                                powers[chan].update({key: powers_usort[value]})
                else:
                    #print self.channels[channel_name].keys()
                    for key in self.channels[channel_name].keys():
                        value = self.channels[channel_name][key]
                        if self.convert:
                            #print self.channels[channel_name]
                            #print channel_name
                            #print key, value
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
            return powers
        except KeyboardInterrupt:
            self.close()
            raise KeyboardInterrupt
            
    def close(self):
        print 'Closing DAQmx task'
        self.CHK(self.nidaq.DAQmxStopTask(self.taskHandle), "Stopping Task")
        self.CHK(self.nidaq.DAQmxClearTask(self.taskHandle), "Clearing Task")