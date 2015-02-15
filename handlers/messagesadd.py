import urllib
from tornado import gen
import tornado.web
import motor

from messagesrules import MessagesRulesHandler
from shared import util

class MessagesAddHandler(MessagesRulesHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        body = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})
            if entry:
                pass

        else:
            entry = None
        self.render("messageadd.html", tryagain=False, item=item, origin=origin, host=host, entry=entry, body=body, rules={}, name=None)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = util.cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        body = util.cleanarg(self.get_argument('body'), False)
        rules = self.get_rules()

        if not body or not host:
            self.render("messageadd.html", tryagain=True, item=item, origin=origin, host=host, entry=None, body=body, rules=rules, name=name)
            return

        collection = self.settings['db'].proxyservice['log_messages']

        yield motor.Op(collection.insert, {
            'host': host,
            'name': name,
            'message': body,
            'rules': rules
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
