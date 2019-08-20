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
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from functools import partial
from datetime import datetime, timedelta
from matplotlib.dates import DateFormatter
import time
import Queue
import zmq
import json

def timeavg(datetimelist,navg):
    #average times, datetime makes this hard
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
    def __init__(self,waitsecs,datatype,serv,mons):
        """
        Initialize GUI.
        Open channel selection dialog and connect to selected channels.
        Create data variables and buttons for all channels.
        :param waitsecs: number of seconds to wait between updating plots
        :param datatype: type of data expected from channels (assumed to be same for all)
        :param serv: server
        :param mons: monitors associated with channels to open
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
        
        self.chmonitor = {}
        
        self.mons = mons
        self.channeldict = {}
        for mon in mons:
            if mon.many_channels:
                self.channeldict.update(mon.channels)
                for ch in mon.channels:
                    self.chmonitor.update({ch: mon})
            else: 
                self.channeldict.update({mon.channel_names: mon.channels})
                self.chmonitor.update({mon.channel_names: mon})
        self.channelnames = self.channeldict.keys()
        
        #channels is dictionary to contain actual open channel objects
        self.channels = {}
        
        #open/plotchannels contain boolean for each channel: True if open, else False 
        #openchannels tracks open channels and plotchannels tracks channels actively plotted
        self.openchannels = {}
        self.plotchannels = {}
        self.datatype = datatype
        self.serv = serv
            
        self.queues = {}
        for name in self.channelnames:
            self.queues[name] = Queue.Queue()
        self.waitsecs = waitsecs
        
        self.started = False
        
        # define dictionaries to hold variables for each channel
        
        self.times = {}
        self.data = {}
        
        self.figs = {}
        self.axes = {}
        self.lines = {}
        self.canvases = {}
        self.scrollbars = {}
        self.windows = {}
        
        self.buttonframe = Frame(self.root)
        self.buttonframe.pack(fill=X,expand=1)
        self.buttonframe.grid_columnconfigure(0,weight=1)
        self.buttonframe.grid_columnconfigure(1,weight=1)
        self.buttons = {}
        self.plotbuttons = {}
        
        self.lbl = Label(self.buttonframe,text="Open and close channels:",width=40)
        self.lbl.grid(row=0,column=0,sticky='ew')
        self.lbl3 = Label(self.buttonframe,text="Toggle channel plots:")
        self.lbl3.grid(row=0,column=1,sticky='ew')
        
        for j, chname in enumerate(self.channelnames):
            self.buttons.update({chname : Button(self.buttonframe,text="%s (closed)"%chname,relief=SUNKEN,bg="red",command=partial(self.toggle_chan,chname))})
            self.plotbuttons.update({chname : Button(self.buttonframe,text="Open plot",command=partial(self.toggle_plot,chname))})
            self.buttons[chname].grid(row=j+1,column=0,sticky='ew')
            self.plotbuttons[chname].grid(row=j+1,column=1,sticky='ew')
            self.openchannels.update({chname : False})
            self.plotchannels.update({chname : False})
            self.times.update({chname : []})
            self.data.update({chname : {}})
            self.figs.update({chname : Figure(figsize=(8,1.5*len(self.channeldict[chname])))})
            self.axes.update({chname : []})
            self.lines.update({chname : {}})
            for i, dataname in enumerate(self.channeldict[chname]):
                self.data[chname][dataname] = []
                self.axes[chname].append(self.figs[chname].add_subplot(len(self.channeldict[chname]),1,i+1))
                self.axes[chname][i].xaxis.set_major_formatter(DateFormatter('%H:%M'))
                self.figs[chname].set_tight_layout(True)
        
        self.get_origin_data()
        
        # open channels requested by user in initial dialog
        d = ChannelOpenDialog(self.root,self.channelnames)
        self.defaultchannels = d.result
        
        for chname in self.defaultchannels:
            self.open_channel(chname,datatype,serv,self.chmonitor[chname])
        
        self.start()
    
    def run(self):
        self.root.mainloop()
        
    def set_tlim(self,event):
        #set time window limit based on typed time
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
        #set time to average over based on typed time
        try:
            self.tavgsec.set(int(self.tavgsec_display.get()))
            self.tavgslider.set(self.tavgsec.get()+60*self.tavgmin.get())
            self.tavgsec.set(self.tavgslider.get()%60)
            self.tavgsec_display.set("%02d" % self.tavgsec.get())
            self.tavgmin.set((self.tavgslider.get()-self.tavgsec.get())/60)
        except Exception as e:
            tkMessageBox.showerror("Error","Invalid entry. Please enter a number.\nError: %s" % e)
    
    def set_entries(self,event):
        #set time window and average time based on slider values
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
        #will still collect data when plotchannels is False
        #will only average and plot data when plotchannels is True
        
        while not self.queues[chname].empty():
            
            
            #data uploaded to dictionary in queue by MonitorThread, needs to be retrieved
            qitem = self.queues[chname].get() 
            t = qitem['measurement_time']
            
            #convert time from datestamp to datetime object format, add to time list
            if len(self.times[chname]) > 0 and self.times[chname][0] < self.times[chname][-1]-timedelta(days=1):
                self.times[chname] = self.shift1(self.times[chname],datetime.fromtimestamp(t/2**32))
                for dataname in self.channels[chname].data_names:
                    self.data[chname][dataname] = self.shift1(self.data[chname][dataname],qitem[dataname])
            else:
                self.times[chname] = np.append(self.times[chname],datetime.fromtimestamp(t/2**32))
                for dataname in self.channels[chname].data_names:
                    self.data[chname][dataname] = np.append(self.data[chname][dataname],qitem[dataname])
            
            #number of points to average over based on time to avg/data time spacing
            navg = self.tavgslider.get()/self.waitsecs
            
            if self.plotchannels[chname]:
                #create temporary time average array
                temp_t = timeavg(self.times[chname],navg)
                    
                currentt = temp_t[-1]
                timewindow = timedelta(seconds=self.tlimitslider.get()*60)
                    
                tlim_index = np.searchsorted(temp_t,currentt-timewindow)
                    
                plot_t = temp_t[tlim_index:]
            
                #plot data for each field in channelstream
                for j, dataname in enumerate(self.channels[chname].data_names):
                    #data averaging done in temporary way in case navg changes
                    tempdata = np.pad(self.data[chname][dataname],(0, (navg-self.data[chname][dataname].size%navg)%navg),mode='constant',constant_values=np.NaN)
                    tempdata = tempdata.reshape(-1,navg)
                    tempdata = np.nanmean(tempdata,axis=1)
                    
                    plotdata = tempdata[tlim_index:]
                    
                    self.lines[chname][dataname].set_xdata(temp_t)
                    self.lines[chname][dataname].set_ydata(tempdata)
                    
                    self.axes[chname][j].set_xlim([currentt-timewindow,currentt])
                    self.axes[chname][j].set_ylim([np.amin(plotdata),np.amax(plotdata)])
                    
                    #self.figs[chname].autofmt_xdate()
                self.figs[chname].canvas.draw()
                self.figs[chname].canvas.flush_events()
                #self.canvases[chname].draw()
    
    def shift1(self, arr, value=np.nan):
        #efficient shifting algorithm to discard first element and add value at end
        result = np.empty_like(arr)
        result[-1] = value
        result[:-1] = arr[1:]
        return result
            
    def start(self,event=None):
        try:
            self.started=True
            self.plot_all()
            for chname in self.channelnames:
                for j,dataname in enumerate(self.channeldict[chname]):
                    self.lines[chname][dataname], = self.axes[chname][j].plot(self.times[chname],self.data[chname][dataname])
                    self.axes[chname][j].set_title(dataname)
            print "Started GUI."
        except Exception as e:
            print e
            tkMessageBox.showerror("Error","Error in plotting. Please try again.\nError: %s" % e)
    
    def open_channel(self,chname, datatype, serv, mon):
        #open channel by creating channel object and add to channel
        self.channels.update({chname : Ch(chname,datatype,serv,self.channeldict[chname],mon)})
        self.openchannels.update({chname : True})
        self.buttons[chname].config(bg="green",relief=RAISED,text="%s (open)"%chname)
        
        #self.open_plot(chname)
    
    def open_plot(self,chname):
        #create window and canvas to plot in
        if not self.openchannels[chname]:
            self.open_channel(chname,self.datatype,self.serv,self.chmonitor[chname])
        self.windows.update({chname : Toplevel()})
        self.windows[chname].title(chname)
        self.windows[chname].protocol("WM_DELETE_WINDOW", partial(self.close_plot,chname))
        self.windows[chname].resizable(width=False, height=True)
        
        size=self.figs[chname].get_size_inches()*self.figs[chname].dpi
        temp = Canvas(master=self.windows[chname],width=size[0],height=4*self.figs[chname].dpi)
        temp.pack(side=LEFT,fill=Y,expand=1,padx=5,pady=5)
        
        self.scrollbars.update({chname : Scrollbar(self.windows[chname])})
        self.scrollbars[chname].pack(side=RIGHT,fill=Y)
        
        for j, dataname in enumerate(self.channels[chname].data_names):
            self.axes[chname][j].cla()
            self.lines[chname][dataname], = self.axes[chname][j].plot(self.times[chname],self.data[chname][dataname])
        
        self.canvases.update({chname : FigureCanvasTkAgg(self.figs[chname],temp)})
        
        temp.config(yscrollcommand=self.scrollbars[chname].set)
        self.scrollbars[chname].config(command=temp.yview)
        temp.create_window(0,0,window=self.canvases[chname].get_tk_widget(),anchor=NW)
        temp.config(scrollregion=temp.bbox(ALL))
        temp.bind('<Enter>',partial(self.bind_mousewheel,temp))
        temp.bind('<Leave>',partial(self.unbind_mousewheel,temp))
        
        self.canvases[chname].draw()
        self.plotbuttons[chname].config(text="Close plot",relief=SUNKEN)
        self.plotchannels[chname] = True
        
    def close_channel(self,chname):
        #modified from close_all in HybridMonitor.py
        print "closing channel: " + chname
        try:
            self.openchannels.update({chname : False})
            status = self.channels[chname].hang()
            del self.channels[chname]
            self.buttons[chname].config(bg="red",relief=SUNKEN,text="%s (closed)"%chname)
            #self.plotbuttons[chname].config(state=DISABLED)
            if self.plotchannels[chname]:
                self.close_plot(chname)
        except Exception as e: 
            tkMessageBox.showerror("Error","Error in closing channel.\nError: %s" % e)
        return status
    
    def close_plot(self,chname):
        self.windows[chname].destroy()
        self.plotbuttons[chname].config(text="Open plot",relief=RAISED)
        self.plotchannels[chname] = False
        
    def bind_mousewheel(self,canv,event):
        canv.bind_all("<MouseWheel>", partial(self.on_mousewheel,canv))
        
    def unbind_mousewheel(self,canv,event):
        canv.unbind_all("<MouseWheel>")
        
    def on_mousewheel(self,canv,event):
        canv.yview_scroll(int(-1*(event.delta/120)),"units")
    
    def on_closing(self):
        #executed when root window is closed, closes all channels
        if tkMessageBox.askokcancel("Quit","Quit and close all open channels?"):
            try:
                status = np.empty(len(self.channels),dtype=object)
                chnames = self.channels.keys()
                for i, chname in enumerate(chnames):
                    status[i] = self.close_channel(chname)
                for mon in self.mons:
                    mon.close()
            finally:
                self.root.destroy()
    
    def toggle_chan(self,chname):
        #button function to open/close channels from main window
        if self.openchannels[chname]:
            self.close_channel(chname)
        else:
            self.open_channel(chname,self.datatype,self.serv,self.chmonitor[chname])
        
    def toggle_plot(self,chname):
        if self.plotchannels[chname]:
            self.close_plot(chname)
        else:
            self.open_plot(chname)
    
    def get_origin_data(self):
        config = self.serv.config
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        
        #copied from origin-reader-HybridMag:
        host = 'hexlabmonitor.physics.wisc.edu' 
        port = 5561
        socket.connect("tcp://%s:%s" % (host,port))
        start = 24*60*60
        stop = 0*24*60*60
        
        stream_data = {}
        
        for stream in self.channelnames: 
            print "sending raw read request for stream %s" % stream
            request_obj = {'stream': stream, 'raw': True, 'start': time.time()-start, 'stop':time.time()-stop}
            socket.send(json.dumps(request_obj))
            response = socket.recv()
            dat = json.loads(response)
            truedata = dat[1]
            stream_data[stream] = truedata
            fields = stream_data[stream].keys()
#            print fields
#            print self.data[stream].keys()
            for field in fields:
                try: 
                    if field == u'measurement_time':
                        time_data = stream_data[stream][field]
                        for timestamp in time_data:
                            self.times[stream].append(datetime.fromtimestamp(timestamp/2**32))
                        self.times[stream] = np.array(self.times[stream])
                    elif field == u'error':
                        print "Error:", stream_data[stream][field]
                    elif field == u'stream':
                        pass
                    else:
                        self.data[stream][field] = np.array(stream_data[stream][field])
                        print field
                except Exception as e:
                    print 'Error in getting stream %s, field %s: %s' % (stream, field, e)
            
            
            
            
        
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