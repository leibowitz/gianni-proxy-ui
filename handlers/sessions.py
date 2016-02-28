from datetime import datetime, timedelta
from tornado import gen
import tornado.web
import pymongo

from base import BaseRequestHandler
from shared import util

class SessionsHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        # Get Latest 20 hosts 
        collection = self.settings['db'].proxyservice['log_logentry']

        # for the last 24 hours
        d = datetime.utcnow() - timedelta(hours=100)

        # 
        hosts = yield collection.find({"date": {"$gte":d}}).\
            sort([("$natural", pymongo.DESCENDING)]).\
            limit(200).\
            distinct("request.origin")

        # filter empty hosts - not necessary but could
        # happen if origin was not set on one request
        hosts = filter(None, hosts)

        # Get one request from each host to try
        # to sniff the user-agent
        entries = {}
        for host in hosts:
            request = yield collection.find_one({'request.origin':host}, {"request.headers":1})
            entries[host] = util.find_agent(util.get_header(self.nice_headers(request['request']['headers']), 'User-Agent'))

        # if proxyhost was set when starting, use it
        # otherwise determine host/ip by looking at the Host request header
        proxyip = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']

        self.render("sessions.html", 
                items=entries, 
                host=self.request.host, 
                port=proxyport, 
                ip=proxyip, 
                yourip=self.request.remote_ip)
