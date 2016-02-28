from tornado import gen
import tornado.web

from base import BaseRequestHandler

class RulesHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        
        query = {}

        if origin:
            query['origin'] = {'$in': [origin, None]}
        if host:
            query['host'] = {'$in': [host, None]}
        # merge all conditions with an and
        if len(query) > 1:
            query = {'$and': map(lambda x: {x[0]: x[1]}, query.iteritems())}

        #collection = self.settings['db']['log_logentry'].open_sync()
        collection = self.settings['db'].proxyservice['log_rules']
        cursor = collection.find(query).sort([('origin', 1), ('host', 1), ('path', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("rules.html", items=entries, item=item, origin=origin, host=host)

    def post(self):
        collection = self.settings['db'].proxyservice['log_rules']
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

