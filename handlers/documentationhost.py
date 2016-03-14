from tornado import gen
import tornado.web

from shared import util

from base import BaseRequestHandler

class DocumentationHostHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):

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

        self.render("documentationhost.html", host=host, entry=None, entries=[], tree=tree, render_tree=self.render_tree, render_document=self.render_document, reqbody=None, resbody=None, requestheaders={}, responseheaders={}, reqtype=None, restype=None, currentpath=None, method=None)

    def render_tree(self, host, tree, currentpath=None, fullpath = '', method=None):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath, currentmethod=method)

    def render_document(self, entry, entries=[]):
        return self.render_string("documentationendpoint.html", entry=entry, entries=entries)
