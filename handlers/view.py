import re
import os
import tempfile
from bson import objectid
from tornado import gen
import tornado.web
import motor

from base import BaseRequestHandler
from shared import util

class ViewHandler(BaseRequestHandler):

    def is_text_content(self, headers):
        #print headers
        if 'Content-Type' not in headers:
            return False
        return 'text' in headers['Content-Type'] \
               or 'json' in headers['Content-Type'] \
               or 'application/x-www-form-urlencoded' in headers['Content-Type'] \
               or 'application/javascript' in headers['Content-Type'] 
    
    def is_binary(self, headers):
        #assume not binary if missing headers
        if 'Content-Type' not in headers:
            return False

        if self.is_text_content(headers):
            return False

        if 'binary' in headers['Content-Type'] or 'image' in headers['Content-Type'] or 'pdf' in headers['Content-Type']:
            return True

        # assume binary in all other cases
        return True


    @tornado.web.asynchronous
    @gen.coroutine
    def post(self, ident):
        msgid = self.get_argument('msgid', None)        
        if msgid is not None:
            collection = self.settings['db'].proxyservice['log_messages']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(msgid)})
            rulecollection = self.settings['db'].proxyservice['log_rules']
            if entry and 'rules' in entry:
                for ruleid, active in entry['rules'].iteritems():
                    print 'switching rule ', ruleid, ' to ', active
                    rulecollection.update({'_id': self.get_id(ruleid)}, {'$set': {'active': active}})

            
        self.write('done')


    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        collection = self.settings['db'].proxyservice['log_logentry']
        fs = motor.MotorGridFS(self.settings['db'].proxyservice)

        try:
            oid = objectid.ObjectId(ident)
        except objectid.InvalidId as e:
            print e
            self.send_error(500)
            return
        #raise tornado.web.HTTPError(400)

        entry = yield motor.Op(collection.find_one, {'_id': oid})
        if not entry:
            raise tornado.web.HTTPError(404)

        requestquery = util.nice_body(entry['request']['query'], 'application/x-www-form-urlencoded')
        #print entry['request']['headers']
        requestheaders = self.nice_headers(entry['request']['headers'])
        responseheaders = self.nice_headers(entry['response']['headers'])
        requestbody = None
        responsebody = None

        socketuuid = util.get_uuid(entry)

        # consider the response finished
        finished = True

        #print entry['request']
        #print entry['response']
        if 'fileid' in entry['response'] and self.is_text_content(responseheaders):

            respfileid = entry['response']['fileid']
            filepath = os.path.join(tempfile.gettempdir(), "proxy-service", str(respfileid))
            #print filepath
            if not os.path.exists(filepath):
                responsebody = yield util.get_gridfs_content(fs, respfileid)
                if responsebody:
                    if 'text/plain' in util.get_content_type(responseheaders):
                        responsebody = util.get_body_non_empty_lines(responsebody.strip().split("\n"))
                    else:
                        responsebody = util.nice_body(responsebody, util.get_content_type(responseheaders))
            else:
                if 'text/plain' in util.get_content_type(responseheaders):
                    lines = open(filepath).readlines()
                    responsebody = util.get_body_non_empty_lines(lines)
                else:
                    content = open(filepath).read()
                    responsebody = util.nice_body(content, util.get_content_type(responseheaders))
                # request seems to be still open
                finished = False
                #responsebody = open(filepath).read()
                #ctype = responseheaders['Content-Type']
                #responsebody = util.nice_body(responsebody, ctype)

        cmd = 'curl' 
        cmd = cmd + ' -X ' + entry['request']['method']
        for key, value in requestheaders.iteritems():
            cmd = cmd + ' -H ' + util.QuoteForPOSIX(key + ': ' + value)
            if key == 'Cookie':
                requestheaders[key] = util.nice_body(value, 'application/x-www-form-urlencoded')

        if 'fileid' in entry['request'] and not self.is_binary(requestheaders):
            requestbody = yield util.get_gridfs_content(fs, entry['request']['fileid'])
            if requestbody:
                ctype = util.get_content_type(requestheaders)
                # default to x-www-form-urlencoded
                ctype = ctype if ctype is not None else 'application/x-www-form-urlencoded'
                #if self.is_text_content(requestheaders)

                if util.get_content_encoding(requestheaders) == 'gzip':
                    requestbody = util.ungzip(requestbody)

                    ctype = None

                bodyparam = util.QuoteForPOSIX(requestbody)
                try:
                    cmd = cmd + ' -d ' + bodyparam
                except Exception as e:
                    print e

                requestbody = util.nice_body(requestbody, ctype)
        #requestbody = util.nice_body(entry['request']['body'], requestheaders)
        #responsebody = util.nice_body(entry['response']['body'], responseheaders)

        cmd = cmd + ' ' + util.QuoteForPOSIX(entry['request']['url'])

        if entry['request']['method'] == 'GET':
            collection = self.settings['db'].proxyservice['log_messages']
            messages = yield collection.find({"host": entry['request']['host']}).sort('_id').to_list(100)
            for msg in messages:
                msg['message'] = re.escape(msg['message'])
        else:
            messages = {}

        self.render("one.html", 
                item=entry, 
                cmd=cmd,
                messages=messages,
                requestheaders=requestheaders, 
                responseheaders=responseheaders,
                requestbody=requestbody, 
                responsebody=responsebody,
                requestquery=requestquery, 
                finished=finished,
                socketuuid=socketuuid,
                origin=origin,
                host=host)
