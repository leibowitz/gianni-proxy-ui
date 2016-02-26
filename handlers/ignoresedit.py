import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class IgnoresEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_ignores']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        host = self.get_argument('host', None)
        self.render("ignoresedit.html", entry=entry, host=host, tryagain=False)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        host = self.get_argument('host', None)
        active = self.get_argument('active', False)
        active = active if active is False else True

        collection = self.settings['db'].proxyservice['log_ignores']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        if not host:
            self.render("ignoresedit.html", entry=entry, host=host, tryagain=True)
            return

        collection = self.settings['db'].proxyservice['log_ignores']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'host': host
        })

        params = {}
        # this is required otherwise we will filter out this rule after the redirect
        if host:
            params['host'] = host
        self.redirect('/ignores?' + urllib.urlencode(params))

