from tornado import gen
import tornado.web
from bson.objectid import ObjectId

from shared import util

from base import BaseRequestHandler

class DocumentationHostHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):

        collection = self.settings['db'].proxyservice['documentation']
        req = {'request.host': {'$regex': '.*' + host + '.*'}}
        cursor = collection.find(req).sort([('request.path', 1), ('response.status', 1)])
        res = cursor.to_list(100)
        entries = yield res

        # Get a list of requests per endpoints
        tree = util.tree()

        for item in entries:
            if item['request']['path']:
                parts = filter(None, item['request']['path'].split('/'))
            else:
                parts = []
            o = tree[ item['request']['host'] ]
            for part in parts:
                o = o['children'][part]

            o['methods'][item['request']['method']][item['response']['status']] = item['_id']

        collection = self.settings['db'].proxyservice['docsettings']
        row = yield collection.find_one({'host': host})

        self.render("documentationhost.html", row=row, host=host, reqhost=host, entries=[], alltree=tree, render_tree=self.render_tree, render_document=self.render_document, currentpath=None, method=None, ObjectId=ObjectId)

    def render_tree(self, treehost, tree, currentpath=None, fullpath = '', method=None, hostsettings=None, host=None):
        return self.render_string("documentationtree.html", treehost=treehost, tree=tree, render_tree=self.render_tree, fullpath=fullpath+'/', currentpath=currentpath, currentmethod=method, hostsettings=hostsettings, host=host)

    def render_document(self, entries=[], method=None, host=None, reqhost=None):
        return self.render_string("documentationendpoint.html", entries=entries, method=method, host=host, reqhost=reqhost)
