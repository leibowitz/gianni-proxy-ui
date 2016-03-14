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

class DocumentationViewHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        collection = self.settings['db'].proxyservice['documentation']
        resbody = None

        try:
            oid = objectid.ObjectId(ident)
        except objectid.InvalidId as e:
            print e
            self.send_error(500)
            return
        #raise tornado.web.HTTPError(400)

        entry = yield motor.Op(collection.find_one, {'_id': oid})
        if not entry:
            raise tornado.web.HTTPError(404)

        requestquery = util.nice_body(entry['request']['query'], 'application/x-www-form-urlencoded')
        #print entry['request']['headers']
        requestheaders = self.nice_headers(entry['request']['headers'])
        responseheaders = self.nice_headers(entry['response']['headers'])
        requestbody = None
        responsebody = None

        if 'fileid' in entry['response']:
            resbody, ctype = yield self.get_gridfs_body(entry['response']['fileid'], responseheaders)
            responsebody = self.get_formatted_body(resbody, ctype)
            
        if 'fileid' in entry['request']:
            reqbody, ctype = yield self.get_gridfs_body(entry['request']['fileid'], requestheaders)
            requestbody = self.get_formatted_body(reqbody, ctype)

        for key, value in requestheaders.iteritems():
            if key == 'Cookie':
                requestheaders[key] = util.nice_body(value, 'application/x-www-form-urlencoded')

        cmd = yield self.get_curl_cmd(entry, reqbody)

        fmt = util.get_format(util.get_content_type(self.nice_headers(responseheaders))) if responseheaders else None

        self.render("one.html", 
                item=entry, 
                body=resbody,
                fmt=fmt,
                cmd=cmd,
                requestheaders=requestheaders, 
                responseheaders=responseheaders,
                requestbody=requestbody, 
                responsebody=responsebody,
                requestquery=requestquery, 
                finished=True,
                socketuuid=None,
                origin=origin,
                host=host,
                show_save=False,
                show_resend=False)

