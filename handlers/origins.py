from tornado import gen
import tornado.web
from datetime import datetime
from datetime import timedelta
import pymongo

from shared import util

from base import BaseRequestHandler

class OriginsHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        collection = self.settings['db'].proxyservice['origins']
        cursor = collection.find({}).sort([('name', 1)])
        res = cursor.to_list(100)
        results = yield res
        #for entry in results:
        #    print entry

        # Get Latest 20 hosts 
        collection = self.settings['db'].proxyservice['log_logentry']

        # for the last 100 hours
        d = datetime.utcnow() - timedelta(hours=100)

        # only check for the last 200 items
        hosts = yield collection.find({"date": {"$gte":d}}).\
            sort([("$natural", pymongo.DESCENDING)]).\
            limit(200).\
            distinct("request.origin")
        
        # filter empty hosts - not necessary but could
        # happen if origin was not set on one request
        hosts = filter(None, hosts)

        # make a dictionary out of results list
        rkeys = dict((r["origin"], r) for r in results)

        # Get one request from each host to try
        # to sniff the user-agent
        for host in hosts:
            request = yield collection.find_one({'request.origin':host}, {"request.headers":1})
            agent = util.find_agent(util.get_header(self.nice_headers(request['request']['headers']), 'User-Agent'))
            if host not in rkeys:
                rkeys[host] = {"origin": host, "agent": agent}
            else:
                rkeys[host]['agent'] = agent
        
        self.render("origins.html", items=rkeys)

    def post(self):
        collection = self.settings['db'].proxyservice['origins']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'origin': ident})
        elif action == "enable":
            collection.update({'origin': ident}, {'$set': {"filterAll": False}})
        elif action == "disable":
            collection.update({'origin': ident}, {'$set': {"filterAll": True}})

        if 'X-Requested-With' in self.request.headers and self.request.headers['X-Requested-With'] == "XMLHttpRequest":
            return
        
        self.redirect("/origins")

