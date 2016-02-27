from tornado.web import RequestHandler
from bson import objectid
import pytz

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
        return filter(None, self.get_arguments(fieldname+'[]', []))

    def get_submitted_headers(self, fieldname):

        headers = {}
        x = 0

        row = self.get_arguments(fieldname+'[' + str(x) + '][]', [])

        while len(row) > 1:

            if len(row[0].strip()) != 0:
                headers[ row[0] ] = row[1]

            row = self.get_arguments(fieldname+'[' + str(x) + '][]', [])
            x += 1

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

