import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class RewritesEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_hostrewrite']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        item = self.get_argument('item', None)
        origin = entry['origin'] or None if 'origin' in entry else self.get_argument('origin', None)
        host = self.get_argument('host', None)
        self.render("rewriteedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, ohost=entry['host'], dhost=entry['dhost'], protocol=entry['protocol'], dprotocol=entry['dprotocol'])
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', False)
        host = self.get_argument('host', None)

        ohost = util.cleanarg(self.get_argument('ohost'), False)
        dhost = util.cleanarg(self.get_argument('dhost'), False)
        
        protocol = util.cleanarg(self.get_argument('protocol'), False)
        dprotocol = util.cleanarg(self.get_argument('dprotocol'), False)

        active = self.get_argument('active', False)
        active = active if active is False else True

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        if not dhost and not dprotocol or not ohost and not protocol:
            self.render("rewriteedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, ohost=ohost, dhost=dhost, protocol=protocol, dprotocol=dprotocol)
            return

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'host': ohost,
            'dhost': dhost,
            'origin': origin,
            'protocol': protocol,
            'dprotocol': dprotocol
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == host:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rewrites?' + urllib.urlencode(params))


