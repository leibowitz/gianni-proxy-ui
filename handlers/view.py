import re
import os
import tempfile
from bson import objectid
from tornado import gen
import tornado.web
import motor
import requests

from base import BaseRequestHandler
from shared import util

class ViewHandler(BaseRequestHandler):


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

        entry = yield motor.Op(collection.find_one, {'_id': oid})
        if not entry:
            raise tornado.web.HTTPError(404)

        requestquery = util.nice_body(entry['request']['query'], 'application/x-www-form-urlencoded')
        requestheaders = self.nice_headers(entry['request']['headers'])
        responseheaders = self.nice_headers(entry['response']['headers'])
        requestbody = None
        responsebody = None

        socketuuid = util.get_uuid(entry)

        # consider the response finished
        finished = True

        if 'fileid' in entry['response']:

            respfileid = entry['response']['fileid']
            filepath = util.getfilepath(respfileid)
            finished = util.is_finished(filepath)
            
            response_mime_type = util.get_content_type(requests.structures.CaseInsensitiveDict(responseheaders))
            if finished:
                body = yield util.get_gridfs_content(fs, respfileid)
                if body:
                    body, response_mime_type = self.get_uncompressed_body(responseheaders, body)
                    responsebody = self.get_formatted_body(body, response_mime_type)
            else:
                responsebody = self.get_partial_content_body(filepath, response_mime_type)

        if 'fileid' in entry['request'] and not self.has_binary_content(requestheaders):
            requestbody = yield util.get_gridfs_content(fs, entry['request']['fileid'])
            if requestbody:
                requestbody, ctype = self.get_uncompressed_body(requestheaders, requestbody)
                requestbody = util.nice_body(requestbody, ctype)

        # format the cookie header
        for key, value in requestheaders.iteritems():
            if key == 'Cookie':
                requestheaders[key] = util.nice_body(value, 'application/x-www-form-urlencoded', 'nopadding')

        # get pre-formatted messages for this host if needed
        messages = []
        if not finished:
            messages = yield self.get_messages(entry)

        cmd = yield self.get_curl_cmd(entry)

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
                host=host,
                show_save=True,
                show_resend=True)

    @gen.coroutine
    def get_curl_cmd(self, entry):
        cmd = 'curl' 
        cmd = cmd + ' -X ' + entry['request']['method']

        requestheaders = self.nice_headers(entry['request']['headers'])

        for key, value in requestheaders.iteritems():
            cmd = cmd + ' -H ' + util.QuoteForPOSIX(key + ': ' + value)

        if 'fileid' in entry['request'] and not self.has_binary_content(requestheaders):
            fs = motor.MotorGridFS(self.settings['db'].proxyservice)
            requestbody = yield util.get_gridfs_content(fs, entry['request']['fileid'])
            if requestbody:
                if util.get_content_encoding(requestheaders) == 'gzip':
                    requestbody = util.ungzip(requestbody)

                bodyparam = util.QuoteForPOSIX(requestbody)
                try:
                    cmd = cmd + ' -d ' + bodyparam
                except Exception as e:
                    # probably failed because the content has a different encoding
                    print e

        cmd = cmd + ' ' + util.QuoteForPOSIX(entry['request']['url'])

        raise gen.Return(cmd)


    @gen.coroutine
    def get_messages(self, entry):
        if entry['request']['method'] != 'GET':
            raise gen.Return({})
        collection = self.settings['db'].proxyservice['log_messages']
        messages = yield collection.find({"host": entry['request']['host']}).sort('_id').to_list(100)
        for msg in messages:
            msg['message'] = re.escape(msg['message'])
        raise gen.Return(messages)
