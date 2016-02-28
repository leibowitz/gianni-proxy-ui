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
        body = None
        url = None
        method = None
        if itemid:
            collection = self.settings['db'].proxyservice['log_logentry']
            fs = motor.MotorGridFS(self.settings['db'].proxyservice)
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(itemid)})
            if entry and entry['request']:
                headers = entry['request']['headers']
                url = entry['request']['url'] if 'url' in entry['request'] else (entry['request']['scheme'] if 'scheme' in entry['request'] else '') + entry['request']['host'] + entry['request']['path']
                method = entry['request']['method']
                requestquery = entry['request']['query']
                requestheaders = self.nice_headers(headers)
                body = None
                if 'fileid' in entry['request'] and not self.has_binary_content(requestheaders):
                    body = yield util.get_gridfs_content(fs, entry['request']['fileid'])
                    if body:
                        if util.get_content_encoding(requestheaders) == 'gzip':
                            body = util.ungzip(body)

        self.render("request.html", headers=headers, method=method, body=body, url=url, tryagain=False)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        body = self.get_argument('body', None)
        headers = self.get_submitted_headers('header')
        url = self.get_argument('url', None)
        method = self.get_argument('method', 'GET')
        if not url:
            self.render("request.html", headers=headers, method=method, body=body, url=url, tryagain=True)

        target = urlparse(url)
        params = {}

        proxyhost = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']
        host = proxyhost + ':' + str(proxyport)
        resp = requests.request(method, url, params=params, data=body, headers=headers)#, proxies={'http':host, 'https':host})
        #print resp.text, resp.status_code, resp.url, resp.headers
        #print body, requestheaders, method, url

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
            },
            'response': {
                'status': resp.status_code,
                'headers': resp.headers,
            },
            'uuid': suid,
            'date': datetime.datetime.utcnow(),
            }

	print type(resp.headers)
	ctype = util.get_content_type(self.nice_headers(headers))
	reqCtype = util.get_body_content_type(body, ctype)

	ctype = util.get_content_type(self.nice_headers(resp.headers))
	resCtype = util.get_body_content_type(resp.text, ctype)

        reqid = bson.objectid.ObjectId()
        resid = bson.objectid.ObjectId()

	reqEnc = util.get_content_encoding(self.nice_headers(headers))
	resEnc = resp.encoding
	if not resEnc:
	    resEnc = util.get_content_encoding(self.nice_headers(resp.headers))

	print reqid, body, reqCtype
	print resid, resp.text, resCtype

	gfs = motor.MotorGridFS(self.settings['db'].proxyservice, 'fs')

	if body: 
	    print 'saving request', reqCtype, reqEnc
	    rqid = yield gfs.put(body, _id=reqid, filename=str(reqid), contentType=reqCtype, encoding=reqEnc)
	    data['request']['fileid'] = reqid

	if resp.text:
	    print resp.headers
	    print 'saving response', resCtype, resEnc
	    if not resEnc:
		resEnc = 'utf8'
	    rsid = yield gfs.put(resp.text, _id=resid, filename=str(resid), contentType=resCtype, encoding=resEnc)
	    data['response']['fileid'] = resid

        print "Inserting"
        #print data
        collection = self.settings['db'].proxyservice['log_logentry']
        collection.insert(data, callback=self.inserted)

    def inserted(self, result, error):
        #print result, error
        #self.redirect('/origin/'+proxyhost+'/host/'+target.netloc)
        #self.write('done')
	pass
