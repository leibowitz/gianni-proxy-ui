from tornado import gen
import tornado.web

from base import BaseRequestHandler

class DocSettingsHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db'].proxyservice['docsettings']
        cursor = collection.find({}).sort([('request.host', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("docsettings.html", items=entries)

    def post(self):
        collection = self.settings['db'].proxyservice['docsettings']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})

        if 'X-Requested-With' in self.request.headers and self.request.headers['X-Requested-With'] == "XMLHttpRequest":
            return

        self.redirect('/docsettings')

