# TODO:
* Refactor code to make use of less ambiguous terms "Stream" to refer to a list of data channels of interest, "Field" to
refer to a given data field on the server, and "Channel" to refer to the measurement port on a device. Currently, all three
are just channel.
* Save measured data locally to some sort of buffer variable or file, going back a certain amount of time. Use these data
to plot measurements in real time.
* Interface to change and set Stream, field and channel configuration without having to hard code the info into the
HybridMonitor.py file. Allow updating this info wihtout restarting entire program, and minimizing the number of streams
to Origin that need to be closed and re-opened 
