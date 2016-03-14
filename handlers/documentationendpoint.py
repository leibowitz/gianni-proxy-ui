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

        for k, entry in enumerate(entries):
            entries[k]['request']['headers'] = self.nice_headers(entry['request']['headers'])
            entries[k]['response']['headers'] = self.nice_headers(entry['response']['headers'])

            if entry['request']['query']:
                entries[k]['request']['query'] = urlparse.parse_qsl(entry['request']['query'], keep_blank_values=True)

            if 'request' in entry and 'fileid' in entry['request']:
                reqbody, entries[k]['request']['content-type'] = yield self.get_gridfs_body(entry['request']['fileid'], entry['request']['headers'])
                if entries[k]['request']['content-type'] == 'application/x-www-form-urlencoded':
                    entries[k]['request']['body'] = urlparse.parse_qsl(reqbody, keep_blank_values=True)

            if 'response' in entry and 'fileid' in entry['response']:
                entry['response']['body'], entries[k]['response']['content-type'] = yield self.get_gridfs_body(entry['response']['fileid'], entry['response']['headers'])

                if util.get_format(entry['response']['content-type']) == 'json':
                    entries[k]['response']['schema'] = skinfer.generate_schema(json.loads(entry['response']['body']))
                    #genson.Schema().add_object(json.loads(resbody)).to_dict()

        self.render("documentationhost.html", host=host, entries=entries, tree=tree, render_tree=self.render_tree, render_document=self.render_document, currentpath=path, method=method)

    def render_tree(self, host, tree, currentpath=None, fullpath = '', method=None):
        return self.render_string("documentationtree.html", host=host, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath, currentmethod=method)

    def render_document(self, entries, method):
        entry = None
        if len(entries) != 0:
            entry = entries[0]
        return self.render_string("documentationendpoint.html", entries=entries, render_schema=self.render_schema, method=method, entry=entry)

    def render_schema(self, schema):
        return self.render_string("documentationschema.html", schema=schema, render_schema=self.render_schema)
