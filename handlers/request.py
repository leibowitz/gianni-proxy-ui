from urlparse import urlparse
import requests
from tornado import gen
import tornado.web
import motor
from shared import util
import datetime
import uuid
import bson

from base import BaseRequestHandler

class RequestHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        headers = {}
        itemid = self.get_argument('item', None)
        doc = True if self.get_argument('doc', False) else False
        coll = 'documentation' if doc else 'log_logentry'
        body = None
        url = None
        method = 'GET'
        if itemid:
            collection = self.settings['db'].proxyservice[coll]
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(itemid)})
            if entry and entry['request']:
                headers = entry['request']['headers']
                if 'Content-Length' in headers:
                    del headers['Content-Length']
                url = entry['request']['url'] if 'url' in entry['request'] else (entry['request']['scheme'] if 'scheme' in entry['request'] else 'http') + '://' + entry['request']['host'] + (entry['request']['path'] if entry['request']['path'] else '')
                method = entry['request']['method']
                requestquery = entry['request']['query']
                requestheaders = self.nice_headers(headers)

                if 'fileid' in entry['request']:
                    body, ctype = yield self.get_gridfs_body(entry['request']['fileid'], requestheaders)
                elif 'body' in entry['request']:
                    body = entry['request']['body']

        self.render("request.html", headers=headers, method=method, body=body, url=url, methods=self.methods, tryagain=False)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        body = self.get_argument('body', None)
        if not body:
            body = None
        headers = self.get_submitted_headers('header')
        url = self.get_argument('url', None)
        method = self.get_argument('method', 'GET')
        if not url:
            self.render("request.html", headers=headers, method=method, body=body, url=url, methods=self.methods, tryagain=True)
            return

        target = urlparse(url)
        params = {}

        proxyhost = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']
        host = proxyhost + ':' + str(proxyport)
        now = datetime.datetime.utcnow()
        try:
            resp = requests.request(method, url, params=params, data=body, headers=self.nice_headers(headers), allow_redirects=False, timeout=10)#, proxies={'http':host, 'https':host})
            elapsed = resp.elasped
        except requests.Timeout as e:
            print e
            resp = None
            elapsed = datetime.datetime.utcnow() - now

        suid = bson.binary.Binary(uuid.uuid4().bytes, 0)
        data = {
            'request': {
                'path': target.path,
                'query': target.query,
                'scheme': target.scheme,
                'host': target.netloc,
                'headers': headers,
                'origin': '127.0.0.1',
                'url': url,
                'method': method,
                'time': elapsed.total_seconds(),
            },
            'response': {
                'status': resp.status_code if resp else 0,
                'headers': self.dict_headers(resp.headers) if resp else {},
            },
            'uuid': suid,
            'date': now,
            }

        ctype = util.get_content_type(self.nice_headers(headers))
        reqCtype = util.get_body_content_type(body, ctype)

        if resp:
            ctype = util.get_content_type(self.nice_headers(resp.headers))
            resCtype = util.get_body_content_type(resp.text, ctype)
        else:
            resCtype = None


        reqid = bson.objectid.ObjectId()
        resid = bson.objectid.ObjectId()

        reqEnc = util.get_content_encoding(self.nice_headers(headers))
        resEnc = resp.encoding if resp else None
        if not resEnc and resp:
            resEnc = util.get_content_encoding(self.nice_headers(resp.headers))

        gfs = motor.MotorGridFS(self.settings['db'].proxyservice, 'fs')

        if body: 
            rqid = yield gfs.put(body, _id=reqid, filename=str(reqid), contentType=reqCtype, encoding=reqEnc)
            data['request']['fileid'] = reqid

        if resp and resp.text:
            if not resEnc:
                resEnc = 'utf8'
            rsid = yield gfs.put(resp.text, _id=resid, filename=str(resid), contentType=resCtype, encoding=resEnc)
            data['response']['fileid'] = resid

        collection = self.settings['db'].proxyservice['log_logentry']
        itemid = yield collection.insert(data)
        self.redirect('item/'+str(itemid))

