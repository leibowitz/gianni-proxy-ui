import json
from datetime import datetime, timedelta
from bson import json_util
from tornado import gen
from tornado.ioloop import IOLoop

from sock import BaseSockJSConnection
from shared import util

class ListenerConnection(BaseSockJSConnection):

    #is_connection_alive = True
    listeners = set()
    origin = None

    @staticmethod
    @gen.coroutine
    def tail(collection, origin=None):
        print 'Opening a global tailable cursor', collection
        dn = datetime.utcnow()
        query = {'date': {'$gte': dn} }
        if origin is not None:
            query['request.origin'] = origin
        #collection.find(query, tailable=True, await_data=True).tail(callback=self.on_new_requests)

        cursor = collection.find(query, tailable=True, await_data=True)
        while True:

            if not cursor.alive:
                now = datetime.utcnow()
                # While collection is empty, tailable cursor dies immediately
                yield gen.Task(IOLoop.current().add_timeout, timedelta(seconds=1))
                cursor = collection.find(query, tailable=True, await_data=True)

            if (yield cursor.fetch_next):
                ListenerConnection.on_new_requests(cursor.next_object())

    def on_open(self, info):
        self.listeners.add(self)
        #self.tail()
        pass

    def on_close(self):
        self.listeners.remove(self)
        #print 'close'
        #self.is_connection_alive = False
        
    def on_message(self, msg):
        data = json.loads(msg)
        if 'filterOrigin' in data:
            self.origin = data['filterOrigin']
            #self.tail(collection=self.db['log_logentry'])#, origin=data['filterOrigin'])
            #IOLoop.current().run_sync(lambda: self.tail(origin=data['filterOrigin']))
            

    @staticmethod
    def on_new_requests(result):
        if result and ListenerConnection.listeners:
            #for listener in ListenerConnection.listeners:
                #if listener.origin is not None and result['request']['origin'] == listener.origin:
                    #print 'sending to listener ', listener
                    # uuid is a binary field, change it to string
                    # before sending it via websocket
                    result['uuid'] = util.get_uuid(result)
                    result['request']['headers'] = ListenerConnection.s_nice_headers(result['request']['headers'])

                    msg = json.dumps(result, separators=(',', ':'), default=json_util.default)
                    #msg = proto.json_encode(result)
                    listener = next(iter(ListenerConnection.listeners))
                    #listener.send(msg)
                    #listener = ListenerConnection.listeners[0]
                    listener.broadcast(ListenerConnection.listeners, msg)
