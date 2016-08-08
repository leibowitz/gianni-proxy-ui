from tornado import gen
import tornado.web
from tornado.ioloop import IOLoop
from bson import objectid
import urlparse
import collections
from markdown import Markdown

from shared import util

from base import BaseRequestHandler

class DocumentationApiHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):

        raw = True if self.get_argument('raw', False) else False
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

        items = {}
        for item in entries:
            if 'fileid' in item['request']:
                item['request']['body'] = yield self.gridfs_body(item['request']['fileid'])
            if 'fileid' in item['response']:
                item['response']['body'] = yield self.gridfs_body(item['response']['fileid'])

            item['request']['headers'] = self.filter_headers(item['request']['headers'])
            item['response']['headers'] = self.filter_headers(item['response']['headers'])

            items[str(item['_id'])] = item

        documentation = self.render_api_blueprint(host, tree, items)
        m = Markdown(extensions=["plueprint"])
        m.set_output_format("apiblueprint")
        api = m.convert("""
FORMAT: 1A

# The Simplest API
This is one of the simplest APIs written in the **API Blueprint**.

# /message

## GET
+ Response 200 (text/plain)

        Hello World!
""")

        if raw:
            self.write(documentation)
            self.finish()
            return

        self.render("documentationapi.html", host=host, entries=items, tree=tree, documentation=documentation)


    def render_api_blueprint(self, host=None, tree=[], entries=[]):
        return self.render_string("documentationapiblueprint.html", host=host, entries=entries, tree=tree, render_api_tree=self.render_api_tree)


    def filter_headers(self, hdrs):
            headers = {}
            for key, value in hdrs.iteritems():
                if key in ['X-Amz-Cf-Id', 'Connection', 'Transfer-Encoding', 'Cache-Control', 'User-Agent', 'Content-Length', 'Accept-Encoding', 'X-Cache', 'Via']:
                    continue
                if key not in headers:
                    headers[key] = []
                headers[key] = value
            
            return headers

    def render_api_tree(self, host=None, tree=[], entries=[], fullpath=''):
        return self.render_string("documentationapitree.html", entries=entries, tree=tree, host=host, fullpath=fullpath, render_api_tree=self.render_api_tree, render_api_document=self.render_api_document)

    
    def render_api_document(self, doc): 
        if 'query' in doc and doc['query']:
            parsedbody = urlparse.parse_qsl(doc['query'], keep_blank_values=True)
            args = collections.OrderedDict(sorted(parsedbody))
            if len(args) != 0:
            #params = "\n".join([k.strip() + "=" + v for k, v in args.iteritems()])
                doc['params'] = args
        #print doc
        #if 'headers' in doc and 'Content-Type' in doc['headers'] and 'application/x-www-form-urlencoded' in doc['headers']['Content-Type']:
        #    print doc['body']
        #    del doc['body']
        #    doc['params'] = {}
        return self.render_string("documentationapiendpoint.html", entry=doc)

