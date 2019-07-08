# -*- coding: utf-8 -*-
"""
Created on Fri Jun 28 17:58:42 2019

@author: Wendt
"""

import random
from Monitor import Monitor as Mon

class DummyMonitor(Mon):
    
    def __init__(self, channels, channel_names):
        Mon.__init__(self,channels,channel_names)
    
    def measure(self,channel_name=None):
        
        if channel_name is not None:
            assert channel_name in self.channels.keys(), "%s is not a Monitor Channel" % channel_name
        
        data = {}
        
        ch = self.channels[channel_name]
        for data_name in self.stream_names[channel_name]:
            data.update({data_name: random.random()})
        return data
    
    def close(self):
        print "dummy channel closed"