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

        requestheaders = {}
        responseheaders = {}
        reqbody = None
        resbody = None

        if entry:
            requestheaders = self.nice_headers(entry['request']['headers'])
            responseheaders = self.nice_headers(entry['response']['headers'])

            if 'request' in entry and 'fileid' in entry['request']:
                reqbody, ctype = yield self.get_gridfs_body(entry['request']['fileid'], requestheaders)

            if 'response' in entry and 'fileid' in entry['response']:
                resbody, ctype = yield self.get_gridfs_body(entry['response']['fileid'], responseheaders)

        self.render("documentationhost.html", host=host, entry=entry, tree=tree, render_tree=self.render_tree, render_document=self.render_document, requestheaders=requestheaders, responseheaders=responseheaders, reqbody=reqbody, resbody=resbody)

    def render_tree(self, host, tree, fullpath = ''):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/')

    def render_document(self, entry, requestheaders, responseheaders, reqbody, resbody):
        return self.render_string("documentationendpoint.html", entry=entry, requestheaders=requestheaders, responseheaders=responseheaders, resbody=resbody, reqbody=reqbody)
