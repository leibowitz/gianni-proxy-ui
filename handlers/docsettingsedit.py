import urllib
from tornado import gen
import tornado.web
import motor
import bson

from base import BaseRequestHandler
from shared import util

class DocSettingsEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)

        collection = self.settings['db'].proxyservice['docsettings']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            entry = {'active': False, 'host': host, '_id': bson.objectid.ObjectId()} # active should probably be whatever is the default
            #raise tornado.web.HTTPError(404)

        self.render("docsettingsedit.html", entry=entry, item=item, host=host, tryagain=False)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        active = self.get_argument('active', False)
        active = active if active is False else True

        collection = self.settings['db'].proxyservice['docsettings']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        if not host:
            self.render("docsettingsedit.html", entry=entry, item=item, host=host, tryagain=True)
            return

        collection = self.settings['db'].proxyservice['docsettings']
        collection.update({'_id': self.get_id(ident)}, {'$set': {'active': active, 'host': host}}, upsert=True)

        self.redirect('/docsettings')

