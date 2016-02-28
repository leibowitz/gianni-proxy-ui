from tornado import gen
import tornado.web

from base import BaseRequestHandler

class IgnoresHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        host = self.get_argument('host', None)
        
        query = {}

        if host:
            query['host'] = {'$in': [host, None]}

        collection = self.settings['db'].proxyservice['log_ignores']
        cursor = collection.find(query).sort([('host', 1), ('path', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("ignores.html", items=entries, host=host)

    def post(self):
        collection = self.settings['db'].proxyservice['log_ignores']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})
        elif action == "enable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": True}})
        elif action == "disable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": False}})

        if 'X-Requested-With' in self.request.headers and self.request.headers['X-Requested-With'] == "XMLHttpRequest":
            return

        self.show_list()

