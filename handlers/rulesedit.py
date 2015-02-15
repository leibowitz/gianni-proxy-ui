import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class RulesEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_rules']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        item = self.get_argument('item', None)
        origin = entry['origin'] or None if 'origin' in entry else self.get_argument('origin', None)
        host = self.get_argument('host', None)
        reqheaders = entry['reqheaders'] if entry and 'reqheaders' in entry else {}
        respheaders = entry['respheaders'] if entry and 'respheaders' in entry else {}
        fmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None
        respheaders = self.nice_headers(respheaders) if respheaders else respheaders
        reqheaders = self.nice_headers(reqheaders) if reqheaders else reqheaders
        self.render("ruleedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, body=None, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = util.cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        active = self.get_argument('active', False)
        active = active if active is False else True

        rhost = util.cleanarg(self.get_argument('rhost'), False)
        path = util.cleanarg(self.get_argument('path'), False)
        query = util.cleanarg(self.get_argument('query'), False)
        status = util.cleanarg(self.get_argument('status'), False)
        method = util.cleanarg(self.get_argument('method'), False)
        response = util.cleanarg(self.get_argument('response'), False)
        delay = int(util.cleanarg(self.get_argument('delay', 0), 0))
        body = util.cleanarg(self.get_argument('body'), False)
        reqheaders = self.get_submitted_headers('reqheader')
        respheaders = self.get_submitted_headers('respheader')

        dynamic = True if response is False and body is False and not respheaders else False

        collection = self.settings['db'].proxyservice['log_rules']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        fmt = util.get_format(util.get_content_type(respheaders)) if respheaders else None

        if not rhost and not path and not query and not status:
            respheaders = self.nice_headers(respheaders)
            reqheaders = self.nice_headers(reqheaders)
            self.render("ruleedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
            return

        reqheaders = reqheaders if reqheaders else False

        collection = self.settings['db'].proxyservice['log_rules']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'dynamic': dynamic,
            'host': rhost,
            'path': path,
            'query': query,
            'method': method,
            'status': status,
            'origin': origin,
            'delay': delay,
            'response': response,
            'reqheaders': reqheaders,
            'respheaders': util.array_headers(respheaders),
            'body': body
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        if host and host == rhost:
            params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rules?' + urllib.urlencode(params))

