import tornado.ioloop
import tornado.web
from tornado import gen
from datetime import datetime
import motor
import json
import urlparse
from httpheader import parse_media_type
import pytz
import pymongo
import gridfs
import os
import time
from sockjs.tornado import SockJSRouter, SockJSConnection
from sockjs.tornado.periodic import Callback
from bson import json_util, objectid
from pygments import highlight
from pygments.lexers import JsonLexer, TextLexer, IniLexer, get_lexer_for_mimetype
from pygments.formatters import HtmlFormatter
import tempfile

class MySocket(SockJSConnection):
    def __init__(self, session):
        self.client = motor.MotorClient('mongodb://localhost:17017')
        self.db = self.client.proxyservice
        super(MySocket, self).__init__(session)


class EchoConnection(MySocket):

    @gen.coroutine
    def tail(self, origin=None):
        collection = self.db['log_logentry']
        dn = datetime.utcnow()
        query = {'date': {'$gte': dn} }
        if origin is not None:
            query['request.origin'] = origin
        #collection.find(query, tailable=True, await_data=True).tail(callback=self.on_new_requests)

        cursor = collection.find(query, tailable=True, await_data=True)
        while True:
            if not cursor.alive:
                now = datetime.datetime.utcnow()
                # While collection is empty, tailable cursor dies immediately
                yield gen.Task(loop.add_timeout, datetime.timedelta(seconds=1))
                cursor = collection.find(query, tailable=True, await_data=True)

            if (yield cursor.fetch_next):
                self.on_new_requests(cursor.next_object())

    def on_open(self, info):
        #self.tail()
        pass
        
    def on_message(self, msg):
        data = json.loads(msg)
        self.tail(origin=data['filterOrigin'])

    def on_new_requests(self, result):
        if result:
            msg = json.dumps(result, default=json_util.default)

            self.send(msg)

class BodyConnection(SockJSConnection):
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

        self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        self.pcb.start()

        # check for new data every second        
        #self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        #self.pcb = Callback(self.check_data)
        #self.pcb.start()
        #print "started"

    def check_data(self):
        #print "looking at data"
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
            data = nice_body(data, 'application/json')
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



def get_numbers(ret, error):
    pass

def nice_headers(headers):
    return {k: v[0] for k, v in headers.iteritems() if len(v) != 0}

def nice_body(body, content):
    if 'application/x-www-form-urlencoded' in content:
        params = "\n".join([k + "=" + v for k, v in dict(urlparse.parse_qsl(body)).iteritems()])
        return highlight(params, IniLexer(), HtmlFormatter(cssclass='codehilite'))
    if 'json' in content:
        return highlight(json.dumps(json.loads(body), indent=4), JsonLexer(), HtmlFormatter(cssclass='codehilite'))

    ctype, chars = parse_media_type(content, with_parameters=False)
    lex = get_lexer_for_mimetype('/'.join(filter(None, ctype)))
    #print lex
    return highlight(body, lex, HtmlFormatter(cssclass='codehilite'))
    #if headers != None and 'Content-Type' in headers and headers['Content-Type'].split(';')[0] == 'application/json':
    #    return highlight(body, JsonLexer(), HtmlFormatter())
    #    #return json.dumps(json.loads(body), indent=4)
    #return body

class MainHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db'].proxyservice['log_logentry']
        entries = yield collection.distinct("request.origin")
        self.render("index.html", items=entries)

class OriginHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, origin):
        #collection = self.settings['db']['log_logentry'].open_sync()
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.origin": origin}).sort([("$natural", pymongo.DESCENDING)]).limit(10)#.sort([('date', pymongo.DESCENDING)]).limit(10)
        res = cursor.to_list(10)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), EST=EST, host=None, origin=origin)

