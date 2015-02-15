import os
import tempfile
from tornado.ioloop import PeriodicCallback
from tornado import gen

from sock import BaseSockJSConnection
from shared import util

class BodyConnection(BaseSockJSConnection):
    filet = None
    position = 0

    def on_open(self, info):
        pass
        
    def on_message(self, fileid):
        #print "message [" + fileid + "]"
        filepath = os.path.join(tempfile.gettempdir(), "proxy-service", fileid)
        if os.path.exists(filepath):
            self.tail_file(filepath)
        else:
            #print "File does not exist"
            self.close()
        
    @gen.engine
    def tail_file(self, filepath):
        #print "opening file"
        #self.position = 0
        self._file = open(filepath)
        self.position = 0

        # Go to the end of file
        self._file.seek(0,2)
        self.position = self._file.tell()

        self.pcb = PeriodicCallback(self.check_data, 1000)
        self.pcb.start()

        # check for new data every second        
        #self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        #self.pcb = Callback(self.check_data)
        #self.pcb.start()
        #print "started"

    def check_data(self):
        if not self._file.closed:
            self._file.seek(self.position)
            line = self._file.readline()
            if line:
                self.position=self._file.tell()
                self.on_new_data(line)

#        self.on_new_data(data)
        #self.position = self.filet.follow(blocking=False, position=self.position)

    def on_new_data(self, data):
        #print "data ", data
        data = data.strip()

        if len(data) == 0:
            return

        try:
            data = util.nice_body(data, 'application/json')
            self.send(data)
            #json.dumps(json.loads(data), indent=4)
        except Exception as e:
            print e

    def on_close(self):
        #print "closing"
        if self._file is not None and not self._file.closed:
            self._file.close()
        self.pcb.stop()
        #self.position = 0
        #self.pcb.stop()
        #if self.filet != None:
        #    print self.filet
