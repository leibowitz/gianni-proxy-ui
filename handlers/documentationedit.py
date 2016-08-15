import re
import os
import tempfile
from bson import objectid
from tornado import gen
import tornado.web
import motor
import requests
from pygments import highlight
from pygments.lexers import BashLexer
from pygments.formatters import HtmlFormatter

from base import BaseRequestHandler
from shared import util

class DocumentationEditHandler(BaseRequestHandler):


    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['documentation']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        reqheaders = entry['request']['headers'] if 'request' in entry and 'headers' in entry['request'] else {}
        respheaders = entry['response']['headers'] if 'response' in entry and 'headers' in entry['response'] else {}

        if 'fileid' in entry['response']:
            resbody, ctype = yield self.get_gridfs_body(entry['response']['fileid'], respheaders)
            entry['response']['body'] = resbody
            
        if 'fileid' in entry['request']:
            reqbody, ctype = yield self.get_gridfs_body(entry['request']['fileid'], reqheaders)
            entry['request']['body'] = reqbody

        reqfmt = util.get_format(util.get_content_type(self.nice_headers(reqheaders))) if reqheaders else None
        respfmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None
        scheme = entry['request']['scheme'] if 'scheme' in entry['request'] else 'http'

        self.render("documentationedit.html", entry=entry, tryagain=False, reqheaders=reqheaders, respheaders=respheaders, respfmt=respfmt, reqfmt=reqfmt, scheme=scheme)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):

        host = util.cleanarg(self.get_argument('host'), False)
        scheme = util.cleanarg(self.get_argument('scheme'), False)
        path = util.cleanarg(self.get_argument('path'), False)
        query = util.cleanarg(self.get_argument('query'), False)
        status = util.cleanarg(self.get_argument('status'), False)
        method = util.cleanarg(self.get_argument('method'), False)
        respbody = util.cleanarg(self.get_argument('respbody'), False)
        reqbody = util.cleanarg(self.get_argument('reqbody'), False)
        reqheaders = self.get_submitted_headers('reqheader')
        respheaders = self.get_submitted_headers('respheader')

        collection = self.settings['db'].proxyservice['documentation']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        reqfmt = util.get_format(util.get_content_type(self.nice_headers(reqheaders))) if reqheaders else None
        respfmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None

        if not host and not path and not query and not status:
            self.render("documentationedit.html", entry=entry, tryagain=True, reqheaders=reqheaders, respheaders=respheaders, respfmt=respfmt, reqfmt=reqfmt, scheme=scheme)
            return

        # default stuff
        if not scheme:
            scheme = 'http'
        if not status:
            status = 200
        if not method:
            method = 'GET'

        item = {
            'request': {
                'scheme': scheme,
                'host': host,
                'path': path,
                'query': query,
                'method': method,
                'body': reqbody,
                'headers': reqheaders,
            },
            'response': {
                'body': respbody,
                'headers': respheaders,
                'status': int(status),
            }
        }

        up = {
                'request.host': host,
                'request.scheme': scheme,
                'request.path': path,
                'request.query': query,
                'request.method': method,
                'request.body': reqbody,
                'request.headers': reqheaders,
                'response.body': respbody,
                'response.headers': respheaders,
                'response.status': int(status),
        }

        yield collection.update({'_id': self.get_id(ident)}, {'$set': up})
        item['_id'] = ident

        self.render("documentationedit.html", entry=item, tryagain=False, reqheaders=reqheaders, respheaders=respheaders, respfmt=respfmt, reqfmt=reqfmt, scheme=scheme)

