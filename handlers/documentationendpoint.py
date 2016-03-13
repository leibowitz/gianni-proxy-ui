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
        cursor = collection.find({'request.host': host}).sort([('request.path', 1)])
        res = cursor.to_list(100)
        entries = yield res

        # Get a list of requests per endpoints
        tree = util.tree()

        for item in entries:
            parts = filter(None, item['request']['path'].split('/'))
            o = tree
            for part in parts:
                o = o['children'][part]

            o['methods'][item['request']['method']][item['response']['status']] = item['_id']

        entry = yield collection.find_one({'request.host': host, 'request.path': path, 'request.method': method})

        self.render("documentationhost.html", host=host, entry=entry, tree=tree, render_tree=self.render_tree, render_document=self.render_document)

    def render_tree(self, host, tree, fullpath = ''):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/')

    def render_document(self, entry):
        return self.render_string("documentationendpoint.html", entry=entry)
