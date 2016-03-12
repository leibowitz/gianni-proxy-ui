import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class OriginsAddHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        name = self.get_argument('name', None)
        origin = self.get_argument('origin', None)

        entry = None
        item = self.get_argument('item', None)
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})

        self.render("originsadd.html", tryagain=False, name=name, origin=origin, entry=entry)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        name = self.get_argument('name', None)
        origin = self.get_argument('origin', None)
        print name, origin

        entry = None
        
        if not name or not origin:
            self.render("originsadd.html", tryagain=True, name=name, origin=origin, entry=entry)
            return

        collection = self.settings['db'].proxyservice['origins']

        data = {
            'name': name,
            'origin': origin,
        }
        
        yield motor.Op(collection.insert, data)

        self.redirect('/origins')

