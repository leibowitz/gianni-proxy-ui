from urlparse import urlparse
import requests
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler

class RequestHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        headers = {}
        itemid = self.get_argument('item', None)
        body = None
        url = None
        method = None
        if itemid:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(itemid)})
            if entry and entry['request']:
                headers = entry['request']['headers']
                url = entry['request']['url'] if 'url' in entry['request'] else (entry['request']['scheme'] if 'scheme' in entry['request'] else '') + entry['request']['host'] + entry['request']['path']
                method = entry['request']['method']

        self.render("request.html", headers=headers, method=method, body=body, url=url)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        body = self.get_argument('body', None)
        headers = self.get_submitted_headers('header')
        url = self.get_argument('url', None)
        method = self.get_argument('method', 'GET')
        if not url:
            self.send_error(500)

        target = urlparse(url)
        params = {}

        proxyhost = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']
        host = proxyhost + ':' + str(proxyport)
        resp = requests.request(method, url, params=params, data=body, headers=headers, proxies={'http':host, 'https':host})
        self.redirect('/origin/'+proxyhost+'/host/'+target.netloc)
        self.write('done')
