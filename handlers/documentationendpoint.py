from tornado import gen
import tornado.web

from shared import util

from base import BaseRequestHandler

class DocumentationEndpointHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):
        path = self.get_argument('path', None)
        method = self.get_argument('method', None)

        collection = self.settings['db'].proxyservice['documentation']
        cursor = collection.find({'request.host': host, 'request.path': path, 'request.method': method}).sort([('response.status', 1)])
        res = cursor.to_list(100)
        entries = yield res

        self.render("documentationendpoint.html", items=entries, host=host)

