import urllib
from tornado import gen
import tornado.web
import motor

from messagesrules import MessagesRulesHandler
from shared import util

class MessagesEditHandler(MessagesRulesHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_messages']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        rules = entry['rules'] if 'rules' in entry else {}
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        origin = self.get_argument('origin', None)
        self.render("messageedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, body=None, rules=rules, name=name)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = util.cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        body = util.cleanarg(self.get_argument('body'), False)
        rules = self.get_rules()

        if not body or not host:
            self.render("messageedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, body=body, rules=rules, name=name)
            return

        collection = self.settings['db'].proxyservice['log_messages']

        collection.update({'_id': self.get_id(ident)}, {
            "$set": {
                'host': host,
                'name': name,
                'message': body,
                'rules': rules
            }
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == rhost:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/messages?' + urllib.urlencode(params))
