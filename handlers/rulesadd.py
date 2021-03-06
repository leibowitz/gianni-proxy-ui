import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class RulesAddHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        ruleid = self.get_argument('ruleid', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        doc = True if self.get_argument('doc', False) else False
        coll = 'documentation' if doc else 'log_logentry'
        body = None
        fmt = None
        reqheaders = {}
        respheaders = {}
        entry = None
        if item:
            collection = self.settings['db'].proxyservice[coll]
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})
            if entry:
                reqheaders = entry['request']['headers'] if 'request' in entry and 'headers' in entry['request'] and entry['request']['headers'] else reqheaders
                respheaders = entry['response']['headers'] if 'response' in entry and 'headers' in entry['response'] else respheaders
                status = entry['response']['status']

                if 'fileid' in entry['response']:
                    body, ctype = yield self.get_gridfs_body(entry['response']['fileid'], respheaders)
                    fmt = util.get_format(ctype)
                elif 'body' in entry['response']:
                    body = entry['response']['body']
                
                entry = entry['request']
                entry['status'] = status

        elif ruleid:
            collection = self.settings['db'].proxyservice['log_rules']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ruleid)})
            body = entry['body']
            reqheaders = entry['reqheaders'] if 'reqheaders' in entry and entry['reqheaders'] else reqheaders
            respheaders = entry['respheaders'] if 'respheaders' in entry else respheaders
            fmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None

        self.render("ruleadd.html", tryagain=False, item=item, origin=origin, host=host, entry=entry, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = util.cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)

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
        fmt = util.get_format(util.get_content_type(self.nice_headers(respheaders))) if respheaders else None

        if not rhost and not path and not query and not status:
            response = False
            self.render("ruleadd.html", tryagain=True, item=item, origin=origin, host=host, entry=None, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
            return

        # filter headers, set field to false if nothing has been added
        reqheaders = reqheaders if reqheaders else False

        collection = self.settings['db'].proxyservice['log_rules']

        yield motor.Op(collection.insert, {
            'active': True,
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
            'respheaders': respheaders,
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

