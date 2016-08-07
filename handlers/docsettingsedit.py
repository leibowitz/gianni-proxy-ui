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
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        groupindex = self.get_argument('groupindex', None)
        groupindex = int(groupindex) if groupindex is not None else None

        collection = self.settings['db'].proxyservice['docsettings']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            if not host:
                raise tornado.web.HTTPError(404)
            else:
                entry = {'_id': self.get_id(ident), 'host': host, 'active': False}

        self.render("docsettingsedit.html", entry=entry, item=item, host=host, groupindex=groupindex, tryagain=False)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        groupindex = self.get_argument('groupindex', None)
        groupindex = int(groupindex) if groupindex is not None else None
        active = self.get_argument('active', False)
        active = active if active is False else True

        collection = self.settings['db'].proxyservice['docsettings']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        if not host:
            if not entry:
                entry = {'_id': self.get_id(ident), 'host': host, 'active': active, 'groupindex': groupindex}
            self.render("docsettingsedit.html", entry=entry, item=item, host=host, groupindex=groupindex, tryagain=True)
            return

        collection = self.settings['db'].proxyservice['docsettings']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'host': host,
            'groupindex': groupindex,
        }, upsert=True)


        self.redirect('/documentation/host/' + host)

