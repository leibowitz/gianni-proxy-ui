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
from sockjs.tornado import SockJSRouter, SockJSConnection
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

        requestbody = nice_body(entry['request']['body'], requestheaders)
        responsebody = nice_body(entry['response']['body'], responseheaders)

        self.render("one.html", item=entry, requestheaders=requestheaders, responseheaders=responseheaders, requestbody=requestbody, responsebody=responsebody)

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

application = tornado.web.Application(
    **settings)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.instance().start()


