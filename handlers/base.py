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
