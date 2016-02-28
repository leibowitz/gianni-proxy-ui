from datetime import datetime, timedelta
from tornado import gen
import tornado.web
import pymongo

from base import BaseRequestHandler
from shared import util

class HomeHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):

        # if proxyhost was set when starting, use it
        # otherwise determine host/ip by looking at the Host request header
        proxyip = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']

        self.render("index.html", 
                port=proxyport, 
                ip=proxyip, 
                host=self.request.host, 
                yourip=self.request.remote_ip)
