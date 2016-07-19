from tornado import gen
import tornado.web

from shared import util

from base import BaseRequestHandler

class DocumentationHostHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):

        collection = self.settings['db'].proxyservice['documentation']
        cursor = collection.find({'request.host': host}).sort([('request.path', 1), ('response.status', 1)])
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

        collection = self.settings['db'].proxyservice['docsettings']
        row = yield collection.find_one({'host': host})

        self.render("documentationhost.html", row=row, host=host, entries=[], tree=tree, render_tree=self.render_tree, render_document=self.render_document, currentpath=None, method=None)

    def render_tree(self, host, tree, currentpath=None, fullpath = '', method=None):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath, currentmethod=method)

    def render_document(self, entries=[], method=None, host=None):
        return self.render_string("documentationendpoint.html", entries=entries, method=method, host=host)
