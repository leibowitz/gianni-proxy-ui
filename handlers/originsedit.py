import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class OriginsEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['origins']
        entry = yield motor.Op(collection.find_one, {'origin': ident})

        name = entry['name'] if entry and 'name' in entry else None
        origin = entry['origin'] if entry and 'origin' in entry else ident

        self.render("originsedit.html", entry=entry, name=name, origin=origin, tryagain=False)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        name = self.get_argument('name', None)
        origin = self.get_argument('origin', None)
        active = self.get_argument('active', False)

        collection = self.settings['db'].proxyservice['origins']
        entry = yield motor.Op(collection.find_one, {'origin': ident})

        if not name or not origin:
            self.render("originsedit.html", entry=entry, name=name, origin=origin, tryagain=True)
            return

        data = {
            'filterAll': not active,
            'origin': origin,
            'name': name,
        }
        
        collection.update({'origin': ident}, data, upsert=True)

        self.redirect('/origins')

