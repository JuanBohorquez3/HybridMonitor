# -*- coding: utf-8 -*-# -*- coding: utf-8 -*-
"""
@Author: Juan Bohorquez
Based on code by Matt Ebert

This class continuously logs data from different sources within hybrid to the 
Origin data server.
"""
import os
import time
import numpy as np
import sys
from Channel import Channel as Ch
import PicosMonitor
import NIDAQMonitor
import DummyMonitor
import GUI
import matplotlib as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import Queue
'''
TODO:
[ ] Refactor Channels(e.g "Hybrid_Beam_Balances") to Streams
[ ] Refactor channels(e.g "X","Y") to Fields
'''

#Defined here for now to avoid issues with importing
class MonitorThread(threading.Thread):
    """
    A Thread class to handle communicating with channels (streams).
    Executes code, moved from end of this program, to allow GUI to run in main thread.
    """
    def __init__(self,channels,config,queues,stop_event):
        """
        Initialize monitoring thread
        :param channels: a dictionary of channels with names as keys, to be communicated with
        :param config: 
        :param queues: a dictionary of queues keyed to channel names
        :param stop_event: a threading Event to ensure thread is stopped when GUI closes
        """
        threading.Thread.__init__(self)
        self.channels = channels
        self.config = config
        self.queues = queues
        self.stop_event = stop_event
        
    def run(self):
        print 'Begin communication thread'
        for channel in self.channels.values():
            print channel.name
        self.err = 0
        while not self.stop_event.is_set():
            try:
                # t1 = time.clock()
                for channel in self.channels.values():
                    print "sending " + channel.name
                    print "Measured :" + repr(channel.measure())
                    ts = current_time(self.config)
                    data = channel.data
                    data.update({TIMESTAMP: ts})
                    #print(data)
### Following try/except loop enables upload data to server
#                    try:
#                        channel.connection.send(**channel.data)
#                    except Exception:
#                        close_all(self.channels.values())
#                        raise Exception
                    self.queues[channel.name].put(data)
            # interrupt this with a keystroke and hang connection
                if self.err == 1:
                    break
                time.sleep(measurementPeriod)
        # FOR TIMING:
        # t2 = time.clock()
        # deltaT = t2 - t1
        # time.sleep(measurementPeriod - deltaT)

            except KeyboardInterrupt:
                # Trying to handle turning off the program monitor without leaving devices on and streams open
                #close_all(channels)
                # ^ NOW HANDLED BY GUI
                raise KeyboardInterrupt
                break
        
        print "Stopping communication thread."

def close_all(channel_list):
    """
    closes all the channels in the argument.
    Arguments:
        channels -- array of channels
        
    """
    '''
    # TODO :
        [ ] This doesn't work with keyboard interrupts. Look at downstream classes failure modes and Fix
    '''
    status = np.empty(len(channel_list),dtype=object)
    for i, chan in enumerate(channel_list):
        print "closing channel : " + chan.name
        status[i] = chan.hang()
    return status

# How often to measure data and log it
measurementPeriod = 4  # s

t0 = time.clock()
# we must first find ourselves
print 'finding ourselves'
fullBinPath = os.path.abspath(os.getcwd())
print fullBinPath
fullBasePath = os.path.dirname(fullBinPath)
print fullBasePath
## Works on Hybrid Machine
fullLibPath = os.path.join(fullBasePath, "origin\\origin\\lib")
fullCfgPath = os.path.join(fullBasePath, "origin\\origin\\config")
## Works on Danny's Machine
#fullLibPath = os.path.join(fullBasePath, "C:\\Users\\Wendt\\Documents\\Hybrid\\Origin\\lib")
#fullCfgPath = os.path.join(fullBasePath, "C:\\Users\\Wendt\\Documents\\Hybrid\\Origin\\config")
sys.path.append(fullLibPath)

print 'getting origin library'
from origin.client import server
from origin import current_time, TIMESTAMP

print 'initializing picos'
# initialize the picos monitor
tempChannels = {"Chamber": 1,
                "Door Coils": 2,
                "CPU Coils": 3,
                "CS Bellows": 4,
                "X1Y1": 5,
                "X2Y2": 6,
                "BreadBoard": 7,
                "LN2 FillPort": 8}
