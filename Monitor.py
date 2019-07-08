class Monitor(object):
    """
    A template class from which the other Monitors in Hybrid should inherit
    """

    # You should overwrite this. Dictionary of error codes to what they mean
    # This should be available from your device
    ERRORS = {0: 'Ok'}

    def __init__(self, channels):
        """
        Initialize the monitor
        :param channels: A dictionary of dictionaries which map origin stream channel
            names to dictionaries which map data names to monitor input channels
                Or a dictionary mapping data names to monitor input channels
        """
        tmp = channels.keys()

        # If channels is a dictionary of dictionary, this monitor handles many streams
        # otherwise it handles a single stream
        self.many_channels = isinstance(channels[tmp[0]], type({}))
        print self.many_channels

        # all of the channel info should be in channels
        self.channels = channels

        # treat channel names and stream names based on self.many_channels
        if self.many_channels:
            self.channel_names = tmp
            self.stream_names = {}
            # stream names is a dictionary of channel names to list of stream names
            for key, value in self.channels.iteritems():
                print(key)
                print(value)
                self.stream_names.update({key: value.keys()})
        else:
            # channel names should be irrelevant and stream names should correspond to
            # keys in channels
            self.channel_names = None
            self.stream_names = tmp

    def start_unit(self):
        """
        Overwrite this function. It should start the connection with the unit.
        :return: Error: an integer corresponding to an internal error code
        """
        return 0

    def measure(self, channel_name = None):
        """
        Overwrite this function. It should query the device channels associated with
        channel_name.
        If channel_name is set to None it queries all active channels.
        If self.many_channels is not true it ignores channel_name and queries active channels
        :param channel_name: String. Name of Hybrid channel to access. If self.many_channels is
            false, this is ignored
        :return: data: dictionary : if channel_name is set, or self.many_channels is false {stream_name: data}
                    otherwise {channel_names: {stream_names: data}}
        """

        if channel_name is not None:
            assert channel_name in self.channels.keys(), "channel_name is not a Monitor Channel"

        data = {}
        return data

    def close(self):
        """
        Overwrite this function. Closes connection with the unit
        :return: int, Internal Error code for the unit.
        """
        return 0