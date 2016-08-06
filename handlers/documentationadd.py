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

class DocumentationAddHandler(BaseRequestHandler):


    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        self.render("documentationadd.html", tryagain=False, host=None, path=None, query=None, status=None, method=None, respbody=None, reqbody=None, reqheaders=None, respheaders=None, reqfmt=None, respfmt=None, scheme=None)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self):

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

        reqfmt = util.get_format(util.get_content_type(self.nice_headers(reqheaders))) if reqheaders else None
        respfmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None

        if not host and not path and not query and not status:
            self.render("documentationadd.html", tryagain=True, host=host, path=path, query=query, status=status, method=method, respbody=respbody, reqbody=reqbody, reqheaders=reqheaders, respheaders=respheaders, reqfmt=reqfmt, respfmt=respfmt, scheme=scheme)
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

        yield collection.insert(item)

        self.redirect('/documentation')

