import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class DocSettingsEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['docsettings']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
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
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'host': host,
        })

        self.redirect('/docsettings')