class ViewHandler(tornado.web.RequestHandler):

    def is_text_content(self, headers):
        #print headers
        if 'Content-Type' not in headers:
            return False
        return 'text' in headers['Content-Type'] or 'json' in headers['Content-Type'] or 'application/x-www-form-urlencoded' in headers['Content-Type']


    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        collection = self.settings['db'].proxyservice['log_logentry']
        fs = motor.MotorGridFS(self.settings['db'].proxyservice)

        try:
            oid = objectid.ObjectId(ident)
        except objectid.InvalidId as e:
            print e
            self.send_error(500)
            return
        #raise tornado.web.HTTPError(400)

        entry = yield motor.Op(collection.find_one, {'_id': oid})
        requestquery = nice_body(entry['request']['query'], 'application/x-www-form-urlencoded')
        requestheaders = nice_headers(entry['request']['headers'])
        responseheaders = nice_headers(entry['response']['headers'])
        requestbody = None
        responsebody = None
        #print entry['request']
        #print entry['response']
        if 'fileid' in entry['response'] and self.is_text_content(responseheaders):
            respfileid = entry['response']['fileid']
            filepath = os.path.join(tempfile.gettempdir(), "proxy-service", str(respfileid))
            #print filepath
            if not os.path.exists(filepath):
                try:
                    gridout = yield fs.get(respfileid)
                    if gridout:
                        responsebody = yield gridout.read()
                        responsebody = nice_body(responsebody, responseheaders['Content-Type'])
                except Exception as e:
                    print e
            else:
                ctype = 'application/json'
                lines = open(filepath).readlines()
                responsebody = '\n'.join(map(lambda line: nice_body(line, ctype), filter(None, map(lambda line: line.strip(), lines))))
                #responsebody = open(filepath).read()
                #ctype = responseheaders['Content-Type']
                #responsebody = nice_body(responsebody, ctype)


        if 'fileid' in entry['request'] and self.is_text_content(requestheaders):
            reqfileid = entry['request']['fileid']
            try:
                gridout = yield fs.get(reqfileid)
                if gridout:
                    requestbody = yield gridout.read()
                    requestbody = nice_body(requestbody, requestheaders['Content-Type'])
            except Exception as e:
                print e
        #requestbody = nice_body(entry['request']['body'], requestheaders)
        #responsebody = nice_body(entry['response']['body'], responseheaders)

        self.render("one.html", item=entry, 
                requestheaders=requestheaders, 
                responseheaders=responseheaders,
                requestbody=requestbody, 
                responsebody=responsebody,
                requestquery=requestquery, 
                origin=origin,
                host=host)

class HostHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.host": host}).sort([("$natural", pymongo.DESCENDING)]).limit(10)#.sort([('date', pymongo.DESCENDING)]).limit(10)
        res = cursor.to_list(10)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), EST=EST, host=host, origin=None)

class OriginHostHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, origin, host):
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.host": host, "request.origin": origin}).sort([("$natural", pymongo.DESCENDING)]).limit(10)#.sort([('date', pymongo.DESCENDING)]).limit(10)
        res = cursor.to_list(10)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), EST=EST, host=host, origin=origin)

db = motor.MotorClient('mongodb://localhost:17017', tz_aware=True)
EST = pytz.timezone('Europe/London')

handlers = [
    (r"/", MainHandler),
    (r"/origin/(?P<origin>[^\/]+)", OriginHandler),
    (r"/origin/(?P<origin>[^\/]+)/host/(?P<host>[^\/]+)", OriginHostHandler),
    (r"/item/(?P<ident>[^\/]+)", ViewHandler),
    (r"/domain/(?P<host>[^\/]+)", HostHandler),
]
    
settings = dict(
    handlers=handlers,
    static_path=os.path.join(os.path.dirname(__file__), 'static'),
    db=db,
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    debug=True
)               

EchoRouter = SockJSRouter(EchoConnection, '/listener')
handlers.extend(EchoRouter.urls)

BodyRouter = SockJSRouter(BodyConnection, '/body')
handlers.extend(BodyRouter.urls)

application = tornado.web.Application(
    **settings)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.instance().start()


