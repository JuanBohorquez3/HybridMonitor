# -*- coding: utf-8 -*-
"""
Created on Mon Jul  1 17:17:06 2019

@author: Danny Wendt

Uses Tkinter to define a GUI class specific to the HybridMonitor implementation.
"""
from Tkinter import *
import tkMessageBox
import numpy as np
from Channel import Channel as Ch
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from functools import partial
from datetime import datetime, timedelta
import time

def timeavg(datetimelist,navg):
    #average times, datetime is stupid
    dlist = map(datetime.timetuple, datetimelist)
    timestamplist = np.array(map(time.mktime,dlist))
    timestamplist = np.pad(timestamplist,(0, (navg-len(timestamplist)%navg)%navg),mode='constant',constant_values=np.NaN)
    timestamplist = timestamplist.reshape(-1,navg)
    timestampavg = np.nanmean(timestamplist,axis=1)
    return map(datetime.fromtimestamp,timestampavg)

class MonitorGUI:
    """
    GUI to handle channels (streams) used in HybridMonitor.py
    Provides functionality to toggle channels enabled/disabled.
    Uses thread-safe queues to get data passed from MonitorThread.
    Plots data vs. time for enabled channels.
    """
    def __init__(self,channeldict,q,waitsecs,datatype,serv,mon):
        """
        Initialize GUI.
        Open channel selection dialog and connect to selected channels.
        Create data variables and buttons for all channels.
        :param channeldict: a dictionary of channels with names as keys
        :param q: a dictionary of queues keyed to channel names
        :param waitsecs: number of seconds to wait between updating plots
        :param datatype: type of data expected from channels (assumed to be same for all)
        :param serv: server
        :param mon: monitor associated with channels to open
        """
        self.root = Tk()
        self.root.title("Hybrid Data Monitor")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        frame = Frame(self.root)
        frame.pack(fill=BOTH,expand=1)
        
        #create labels and sliders for time window and time averaging
        tlimitframe = Frame(frame)
        tlimitframe.pack(fill=BOTH,expand=1)
        tlimitframe.grid_columnconfigure(0,weight=1)
        
        self.tlimitlabel = Label(tlimitframe,text="Time window to view (minutes, hrs:min):")
        self.tlimitlabel.grid(row=0,columnspan=2,sticky="ew")
        
        self.tlimmin = IntVar()
        self.tlimmin.set(10)
        self.tlimhrs = IntVar()
        self.tlimhrs.set(0)
        self.tlimmin_display = StringVar()
        self.tlimmin_display.set("%02d" % self.tlimmin.get())
        self.tlimitslider = Scale(tlimitframe,from_=10,to=24*60,resolution=10,orient=HORIZONTAL)
        self.tlimitslider.grid(row=1,sticky="ew")
        self.tlimitslider.bind("<B1-Motion>",self.set_entries)
        self.tlimitslider.bind("<Button-1>",self.set_entries)
        
        self.tlimithrs = Entry(tlimitframe,textvariable=self.tlimhrs,width=5)
        self.tlimithrs.grid(row=1,column=1)
        self.tlimithrs.bind("<Return>", self.set_tlim)
        
        lbl1 = Label(tlimitframe,text=":")
        lbl1.grid(row=1,column=2)
        
        self.tlimitmin = Entry(tlimitframe,textvariable=self.tlimmin_display,width=5)
        self.tlimitmin.grid(row=1,column=3)
        self.tlimitmin.bind("<Return>", self.set_tlim)
        
        self.tavglabel = Label(tlimitframe,text="Time to average over (seconds, min:sec):")
        self.tavglabel.grid(row=2,columnspan=2,sticky="ew")
        
        self.tavgmin = IntVar()
        self.tavgmin.set(0)
        self.tavgsec = IntVar()
        self.tavgsec.set(4)
        self.tavgsec_display = StringVar()
        self.tavgsec_display.set("%02d" % self.tavgsec.get())
        self.tavgslider = Scale(tlimitframe,from_=waitsecs,to=1800,resolution=waitsecs,orient=HORIZONTAL)
        self.tavgslider.grid(row=3,sticky="ew")
        self.tavgslider.bind("<B1-Motion>",self.set_entries)
        self.tavgslider.bind("<Button-1>",self.set_entries)
        
        self.tavgmins = Entry(tlimitframe,textvariable=self.tavgmin,width=5)
        self.tavgmins.grid(row=3,column=1)
        self.tavgmins.bind("<Return>", self.set_tavg)
        
        lbl2 = Label(tlimitframe,text=":")
        lbl2.grid(row=3,column=2)
        
        self.tavgsecs = Entry(tlimitframe,textvariable=self.tavgsec_display,width=5)
        self.tavgsecs.grid(row=3,column=3)
        self.tavgsecs.bind("<Return>", self.set_tavg)
        
        self.lbl = Label(frame,text="Available channels:",width=50)
        self.lbl.pack(fill=X,expand=1)
        
        self.channeldict = channeldict
        self.channelnames = channeldict.keys()
        
        #channels is dictionary to contain actual open channel objects
        self.channels = {}
        
        #openchannels contains boolean for each channel: True if open, else False 
        self.openchannels = {}
        self.datatype = datatype
        self.serv = serv
        self.mon = mon
        
        # open channels requested by user in initial dialog
        d = ChannelOpenDialog(self.root,self.channelnames)
        self.defaultchannels = d.result
            
        self.queues = q
        self.waitsecs = waitsecs
        
        self.started = False
        
        # define dictionaries to hold variables for each channel
        
        self.times = {}
        self.data = {}
        
        self.figs = {}
        self.axes = {}
        self.canvases = {}
        self.windows = {}
        self.buttons = {}
        
        for chname in self.channelnames:
            self.buttons.update({chname : Button(self.root,text=chname,relief=SUNKEN,bg="red",command=partial(self.callback,chname))})
            self.buttons[chname].pack(fill=X,expand=1)
            self.openchannels.update({chname : False})
            self.times.update({chname : []})
            self.data.update({chname : []})
            self.figs.update({chname : Figure(figsize=(8,1.5*len(channeldict[chname])))})
            self.axes.update({chname : []})
            for i, dataname in enumerate(self.channeldict[chname]):
                print dataname
                self.data[chname].append([])
                self.axes[chname].append(self.figs[chname].add_subplot(len(self.channeldict[chname]),1,i+1))
                self.figs[chname].tight_layout()
        
        for chname in self.defaultchannels:
            self.open_channel(chname,datatype,serv,mon)
        
        self.start()
    
    def run(self):
        self.root.mainloop()
        
    def set_tlim(self,event):
        try:
            self.tlimmin.set(int(self.tlimmin_display.get()))
            self.tlimitslider.set(self.tlimmin.get()+60*self.tlimhrs.get())
            self.tlimmin.set(self.tlimitslider.get()%60)
            self.tlimmin_display.set("%02d" % self.tlimmin.get())
            self.tlimhrs.set((self.tlimitslider.get()-self.tlimmin.get())/60)
        except Exception as e:
            tkMessageBox.showerror("Error","Invalid entry. Please enter a number.\nError: %s" % e)
        #print(self.tlim.get())
    
    def set_tavg(self,event):
        try:
            self.tavgsec.set(int(self.tavgsec_display.get()))
            self.tavgslider.set(self.tavgsec.get()+60*self.tavgmin.get())
            self.tavgsec.set(self.tavgslider.get()%60)
            self.tavgsec_display.set("%02d" % self.tavgsec.get())
            self.tavgmin.set((self.tavgslider.get()-self.tavgsec.get())/60)
        except Exception as e:
            tkMessageBox.showerror("Error","Invalid entry. Please enter a number.\nError: %s" % e)
    
    def set_entries(self,event):
        self.tlimmin.set(self.tlimitslider.get()%60)
        self.tlimmin_display.set("%02d" % self.tlimmin.get())
        self.tlimhrs.set((self.tlimitslider.get()-self.tlimmin.get())/60)
        self.tavgsec.set(self.tavgslider.get()%60)
        self.tavgsec_display.set("%02d" % self.tavgsec.get())
        self.tavgmin.set((self.tavgslider.get()-self.tavgsec.get())/60)
    
    def plot_all(self):
        if self.started:
            for chname in self.channels:
                self.plot_channel(chname)
            self.root.after(1000*self.waitsecs,self.plot_all)
    
    def plot_channel(self,chname):
        while not self.queues[chname].empty():
            #data uploaded to dictionary in queue by MonitorThread, needs to be retrieved
            qitem = self.queues[chname].get() 
            t = qitem['measurement_time']
            
            #convert time from datestamp to datetime object format, add to time list
            self.times[chname].append(datetime.fromtimestamp(t/2**32))
            
            #number of points to average over based on time to avg/data time spacing
            navg = self.tavgslider.get()/self.waitsecs
            
            #plot data for each field in channelstream
            for j, dataname in enumerate(self.channels[chname].data_names):
                self.axes[chname][j].cla()
                self.data[chname][j].append(qitem[dataname])
                temp_t = np.array(self.times[chname])
                temp_t = timeavg(temp_t,navg)
                
                #data averaging done in temporary way in case navg changes
                tempdata = np.array(self.data[chname][j])
                tempdata = np.pad(tempdata,(0, (navg-tempdata.size%navg)%navg),mode='constant',constant_values=np.NaN)
                tempdata = tempdata.reshape(-1,navg)
                tempdata = np.nanmean(tempdata,axis=1)
                
                self.axes[chname][j].plot(temp_t,tempdata)
                self.axes[chname][j].set_title(dataname)
                currentt = temp_t[-1]
                timewindow = timedelta(seconds=self.tlimitslider.get()*60)
                self.axes[chname][j].set_xlim([currentt-timewindow,currentt])
            #self.figs[chname].autofmt_xdate()
            self.canvases[chname].draw()
            
    def start(self,event=None):
        try:
            self.started=True
            self.plot_all()
            print "Started plotting."
        except Exception as e:
            print e
            tkMessageBox.showerror("Error","Error in plotting. Please try again.\nError: %s" % e)
    
    def open_channel(self,chname, datatype, serv, mon):
        #open channel by creating channel object and add to channel
        self.channels.update({chname : Ch(chname,datatype,serv,self.channeldict[chname],mon)})
        self.openchannels.update({chname : True})
        self.buttons[chname].config(bg="green",relief=RAISED)
        
        #create window and canvas to plot in
        self.windows.update({chname : Toplevel()})
        self.windows[chname].title(chname)
        self.windows[chname].protocol("WM_DELETE_WINDOW", partial(self.close_channel,chname))
        self.canvases.update({chname : FigureCanvasTkAgg(self.figs[chname],self.windows[chname])})
        self.canvases[chname].get_tk_widget().pack(fill=BOTH,expand=1,padx=5,pady=5)
        self.canvases[chname].draw()
        
    def close_channel(self,chname):
        #modified from close_all in HybridMonitor.py
        print "closing channel: " + chname
        try:
            self.openchannels.update({chname : False})
            status = self.channels[chname].hang()
            del self.channels[chname]
            self.windows[chname].destroy()
            self.buttons[chname].config(bg="red",relief=SUNKEN)
        except Exception as e: 
            tkMessageBox.showerror("Error","Error in closing channel.\nError: %s" % e)
        return status
    
    def on_closing(self):
        #executed when root window is closed, closes all channels
        if tkMessageBox.askokcancel("Quit","Quit and close all open channels?"):
            status = np.empty(len(self.channels),dtype=object)
            chnames = self.channels.keys()
            for i, chname in enumerate(chnames):
                try:
                    status[i] = self.close_channel(chname)
                except: 
                    self.root.destroy()
            print self.openchannels
            self.root.destroy()
    
    def callback(self,chname):
        #button function to open/close channels from main window
        if self.openchannels[chname]:
            self.close_channel(chname)
        else:
            self.open_channel(chname,self.datatype,self.serv,self.mon)
        
        
        
        
