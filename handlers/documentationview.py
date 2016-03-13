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
        body = None
        fs = motor.MotorGridFS(self.settings['db'].proxyservice)

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

        socketuuid = util.get_uuid(entry)

        # consider the response finished
        finished = True

        #print entry['request']
        #print entry['response']
        if 'fileid' in entry['response']:

            respfileid = entry['response']['fileid']
            filepath = os.path.join(tempfile.gettempdir(), "proxy-service", str(respfileid))
            #print filepath
            
            response_mime_type = util.get_content_type(requests.structures.CaseInsensitiveDict(responseheaders))
            if not os.path.exists(filepath):
                body = yield util.get_gridfs_content(fs, respfileid)
                if body:
                    if not response_mime_type:
                        pass
                    elif 'text/plain' in response_mime_type:
                        responsebody = util.get_body_non_empty_lines(body.strip().split("\n"))
                    elif self.is_text_content(response_mime_type):
                        responsebody = util.nice_body(body, response_mime_type)
                    elif 'image' in response_mime_type:
                        responsebody = util.raw_image_html(body, response_mime_type)
            else:
                if not response_mime_type:
                    pass
                elif 'text/plain' in response_mime_type:
                    lines = open(filepath).readlines()
                    responsebody = util.get_body_non_empty_lines(lines)
                elif self.is_text_content(response_mime_type):
                    content = open(filepath).read()
                    responsebody = util.nice_body(content, response_mime_type)
                elif 'image' in response_mime_type:
                    responsebody = util.raw_image_html(content, response_mime_type)
                # request seems to be still open
                finished = False
                #responsebody = open(filepath).read()
                #ctype = responseheaders['Content-Type']
                #responsebody = util.nice_body(responsebody, ctype)

        cmd = 'curl' 
        cmd = cmd + ' -X ' + entry['request']['method']
        for key, value in requestheaders.iteritems():
            cmd = cmd + ' -H ' + util.QuoteForPOSIX(key + ': ' + value)
            if key == 'Cookie':
                requestheaders[key] = util.nice_body(value, 'application/x-www-form-urlencoded')

        if 'fileid' in entry['request'] and not self.has_binary_content(requestheaders):
            requestbody = yield util.get_gridfs_content(fs, entry['request']['fileid'])
            if requestbody:
                ctype = util.get_content_type(requestheaders)
                # default to x-www-form-urlencoded
                ctype = ctype if ctype is not None else 'application/x-www-form-urlencoded'
                #if self.has_text_content(requestheaders)

                if util.get_content_encoding(requestheaders) == 'gzip':
                    requestbody = util.ungzip(requestbody)

                    ctype = None

                bodyparam = util.QuoteForPOSIX(requestbody)
                try:
                    cmd = cmd + ' -d ' + bodyparam
                except Exception as e:
                    print e

                requestbody = util.nice_body(requestbody, ctype)
        #requestbody = util.nice_body(entry['request']['body'], requestheaders)
        #responsebody = util.nice_body(entry['response']['body'], responseheaders)

        cmd = cmd + ' ' + util.QuoteForPOSIX(entry['request']['url'])

        if entry['request']['method'] == 'GET':
            collection = self.settings['db'].proxyservice['log_messages']
            messages = yield collection.find({"host": entry['request']['host']}).sort('_id').to_list(100)
            for msg in messages:
                msg['message'] = re.escape(msg['message'])
        else:
            messages = {}

        # colorise bash command
        cmd = highlight(cmd, BashLexer(), HtmlFormatter(cssclass='codehilite curl'))
        fmt = util.get_format(util.get_content_type(self.nice_headers(responseheaders))) if responseheaders else None

        self.render("one.html", 
                item=entry, 
                body=body,
                fmt=fmt,
                cmd=cmd,
                messages=messages,
                requestheaders=requestheaders, 
                responseheaders=responseheaders,
                requestbody=requestbody, 
                responsebody=responsebody,
                requestquery=requestquery, 
                finished=finished,
                socketuuid=socketuuid,
                origin=origin,
                host=host,
                show_save=False,
                show_resend=False)
