from tornado import gen
import tornado.web
import skinfer
import genson
import json
import urlparse

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
        endpoints = yield res

        # Get a list of requests per endpoints
        tree = util.tree()

        for item in endpoints:
            parts = filter(None, item['request']['path'].split('/'))
            o = tree
            for part in parts:
                o = o['children'][part]

            o['methods'][item['request']['method']][item['response']['status']] = item['_id']

        entries = yield collection.find({'request.host': host, 'request.path': path, 'request.method': method}).to_list(100)

        requestheaders = {}
        responseheaders = {}
        reqbody = None
        resbody = None
        reqtype = None
        restype = None
        reqfields = {}

        entry = None
        if len(entries) != 0:
            entry = entries[0]
            requestheaders = self.nice_headers(entry['request']['headers'])
            responseheaders = self.nice_headers(entry['response']['headers'])

            if 'request' in entry and 'fileid' in entry['request']:
                reqbody, reqtype = yield self.get_gridfs_body(entry['request']['fileid'], requestheaders)
                if reqtype == 'application/x-www-form-urlencoded':
                    reqfields = urlparse.parse_qsl(reqbody, keep_blank_values=True)

            if 'response' in entry and 'fileid' in entry['response']:
                resbody, restype = yield self.get_gridfs_body(entry['response']['fileid'], responseheaders)

        self.render("documentationhost.html", host=host, entries=entries, entry=entry, tree=tree, render_tree=self.render_tree, render_document=self.render_document, requestheaders=requestheaders, responseheaders=responseheaders, reqbody=reqbody, resbody=resbody, reqtype=reqtype, restype=restype, reqfields=reqfields, currentpath=path)

    def render_tree(self, host, tree, currentpath=None, fullpath = ''):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath)

    def render_document(self, entry, entries, requestheaders, responseheaders, reqbody, resbody, reqtype, restype, reqfields):
        schema = None
        if util.get_format(restype) == 'json':
            schema = skinfer.generate_schema(json.loads(resbody))
            #print genson.Schema().add_object(json.loads(resbody)).to_dict()
        
        query = urlparse.parse_qsl(entry['request']['query'], keep_blank_values=True)
        return self.render_string("documentationendpoint.html", entry=entry, entries=entries, requestheaders=requestheaders, responseheaders=responseheaders, resbody=resbody, reqbody=reqbody, schema=schema, query=query, render_schema=self.render_schema, reqfields=reqfields)

    def render_schema(self, schema):
        return self.render_string("documentationschema.html", schema=schema, render_schema=self.render_schema)