class ChannelOpenDialog(Toplevel):
    """
    Dialog window to choose channels to initially open.
    Modified from Dialog class from effbot.org
    http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
    """
    def __init__(self,parent,channelnames):
        """
        Initialize dialog. 
        :param parent: Parent window for dialog
        :param channelnames: List of channel names to choose from
        """
        Toplevel.__init__(self, parent)
        self.transient(parent)
                
        self.parent = parent
        self.result = []
        
        self.channelnames = channelnames
        
        #dictionary to hold Tkinter checkbox variables keyed to channel names
        self.enabledlist = {}
        
        body = Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5)

        self.buttonbox()

        self.grab_set()

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))

        self.initial_focus.focus_set()

        self.wait_window(self)
    
    def body(self, master):
        #add widgets to body, iterate over channel names to make checkboxes
        Label(master,text="Enable channels:").pack()
        
        for chname in self.channelnames:
            self.enabledlist.update({chname : IntVar()})
            c = Checkbutton(master, text=chname,variable=self.enabledlist[chname])
            c.pack(anchor="w")
        return None
    
    def buttonbox(self):
        # add standard button box.

        box = Frame(self)

        w = Button(box, text="OK", width=10, command=self.ok, default=ACTIVE)
        w.pack(side=LEFT, padx=5, pady=5)
#        w = Button(box, text="Cancel", width=10, command=self.cancel)
#        w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()
    
    def ok(self, event=None):

        if not self.validate():
            self.initial_focus.focus_set() # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()

        self.cancel()
    
    def cancel(self, event=None):
        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()
    
    def validate(self):
        return 1
    
    def apply(self):
        for name in self.enabledlist:
            if self.enabledlist[name].get():
                self.result.append(name)
        
#FOR TESTING:            
#qq = Queue.Queue(10)
#app = GUI(qq,1)
#app.run()