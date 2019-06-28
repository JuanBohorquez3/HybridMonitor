
class Channel(object) :
    """
    A class to represent our connection to origin and to our data acquisition device (DAQ)
    """

    namespace = 'Hybrid'

    def __init__(self ,name ,data_type ,server ,data_map ,monitor):
        """

        :param name: String, the name of the channel on the origin server
        :param data_type: String, the data type to be written to the server.
        for options  origin/lib/origin/origin_data_types.py
        or origin-test-datatypes-binary
        :param server: server, the server object through which we connect to origin
        :param data_map: {String, data_names : Any, DAQ channels}
        :param monitor: Monitor, a monitor object through which we connect to our DAQ
        """
        self.name = self.namespace + '_' + name
        self.data_type = data_type
        self.server = server
        self.data_map = data_map
        self.data_names = data_map.keys()
        self.records = {}
        for data_name in self.data_names:
            self.records.update({data_name: data_type})
        self.monitor = monitor
        self.connection = self.connect()
        self.data = {}

    def connect(self):
        """
        lets the server know we are going to connect and will be sending this kind of data

        :return: conn, object represention our connection to the server
        """
        print self.records
        conn = self.server.registerStream(
            stream=self.name,
            records=self.records,
            timeout=60 * 1000)
        return conn

    def measure(self):
        """
        reads data from our DAQ and returns it as a dictionary
        :return: data, {data_names : data} dictionary mapping data streams to the relevant data
        """
        self.data = self.monitor.measure(self.name)
        return self.data

    def hang(self):
        """
        closes our connection to the server and to the DAQ
        :return: error code from the monitor class or the connection class
        """
        err_serv = self.connection.close()
        err_monitor = self.monitor.close()
        return [err_serv, err_monitor]
