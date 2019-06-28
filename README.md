# HybridMonitor
Parameter Monitoring Program used in the Hybrid Experiment

# Installation:
1. clone this repo onto your machine.  
2. Download the Origin repo from https://github.com/QuantumQuadrate/Origin.
3. Replace the link labeled Origin with a symbolic link to your origin repo  
   -If your filepath looks like GitRepos/Origin/origin/ set the link to the innermost origin folder  
   -You can also change the "fullbasepath" in HybridMonitor.py, to your local Origin path
4. Run python HybridMonitor.py

# Programming guide:
This program consists uses the HybridMonitor.py file as a sort of Main, and a few classes to control our interactions
with our measurement devices(Monitors) and the server(channels*).

## Class Types:
_Monitor_ : A monitor class is a class that serves as an interface between the computer and a measurement device (such as
an NIDAQ). A monitor class represents the connection to a given device, but a given device can log data for many streams,
thus the same monitor class should be able to measure for different streams independently.
A monitor class should implement the following functions:
* start_unit(self) : Opens connection with the device and performs any necessary initialization
* measure(self, channel_name = None) : query the device to measure channels associated with channel_name
* close(self) : should gracefully close connection with the unit

_Channel_ : (Should be Stream) represents a given stream and mediates its connection to the server and to the device that
takes it's data


# Current Monitor Classes:

## Picos Temperature Monitor (PicosMonitor.py)
* Interfaces with the Picos TC-88 Temperature Monitor
  * Thermocouple logger
* Driver Documentation: See "Thermocouple logger Programmer's guide.pdf"

## NIDAQMonitor (PickoffMonitor.py)
* Interfaces with the NI DAQmx usb connected A/DC
* Written to take data for many streams and convert measured voltages to more relevant info
* Driver Documentation: http://zone.ni.com/reference/en-XX/help/370471AA-01/
 
