import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class DocSettingsAddHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        entry = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})
            if entry:
                host = entry['request']['host']

        self.render("docsettingsadd.html", tryagain=False, item=item, host=host, entry=entry)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        
        if not host:
            self.render("docsettingsadd.html", entry=None, item=item, host=host, tryagain=True)
            return

        collection = self.settings['db'].proxyservice['docsettings']

        yield motor.Op(collection.insert, {
            'active': True,
            'host': host
        })

        self.redirect('/docsettings')