picosDLLPath = "C:\Program Files\Pico Technology\SDK\lib"
picos = PicosMonitor.TC08USB(tempChannels, dll_path=picosDLLPath, channel_names="Hybrid_Temp")

print 'Initializing NIDAQ'
# initialize the pickoff monitor
I2VChannels = {"X1": 'ai4',
               "X2": 'ai2',
               "Y1": 'ai0',
               "Y2": 'ai1',
               "Z1": 'ai3',
               "Z2": 'ai5'}
# pickoff conversions
I2VConversion = {"X1": lambda v: 0.758*v+0.031,
                 "X2": lambda v: 0.380*v+0.041,
                 "Y1": lambda v: 1.020*v-0.108,
                 "Y2": lambda v: 1.000*v-0.080,
                 "Z1": lambda v: 0.525*v-0.019,
                 "Z2": lambda v: 1.711*v-0.068}

MuxChannels = {"FORT": "ai6"}

MuxConversion = {"FORT": lambda v: v}

MagSensorChannels = {"X": 'ai8',
                     "Y": 'ai9',
                     "Z": 'ai10'}

MagConversion = {"X": lambda v: 0.2*v,
                 "Y": lambda v: 0.2*v,
                 "Z": lambda v: 0.2*v}

uWRabiChannels = {"Internal Mon": 'ai6',
                  "Circulator": 'ai7'}

uWRabiConversion = {"Internal Mon": lambda v: v,
                    "Circulator": lambda v: v}

lockChannel = {"1190": 'ai11'}

lockConversion = {"1190": lambda v: v}

ADCChan = {"Hybrid_Beam_Balances": I2VChannels,
           "Hybrid_Mag": MagSensorChannels,
           "Hybrid_Mux": MuxChannels,
           "Hybrid_uW": uWRabiChannels,
           "Hybrid_Locks": lockChannel}

ADCCon = {"Hybrid_Beam_Balances": I2VConversion,
          "Hybrid_Mag": MagConversion,
          "Hybrid_Mux": MuxConversion,
          "Hybrid_uW": uWRabiConversion,
          "Hybrid_Locks": lockConversion}

ADCDatatypes = {"Hybrid_Beam_Balances": "float",
          "Hybrid_Mag": "float",
          "Hybrid_Mux": "float",
          "Hybrid_uW": "float",
          "Hybrid_Locks": "int"}

NIDAQ = DummyMonitor.DummyMonitor(ADCChan,ADCChan.keys())
#NIDAQ = NIDAQMonitor.NIDAQmxAI(ADCChan, conversion=ADCCon,channel_names=ADCChan.keys())

print 'grabbing config file'
if len(sys.argv) > 1:
    if sys.argv[1] == 'test':
        configfile = os.path.join(fullCfgPath, "origin-server-test.cfg")
    else:
        configfile = os.path.join(fullCfgPath, sys.argv[1])
else:
    configfile = os.path.join(fullCfgPath, "origin-server.cfg")

import ConfigParser

config = ConfigParser.ConfigParser()
print configfile
config.read(configfile)

# something that represents the connection to the server
print 'grabbing server'
serv = server(config)

#print 'opening channels'
# open the channels
#channels = []
#channels.append(Ch("Temp", "float", serv, tempChannels, picos))
#channels.append(Ch("Beam_Balances", "float", serv, I2VChannels, NIDAQ))
#channels.append(Ch("Mag", "float", serv, MagSensorChannels, NIDAQ))
#channels.append(Ch("Mux", "float", serv, MuxChannels, NIDAQ))
#channels.append(Ch("uW","float",serv,uWRabiChannels,NIDAQ))

Monitors = [NIDAQ,
            picos]

# This might need to be more complicated, but you get the gist. Keep sending records forever

#qq = Queue.Queue()
stop_event = threading.Event()
mongui = GUI.MonitorGUI(measurementPeriod,ADCDatatypes,serv,Monitors)
monthread = MonitorThread(mongui.channels,config,mongui.queues,stop_event)
monthread.start()
mongui.run()
print "Exiting GUI."
stop_event.set()