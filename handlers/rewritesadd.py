import urllib
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler

class RewritesAddHandler(BaseRequestHandler):


    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        entry = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})

        self.render("rewriteadd.html", tryagain=False, origin=origin, host=host, item=item, entry=entry, ohost=None, dhost=None, protocol=None, dprotocol=None)
    
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', False)
        host = self.get_argument('host', None)

        dhost = self.get_argument('dhost', False)
        ohost = self.get_argument('ohost', False)
        
        protocol = self.get_argument('protocol', False)
        dprotocol = self.get_argument('dprotocol', False)

        entry = None
        if not dhost and not dprotocol or not ohost and not protocol:
            self.render("rewriteadd.html", tryagain=True, item=item, origin=origin, host=host, ohost=ohost, dhost=dhost, protocol=protocol, dprotocol=dprotocol, entry=entry)
            return

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        yield motor.Op(collection.insert, {
            'active': True,
            'host': ohost,
            'dhost': dhost,
            'protocol': protocol,
            'dprotocol': dprotocol,
            'origin': origin
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == ohost:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rewrites?' + urllib.urlencode(params))
