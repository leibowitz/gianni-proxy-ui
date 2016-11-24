from tornado import gen
import tornado.web
from bson.objectid import ObjectId

from base import BaseRequestHandler

class DocSettingsHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db'].proxyservice['docsettings']
        cursor = collection.find({}).sort([('host', 1)])
        res = cursor.to_list(100)
        entries = yield res

        collection = self.settings['db'].proxyservice['documentation']
        domains = yield collection.distinct('request.host')

        items = {}
        for item in entries:
            item['exists'] = True
            items[ item['host'] ] = item

        for host in domains:
            if host not in items:
                items[ host ] = {'_id': ObjectId(), 'host': host, 'active': False, 'exists': False}

        self.render("docsettings.html", items=items)

    def post(self):
        collection = self.settings['db'].proxyservice['docsettings']
        ident = self.get_argument('ident', None)
        host = self.get_argument('host', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})
        elif action == "enable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {'active': True, 'host': host}}, upsert=True)
        elif action == "disable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {'active': False, 'host': host}}, upsert=True)

        if 'X-Requested-With' in self.request.headers and self.request.headers['X-Requested-With'] == "XMLHttpRequest":
            return

        self.redirect('/docsettings')

