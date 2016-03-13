from tornado import gen
import tornado.web

from base import BaseRequestHandler

class DocumentationHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db'].proxyservice['documentation']
        cursor = collection.find({}).sort([('request.host', 1), ('request.path', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("documentation.html", items=entries)

