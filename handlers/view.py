import re
import os
import tempfile
from bson import objectid
from tornado import gen
import tornado.web
import motor
import requests
from pygments import highlight
from pygments.lexers import BashLexer
from pygments.formatters import HtmlFormatter

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
        reqbody = None

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
        resbody = None

        socketuuid = util.get_uuid(entry)

        # consider the response finished
        finished = True

        if 'fileid' in entry['response']:

            respfileid = entry['response']['fileid']
            filepath = util.getfilepath(respfileid)
            finished = util.is_finished(filepath)
            
            if finished:
                resbody, ctype = yield self.get_gridfs_body(respfileid, responseheaders)
                responsebody = self.get_formatted_body(resbody, ctype)
            else:
                response_mime_type = util.get_content_type(requests.structures.CaseInsensitiveDict(responseheaders))
                responsebody = self.get_partial_content_body(filepath, response_mime_type)

        if 'fileid' in entry['request']:
            reqbody, ctype = yield self.get_gridfs_body(entry['request']['fileid'], requestheaders)
            requestbody = self.get_formatted_body(reqbody, ctype)

        # format the cookie header
        for key, value in requestheaders.iteritems():
            if key == 'Cookie':
                requestheaders[key] = util.nice_body(value, 'application/x-www-form-urlencoded', 'nopadding')

        # get pre-formatted messages for this host if needed
        messages = []
        if not finished:
            messages = yield self.get_messages(entry)

        cmd = yield self.get_curl_cmd(entry, reqbody)

        cmd = highlight(cmd, BashLexer(), HtmlFormatter(cssclass='codehilite curl'))

        fmt = util.get_format(util.get_content_type(self.nice_headers(responseheaders))) if responseheaders else None

        self.render("one.html", 
                item=entry, 
                cmd=cmd,
                body=resbody,
                fmt=fmt,
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
    def get_messages(self, entry):
        if entry['request']['method'] != 'GET':
            raise gen.Return({})
        collection = self.settings['db'].proxyservice['log_messages']
        messages = yield collection.find({"host": entry['request']['host']}).sort('_id').to_list(100)
        for msg in messages:
            msg['message'] = re.escape(msg['message'])
        raise gen.Return(messages)

