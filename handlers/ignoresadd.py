import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class IgnoresAddHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        host = self.get_argument('host', None)

        self.render("ignoresadd.html", tryagain=False, host=host)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        host = self.get_argument('host', None)
        
        if not host:
            self.render("ignoresadd.html", tryagain=True, host=host)
            return

        collection = self.settings['db'].proxyservice['log_ignores']

        yield motor.Op(collection.insert, {
            'active': True,
            'host': host
        })

        params = {}
        # this is required otherwise we will filter out this rule after the redirect
        if host:
            params['host'] = host
        self.redirect('/ignores?' + urllib.urlencode(params))

