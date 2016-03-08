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
        paths = self.get_submitted_array('paths')

        entry = None
        item = self.get_argument('item', None)
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})

        self.render("ignoresadd.html", tryagain=False, host=host, paths=paths, entry=entry)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        host = self.get_argument('host', None)
        paths = self.get_submitted_array('paths')
        entry = None
        
        if not host:
            self.render("ignoresadd.html", tryagain=True, host=host, paths=paths, entry=entry)
            return

        collection = self.settings['db'].proxyservice['log_ignores']

        data = {
            'active': True,
            'host': host,
        }
        
        if len(paths) != 0:
            data['paths'] = paths

        yield motor.Op(collection.insert, data)

        params = {}
        # this is required otherwise we will filter out this rule after the redirect
        if host:
            params['host'] = host
        self.redirect('/ignores?' + urllib.urlencode(params))

