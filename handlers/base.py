from tornado.web import RequestHandler
from tornado import gen
import motor
from bson import objectid
from collections import defaultdict
import pytz

from shared import util

class BaseRequestHandler(RequestHandler):
    TZ = pytz.timezone('Europe/London')

    def get_id(self, ident):
        try:
            oid = objectid.ObjectId(ident)
        except objectid.InvalidId as e:
            print e
            self.send_error(500)
            return None
        return oid
    
    def get_submitted_array(self, fieldname):
        return filter(None, self.get_arguments(fieldname+'[]'))

    def get_submitted_headers(self, fieldname):

        headers = defaultdict(list)
        x = 0

        row = self.get_arguments(fieldname+'[' + str(x) + '][]')

        while len(row) > 1:

            if len(row[0].strip()) != 0:
                headers[ row[0] ].append(row[1])

            x += 1
            row = self.get_arguments(fieldname+'[' + str(x) + '][]')

        return headers

    @staticmethod
    def s_nice_headers(headers = {}):
        if not headers:
            return {}
        return dict(map(lambda (k,v): (k, v[0] if type(v) is list else v), headers.iteritems()))
    
    def nice_headers(self, headers):
        return BaseRequestHandler.s_nice_headers(headers)
    
    @staticmethod
    def s_dict_headers(headers = {}):
        if not headers:
            return {}
        return dict(map(lambda (k,v): (k, [v] if type(v) is not list else v), headers.iteritems()))
    
    def dict_headers(self, headers):
        return BaseRequestHandler.s_dict_headers(headers)

    def has_text_content(self, headers):
        #print headers
        if 'Content-Type' not in headers:
            return False
        return self.is_text_content(headers['Content-Type'])

    def is_text_content(self, mime):
        if not mime:
            return False
        return 'text' in mime \
               or 'json' in mime \
               or 'x-www-form-urlencoded' in mime \
               or 'javascript' in mime
    
    def has_binary_content(self, headers):
        #assume not binary if missing headers
        if 'Content-Type' not in headers:
            return False

        if self.is_text_content(headers['Content-Type']):
            return False

        if self.is_binary_content(headers['Content-Type']):
            return True

        return True
        # assume binary in all other cases
    
    def is_binary_content(self, mime):
        if not mime:
            return False
        if 'binary' in mime or 'image' in mime or 'pdf' in mime:
            return True

        return False

    def get_partial_content_body(self, filepath, mime_type, cssclass=None):
        if not mime_type:
            return None
        elif 'text/plain' in mime_type:
            lines = open(filepath).readlines()
            return util.get_body_non_empty_lines(lines)
        elif self.is_text_content(mime_type):
            content = open(filepath).read()
            return util.nice_body(content, mime_type, cssclass)
        elif 'image' in mime_type:
            content = open(filepath).read()
            return util.raw_image_html(content, mime_type)
        return None

    def get_formatted_body(self, body, mime_type=None, cssclass=None):
        if not mime_type:
            return None
        elif 'text/plain' in mime_type:
            return util.get_body_non_empty_lines(body.strip().split("\n"))
        elif self.is_text_content(mime_type):
            return util.nice_body(body, mime_type, cssclass)
        elif 'image' in mime_type:
            return util.raw_image_html(body, mime_type)
        return None
        

    @gen.coroutine
    def get_gridfs_body(self, fileid, headers):
        fs = motor.MotorGridFS(self.settings['db'].proxyservice)
        body = yield util.get_gridfs_content(fs, fileid)
        raise gen.Return(util.get_uncompressed_body(self.nice_headers(headers), body))
    
    @gen.coroutine
    def gridfs_body(self, fileid):
        fs = motor.MotorGridFS(self.settings['db'].proxyservice)
        data = None
        gridout = yield fs.get(fileid)
        if gridout:
            data = yield gridout.read()
        raise gen.Return(data)
    
    @gen.coroutine
    def get_curl_cmd(self, entry, body = None):
        cmd = 'curl' 
        cmd = cmd + ' -X ' + entry['request']['method']

        requestheaders = self.nice_headers(entry['request']['headers'])

        for key, value in requestheaders.iteritems():
            cmd = cmd + ' -H ' + util.QuoteForPOSIX(key + ': ' + value)

        if not self.has_binary_content(requestheaders) and body:
            bodyparam = util.QuoteForPOSIX(body)
            try:
                cmd = cmd + ' -d ' + bodyparam
            except Exception as e:
                # probably failed because the content has a different encoding
                print e

        cmd = cmd + ' ' + util.QuoteForPOSIX(entry['request']['url'])

        raise gen.Return(cmd)


