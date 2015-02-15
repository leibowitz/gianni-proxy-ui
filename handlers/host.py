from tornado import gen
import tornado.web
import pymongo

from base import BaseRequestHandler

class HostHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.host": host}).sort([("$natural", pymongo.DESCENDING)])
        res = cursor.to_list(200)
        entries = yield res
        self.render("list.html", items=reversed(entries), tz=self.TZ, host=host, origin=None)

