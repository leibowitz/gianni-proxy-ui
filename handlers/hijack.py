import sys

from sock import BaseSockJSConnection
from shared import util

class HijackConnection(BaseSockJSConnection):

    def on_open(self, info):
        self.info = info
        uuid = self.session.name
        self.sock = util.open_socket(uuid)
        pass
        
    def on_message(self, msg):
        #print self.info.arguments
        #print self.session.conn
        #print self.session.server
        uuid = self.session.name
        print "received ", msg
        try:
            # Send data
            print >>sys.stderr, 'sending "%s"' % msg
            self.sock.sendall(msg)
        except Exception as e:
            print >>sys.stderr, 'error "%s"' % e
            self.close()
            pass
        if not self.sock:
            self.send("error")
        
    def on_close(self):
        self.sock.close()
        print "done"
