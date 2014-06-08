import tornado.ioloop
import tornado.web
from tornado import gen
from datetime import datetime
import motor
import json
import pytz
import pymongo
from bson.objectid import ObjectId
import os
import tail
import time
from watcher import LogWatcher
from sockjs.tornado import SockJSRouter, SockJSConnection
from sockjs.tornado.periodic import Callback
from bson import json_util

class MySocket(SockJSConnection):
    def __init__(self, session):
        self.db = motor.MotorClient('mongodb://localhost:17017').open_sync().proxyservice
        super(MySocket, self).__init__(session)


class EchoConnection(MySocket):

    def on_open(self, info):
        collection = self.db['log_logentry']
        dn = datetime.utcnow()
        query = {'date': {'$gte': dn} }
        collection.find(query, tailable=True, await_data=True).tail(callback=self.on_new_requests)
        
    def on_message(self, msg):
        
        print "message ", msg

    def on_new_requests(self, result, err):

        if err:
            raise tornado.web.HTTPError(500, err)
        elif result:
            msg = json.dumps(result, default=json_util.default)

            self.send(msg)

class BodyConnection(SockJSConnection):
    filet = None
    position = 0

    def on_open(self, info):
        print "open"
        
    def on_message(self, fileid):
        print "message [" + fileid + "]"
        filepath = "/Users/giannimoschini/src/github.com/leibowitz/go-proxy-service/" + fileid
        self.tail_file(filepath)
        
    @gen.engine
    def tail_file(self, filepath):
        print "opening file"
        #self.position = 0
        self._file = open(filepath)
        self.position = 0

        # Go to the end of file
        self._file.seek(0,2)
        self.position = self._file.tell()

        self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        self.pcb.start()

        # check for new data every second        
        #self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        #self.pcb = Callback(self.check_data)
        #self.pcb.start()
        #print "started"

    def check_data(self):
        print "looking at data"
        if not self._file.closed:
            self._file.seek(self.position)
            line = self._file.readline()
            if line:
                self.position=self._file.tell()
                self.on_new_data(line)

#        self.on_new_data(data)
        #self.position = self.filet.follow(blocking=False, position=self.position)

    def on_new_data(self, data):
        print "data ", data
        self.send(data)

    def on_close(self):
        print "closing"
        if self._file is not None and not self._file.closed:
            self._file.close()
        self.pcb.stop()
        #self.position = 0
        #self.pcb.stop()
        #if self.filet != None:
        #    print self.filet



def get_numbers(ret, error):
    pass

def nice_headers(headers):
    return {k: v[0] for k, v in headers.iteritems() if len(v) != 0}

def nice_body(body, headers):
    if headers != None and 'Content-Type' in headers and headers['Content-Type'].split(';')[0] == 'application/json':
        return json.dumps(json.loads(body), indent=4)
    return body

class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db']['log_logentry']
        cursor = collection.find({}).sort([("$natural", pymongo.DESCENDING)]).limit(10)#.sort([('date', pymongo.DESCENDING)]).limit(10)
        entries = yield motor.Op(cursor.to_list)
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), EST=EST)

class ViewHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db']['log_logentry']

        entry = yield motor.Op(collection.find_one, {'_id': ObjectId(ident)})
        requestheaders = nice_headers(entry['request']['headers'])
        responseheaders = nice_headers(entry['response']['headers'])
        print entry['request']

        #requestbody = nice_body(entry['request']['body'], requestheaders)
        #responsebody = nice_body(entry['response']['body'], responseheaders)

        self.render("one.html", item=entry, 
                requestheaders=requestheaders, 
                responseheaders=responseheaders)
                #requestbody=requestbody, 
                #responsebody=responsebody)

db = motor.MotorClient('mongodb://localhost:17017', tz_aware=True).open_sync().proxyservice
EST = pytz.timezone('Europe/London')

handlers = [
    (r"/", MainHandler),
    (r"/item/(?P<ident>[^\/]+)", ViewHandler),
]
    
settings = dict(
    handlers=handlers,
    static_path=os.path.join(os.path.dirname(__file__), 'static'),
    db=db,
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    debug=True
)               

EchoRouter = SockJSRouter(EchoConnection, '/echo')
handlers.extend(EchoRouter.urls)

BodyRouter = SockJSRouter(BodyConnection, '/body')
handlers.extend(BodyRouter.urls)

application = tornado.web.Application(
    **settings)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.instance().start()


