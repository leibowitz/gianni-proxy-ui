from tornado import gen
import tornado.web
import skinfer
#import genson
import json
import urlparse
import urllib
from bson.objectid import ObjectId

from shared import util

from base import BaseRequestHandler

class DocumentationEndpointHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, reqhost):
        host = self.get_argument('host', reqhost)
        path = self.get_argument('path', None)
        method = self.get_argument('method', None)

        collection = self.settings['db'].proxyservice['documentation']

        req = {'request.host': {'$regex': '.*' + host + '.*'}}
        cursor = collection.find(req).sort([('request.path', 1), ('response.status', 1)])
        res = cursor.to_list(100)
        endpoints = yield res

        # Get a list of requests per endpoints
        tree = util.tree()

        for item in endpoints:
            parts = filter(None, item['request']['path'].split('/'))
            o = tree[ item['request']['host'] ]
            for part in parts:
                o = o['children'][part]

            o['methods'][item['request']['method']][item['response']['status']] = item['_id']

        req['request.path'] = path
        req['request.method'] = method

        if len(req) > 1:
            req = {'$and': map(lambda x: {x[0]: x[1]}, req.iteritems())}
        entries = yield collection.find(req).sort([('response.status', 1)]).to_list(100)

        for k, entry in enumerate(entries):
            entries[k]['request']['headers'] = self.nice_headers(entry['request']['headers'])
            entries[k]['response']['headers'] = self.nice_headers(entry['response']['headers'])

            if entry['request']['query']:
                entries[k]['request']['query'] = urlparse.parse_qsl(entry['request']['query'], keep_blank_values=True)

            reqbody = None
            if 'body' in entries[k]['request'] and entries[k]['request']['body']:
                reqbody = entries[k]['request']['body']
            elif 'request' in entry and 'fileid' in entry['request']:
                reqbody, entries[k]['request']['content-type'] = yield self.get_gridfs_body(entry['request']['fileid'], entry['request']['headers'])

            if 'content-type' in entries[k]['request'] and entries[k]['request']['content-type'] == 'application/x-www-form-urlencoded' and reqbody:
                entries[k]['request']['body'] = urlparse.parse_qsl(reqbody, keep_blank_values=True)

            if 'response' in entry:
                if 'fileid' in entry['response']:
                    entries[k]['response']['body'], entries[k]['response']['content-type'] = yield self.get_gridfs_body(entry['response']['fileid'], entry['response']['headers'])
                elif 'body' in entry['response']:
                    entry['response']['content-type'] = util.get_content_type(entry['response']['headers'])

                if util.get_format(entry['response']['content-type']) == 'json':
                    entries[k]['response']['schema'] = skinfer.generate_schema(json.loads(entry['response']['body']))
                    #genson.Schema().add_object(json.loads(resbody)).to_dict()
                
                entries[k]['response']['body'] = self.get_formatted_body(entries[k]['response']['body'], entries[k]['response']['content-type'], 'break-all')

        collection = self.settings['db'].proxyservice['docsettings']
        row = yield collection.find_one({'host': host})

        self.render("documentationhost.html", host=host, reqhost=reqhost, entries=entries, alltree=tree, render_tree=self.render_tree, render_document=self.render_document, currentpath=path, method=method, row=row, ObjectId=ObjectId)

    def render_tree(self, treehost, tree, currentpath=None, fullpath = '', method=None, hostsettings=None, host=None):
        return self.render_string("documentationtree.html", treehost=treehost, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath, currentmethod=method, hostsettings=hostsettings, host=host)

    def render_document(self, entries=[], method=None, host=None, reqhost=None):
        return self.render_string("documentationendpoint.html", entries=entries, render_schema=self.render_schema, method=method, host=host, reqhost=reqhost)

    def render_schema(self, schema):
        return self.render_string("documentationschema.html", schema=schema, render_schema=self.render_schema)
    
    @gen.engine
    def post(self, host):
        if not 'X-Requested-With' in self.request.headers or self.request.headers['X-Requested-With'] != "XMLHttpRequest":
            return

        key = self.get_argument("key", None)
        ident = self.get_argument("ident", None)
        part = self.get_argument("type", None)
        action = self.get_argument("action", None)
        if action == "delete":
            collection = self.settings['db'].proxyservice['documentation']
            if 'header' in part:
                if part == "reqheader":
                    field = "request.headers." + key
                elif part == "resheader":
                    field = "response.headers." + key
                collection.update({'_id': self.get_id(ident)}, {'$unset': {field: ""}})
            else:
                entry = yield collection.find_one({'_id': self.get_id(ident)})
                if not entry:
                    return
                if part == "query":
                    query = urlparse.parse_qs(entry['request']['query'], keep_blank_values=True)
                    del query[key]
                    query = urllib.urlencode(query, doseq=True)
                    collection.update({'_id': self.get_id(ident)}, {'$set': {'request.query': query}})
                    pass
                elif part == "reqbody":
                    if 'body' in entry['request'] and entry['request']['body']:
                        body = entry['request']['body']
                        ctype = entry['request']['content-type']
                    else:
                        body, ctype = yield self.get_gridfs_body(entry['request']['fileid'], entry['request']['headers'])
                    body = urlparse.parse_qs(body, keep_blank_values=True)
                    del body[key]
                    body = urllib.urlencode(body, doseq=True)
                    collection.update({'_id': self.get_id(ident)}, {'$set': {'request.body': body, 'request.content-type': ctype}})
                    pass
                return
