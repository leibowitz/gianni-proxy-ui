from tornado import gen
import tornado.web

from base import BaseRequestHandler

class OriginsHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        collection = self.settings['db'].proxyservice['origins']
        cursor = collection.find({}).sort([('name', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("origins.html", items=entries)

    def post(self):
        collection = self.settings['db'].proxyservice['origins']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'origin': ident})

        if 'X-Requested-With' in self.request.headers and self.request.headers['X-Requested-With'] == "XMLHttpRequest":
            return

        self.show_list()

