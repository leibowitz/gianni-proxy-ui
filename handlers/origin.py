from tornado import gen
import tornado.web
import pymongo

from base import BaseRequestHandler

class OriginHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, origin=None):
        #collection = self.settings['db']['log_logentry'].open_sync()
        collection = self.settings['db'].proxyservice['log_logentry']
        query = {}
        if origin:
            query['request.origin'] = origin
        cursor = collection.find(query).sort([("$natural", pymongo.DESCENDING)])
        res = cursor.to_list(200)
        entries = yield res
        self.render("list.html", items=reversed(entries), tz=self.TZ, host=None, origin=origin)
