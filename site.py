import collections
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import OptionParser
import requests
import tornado.web
from tornado import gen
from datetime import datetime, timedelta
import socket
import uuid
import motor
import mimes
import json
import urlparse
import urllib
import pytz
import pymongo
import gridfs
import os
import sys
import time
from sockjs.tornado import SockJSRouter, SockJSConnection
import sockjs
from sockjs.tornado.periodic import Callback
from bson import json_util, objectid
from pygments import highlight
from pygments.lexers import JsonLexer, TextLexer, IniLexer, get_lexer_for_mimetype
from pygments.formatters import HtmlFormatter
import tempfile
from multiplex import MultiplexConnection
import re

def find_agent(useragent):
    if not useragent:
        return None
    ismatch = re.search("\((?P<agent>[^\)]+)\)", useragent)
    if ismatch:
        parts = ismatch.groupdict()['agent'].split('; ')
        if len(parts) == 1:
            return parts[0]
        elif len(parts) > 1:
            return parts[1]
    return useragent

def cleanarg(arg, default=None):
    if not arg:
        return default
    arg = arg.strip()
    if arg == '':
        return default
    elif arg == '*':
        return True
    return arg
    
@gen.coroutine
def get_gridfs_content(fs, ident):
    data = None
    try:
        gridout = yield fs.get(ident)
        if gridout:
            data = yield gridout.read()
    except Exception as e:
        print e
    raise gen.Return(data)

def get_uuid(entry):
    return str(uuid.UUID(bytes=entry['uuid'])) if 'uuid' in entry else None

def get_content_type(headers):
    return get_header(headers, 'Content-Type')

def get_header(headers, key, default=None):
    return headers[key] if key in headers else default


# http://www.iana.org/assignments/media-types/media-types.xhtml
# http://en.wikipedia.org/wiki/Internet_media_type#Type_text
def get_format(content):
    if content is None:
        return None
    mtype = mimes.MIMEType.from_string(content)
    if mtype.format:
        return mtype.format
    elif mtype.type == u"text":
        return mtype.subtype
    elif mtype.type == "application" and mtype.subtype in ["json", "xml"]:
        return mtype.subtype

    return None

class BaseRequestHandler(tornado.web.RequestHandler):
    def get_id(self, ident):
        try:
            oid = objectid.ObjectId(ident)
        except objectid.InvalidId as e:
            print e
            self.send_error(500)
            return None
        return oid

    def get_submitted_headers(self, fieldname):

        headers = {}
        x = 0

        row = self.get_arguments(fieldname+'[' + str(x) + '][]', [])

        while len(row) > 1:

            if len(row[0].strip()) != 0:
                headers[ row[0] ] = row[1]

            row = self.get_arguments(fieldname+'[' + str(x) + '][]', [])
            x += 1

        return headers

    @staticmethod
    def s_nice_headers(headers = {}):
        if not headers:
            return {}
        return dict(map(lambda (k,v): (k, v[0] if type(v) is list else v), headers.iteritems()))
    
    def nice_headers(self, headers):
        return BaseRequestHandler.s_nice_headers(headers)

class BaseSockJSConnection(SockJSConnection, BaseRequestHandler):
    #db = motor.MotorClient('mongodb://localhost:17017').proxyservice

    #def __init__(self, session):
    #    super(BaseSockJSConnection, self).__init__(session)
    pass


class EchoConnection(BaseSockJSConnection):

    #is_connection_alive = True
    listeners = set()
    origin = None

    @staticmethod
    @gen.coroutine
    def tail(collection, origin=None):
        print 'Opening a global tailable cursor', collection
        dn = datetime.utcnow()
        query = {'date': {'$gte': dn} }
        if origin is not None:
            query['request.origin'] = origin
        #collection.find(query, tailable=True, await_data=True).tail(callback=self.on_new_requests)

        cursor = collection.find(query, tailable=True, await_data=True)
        while True:

            if not cursor.alive:
                now = datetime.utcnow()
                # While collection is empty, tailable cursor dies immediately
                yield gen.Task(IOLoop.current().add_timeout, timedelta(seconds=1))
                cursor = collection.find(query, tailable=True, await_data=True)

            if (yield cursor.fetch_next):
                EchoConnection.on_new_requests(cursor.next_object())

    def on_open(self, info):
        self.listeners.add(self)
        #self.tail()
        pass

    def on_close(self):
        self.listeners.remove(self)
        #print 'close'
        #self.is_connection_alive = False
        
    def on_message(self, msg):
        data = json.loads(msg)
        if 'filterOrigin' in data:
            self.origin = data['filterOrigin']
            #self.tail(collection=self.db['log_logentry'])#, origin=data['filterOrigin'])
            #IOLoop.current().run_sync(lambda: self.tail(origin=data['filterOrigin']))
            

    @staticmethod
    def on_new_requests(result):
        if result and EchoConnection.listeners:
            #for listener in EchoConnection.listeners:
                #if listener.origin is not None and result['request']['origin'] == listener.origin:
                    #print 'sending to listener ', listener
                    # uuid is a binary field, change it to string
                    # before sending it via websocket
                    result['uuid'] = get_uuid(result)
                    result['request']['headers'] = EchoConnection.s_nice_headers(result['request']['headers'])

                    msg = json.dumps(result, separators=(',', ':'), default=json_util.default)
                    #msg = proto.json_encode(result)
                    listener = next(iter(EchoConnection.listeners))
                    #listener.send(msg)
                    #listener = EchoConnection.listeners[0]
                    listener.broadcast(EchoConnection.listeners, msg)

class BodyConnection(BaseSockJSConnection):
    filet = None
    position = 0

    def on_open(self, info):
        pass
        
    def on_message(self, fileid):
        #print "message [" + fileid + "]"
        filepath = os.path.join(tempfile.gettempdir(), "proxy-service", fileid)
        if os.path.exists(filepath):
            self.tail_file(filepath)
        else:
            #print "File does not exist"
            self.close()
        
    @gen.engine
    def tail_file(self, filepath):
        #print "opening file"
        #self.position = 0
        self._file = open(filepath)
        self.position = 0

        # Go to the end of file
        self._file.seek(0,2)
        self.position = self._file.tell()

        self.pcb = PeriodicCallback(self.check_data, 1000)
        self.pcb.start()

        # check for new data every second        
        #self.pcb = tornado.ioloop.PeriodicCallback(self.check_data, 1000)
        #self.pcb = Callback(self.check_data)
        #self.pcb.start()
        #print "started"

    def check_data(self):
        if not self._file.closed:
            self._file.seek(self.position)
            line = self._file.readline()
            if line:
                self.position=self._file.tell()
                self.on_new_data(line)

#        self.on_new_data(data)
        #self.position = self.filet.follow(blocking=False, position=self.position)

    def on_new_data(self, data):
        #print "data ", data
        data = data.strip()

        if len(data) == 0:
            return

        try:
            data = nice_body(data, 'application/json')
            self.send(data)
            #json.dumps(json.loads(data), indent=4)
        except Exception as e:
            print e

    def on_close(self):
        #print "closing"
        if self._file is not None and not self._file.closed:
            self._file.close()
        self.pcb.stop()
        #self.position = 0
        #self.pcb.stop()
        #if self.filet != None:
        #    print self.filet

class HijackConnection(BaseSockJSConnection):

    def on_open(self, info):
        self.info = info
        uuid = self.session.name
        self.sock = open_socket(uuid)
        pass
        
    def on_message(self, msg):
        #print self.info.arguments
        #print self.session.conn
        #print self.session.server
        uuid = self.session.name
        print "received ", msg
        try:
            # Send data
            print >>sys.stderr, 'sending "%s"' % msg
            self.sock.sendall(msg)
        except Exception as e:
            pass
        
    def on_close(self):
        self.sock.close()
        print "done"


def get_numbers(ret, error):
    pass

def array_headers(headers):
    return {k: [v] for k, v in headers.iteritems()}

def get_body_non_empty_lines(lines, ctype = 'application/json'):
    return '\n'.join(map(lambda line: nice_body(line, ctype), filter(None, map(lambda line: line.strip(), lines)))) if len(lines) != 0 else []

def nice_body(body, content):
    if content is None:
        return body
    try:
        if 'application/x-www-form-urlencoded' in content:
            args = collections.OrderedDict(sorted(urlparse.parse_qsl(body)))
            params = "\n".join([k + "=" + v for k, v in args.iteritems()])
            return highlight(params, IniLexer(), HtmlFormatter(cssclass='codehilite'))
        if 'json' in content:
            return highlight(json.dumps(json.loads(body), indent=4), JsonLexer(), HtmlFormatter(cssclass='codehilite'))

        ctype, chars = parse_media_type(content, with_parameters=False)
        lex = get_lexer_for_mimetype('/'.join(filter(None, ctype)))
        print lex
        return highlight(body, lex, HtmlFormatter(cssclass='codehilite'))
    except Exception as e:
        return body
    #if headers != None and 'Content-Type' in headers and headers['Content-Type'].split(';')[0] == 'application/json':
    #    return highlight(body, JsonLexer(), HtmlFormatter())
    #    #return json.dumps(json.loads(body), indent=4)
    #return body


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
                headers = self.nice_headers(entry['request']['headers'])
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
        headers = self.nice_headers(headers)
        target = urlparse.urlparse(url)
        params = {}

        proxyhost = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']
        host = proxyhost + ':' + str(proxyport)
        resp = requests.request(method, url, params=params, data=body, headers=headers, proxies={'http':host, 'https':host})
        self.redirect('/origin/'+proxyhost+'/host/'+target.netloc)
        self.write('done')

class MainHandler(BaseRequestHandler):
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
            entries[host] = find_agent(get_header(self.nice_headers(request['request']['headers']), 'User-Agent'))

        # if proxyhost was set when starting, use it
        # otherwise determine host/ip by looking at the Host request header
        proxyip = self.settings['proxyhost'] or self.request.host.split(':')[0]
        proxyport = self.settings['proxyport']

        self.render("index.html", 
                items=entries, 
                host=self.request.host, 
                port=proxyport, 
                ip=proxyip, 
                yourip=self.request.remote_ip)

class OriginHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, origin=None):
        #collection = self.settings['db']['log_logentry'].open_sync()
        collection = self.settings['db'].proxyservice['log_logentry']
        query = {}
        if origin:
            query['request.origin'] = origin
        cursor = collection.find(query).sort([("$natural", pymongo.DESCENDING)])
        res = cursor.to_list(200)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), tz=TZ, host=None, origin=origin)

class ViewHandler(BaseRequestHandler):

    def is_text_content(self, headers):
        #print headers
        if 'Content-Type' not in headers:
            return False
        return 'text' in headers['Content-Type'] or 'json' in headers['Content-Type'] or 'application/x-www-form-urlencoded' in headers['Content-Type']
    
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

        requestquery = nice_body(entry['request']['query'], 'application/x-www-form-urlencoded')
        #print entry['request']['headers']
        requestheaders = self.nice_headers(entry['request']['headers'])
        responseheaders = self.nice_headers(entry['response']['headers'])
        requestbody = None
        responsebody = None

        socketuuid = get_uuid(entry)

        # consider the response finished
        finished = True

        #print entry['request']
        #print entry['response']
        if 'fileid' in entry['response'] and self.is_text_content(responseheaders):

            respfileid = entry['response']['fileid']
            filepath = os.path.join(tempfile.gettempdir(), "proxy-service", str(respfileid))
            #print filepath
            if not os.path.exists(filepath):
                responsebody = yield get_gridfs_content(fs, respfileid)
                if responsebody:
                    if 'text/plain' in get_content_type(responseheaders):
                        responsebody = get_body_non_empty_lines(responsebody.strip().split("\n"), 'application/json')
                    else:
                        responsebody = nice_body(responsebody, get_content_type(responseheaders))
            else:
                print filepath
                if 'text/plain' in get_content_type(responseheaders):
                    lines = open(filepath).readlines()
                    responsebody = get_body_non_empty_lines(lines, 'application/json')
                else:
                    content = open(filepath).read()
                    responsebody = nice_body(content, get_content_type(responseheaders))
                # request seems to be still open
                finished = False
                #responsebody = open(filepath).read()
                #ctype = responseheaders['Content-Type']
                #responsebody = nice_body(responsebody, ctype)

        if 'fileid' in entry['request'] and not self.is_binary(requestheaders):
            requestbody = yield get_gridfs_content(fs, entry['request']['fileid'])
            if requestbody:
                ctype = get_content_type(requestheaders)
                # default to x-www-form-urlencoded
                ctype = ctype if ctype is not None else 'application/x-www-form-urlencoded'
                #if self.is_text_content(requestheaders)
                requestbody = nice_body(requestbody, ctype)
            else:
                print 'nobody'
        else:
            print 'not reading body because maybe binary'
        #requestbody = nice_body(entry['request']['body'], requestheaders)
        #responsebody = nice_body(entry['response']['body'], responseheaders)

        if entry['request']['method'] == 'GET':
            collection = self.settings['db'].proxyservice['log_messages']
            messages = yield collection.find({"host": entry['request']['host']}).sort('_id').to_list(100)
            for msg in messages:
                msg['message'] = re.escape(msg['message'])
        else:
            messages = {}

        self.render("one.html", 
                item=entry, 
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

class HostHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, host):
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.host": host}).sort([("$natural", pymongo.DESCENDING)])
        res = cursor.to_list(200)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), tz=TZ, host=host, origin=None)

class OriginHostHandler(BaseRequestHandler):
    @tornado.web.asynchronous
    @gen.engine
    def get(self, origin, host):
        collection = self.settings['db'].proxyservice['log_logentry']
        cursor = collection.find({"request.host": host, "request.origin": origin}).sort([("$natural", pymongo.DESCENDING)])
        res = cursor.to_list(200)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("list.html", items=reversed(entries), tz=TZ, host=host, origin=origin)

class MessagesHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        
        query = {}

        if origin:
            query['origin'] = {'$in': [origin, None]}
        if host:
            query['host'] = {'$in': [host, None]}
        # merge all conditions with an and
        if len(query) > 1:
            query = {'$and': map(lambda x: {x[0]: x[1]}, query.iteritems())}

        collection = self.settings['db'].proxyservice['log_messages']
        cursor = collection.find(query).sort([('origin', 1), ('host', 1)])
        res = cursor.to_list(100)
        entries = yield res
        self.render("messages.html", items=entries, item=item, origin=origin, host=host)

    def post(self):
        collection = self.settings['db'].proxyservice['log_messages']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})

        self.show_list()

class MessagesRulesHandler(BaseRequestHandler):
    def get_rules(self):
        x = 0
        rid = self.get_argument('rules_ids[' + str(x) + ']', None)
        rstate = self.get_argument('rules_states[' + str(x) + ']', False)
        rstate = False if rstate == False else True
        rules = []
        
        while rid is not None:
            rules.append([rid, rstate])
            x = x + 1
            rid = self.get_argument('rules_ids[' + str(x) + ']', None)
            rstate = self.get_argument('rules_states[' + str(x) + ']', False)
            rstate = False if rstate == False else True

        return dict([[rid, rstate] for rid, rstate in rules if rid])


class MessagesAddHandler(MessagesRulesHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        body = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})
            if entry:
                pass

        else:
            entry = None
        self.render("messageadd.html", tryagain=False, item=item, origin=origin, host=host, entry=entry, body=body, rules={}, name=None)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        body = cleanarg(self.get_argument('body'), False)
        rules = self.get_rules()

        if not body or not host:
            self.render("messageadd.html", tryagain=True, item=item, origin=origin, host=host, entry=None, body=body, rules=rules, name=name)
            return

        collection = self.settings['db'].proxyservice['log_messages']

        yield motor.Op(collection.insert, {
            'host': host,
            'name': name,
            'message': body,
            'rules': rules
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == rhost:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/messages?' + urllib.urlencode(params))

class MessagesEditHandler(MessagesRulesHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_messages']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        rules = entry['rules'] if 'rules' in entry else {}
        item = self.get_argument('item', None)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        origin = self.get_argument('origin', None)
        self.render("messageedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, body=None, rules=rules, name=name)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        name = self.get_argument('name', None)
        body = cleanarg(self.get_argument('body'), False)
        rules = self.get_rules()

        if not body or not host:
            self.render("messageedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, body=body, rules=rules, name=name)
            return

        collection = self.settings['db'].proxyservice['log_messages']

        collection.update({'_id': self.get_id(ident)}, {
            "$set": {
                'host': host,
                'name': name,
                'message': body,
                'rules': rules
            }
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == rhost:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/messages?' + urllib.urlencode(params))

class RulesHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        
        query = {}

        if origin:
            query['origin'] = {'$in': [origin, None]}
        if host:
            query['host'] = {'$in': [host, None]}
        # merge all conditions with an and
        if len(query) > 1:
            query = {'$and': map(lambda x: {x[0]: x[1]}, query.iteritems())}

        #collection = self.settings['db']['log_logentry'].open_sync()
        collection = self.settings['db'].proxyservice['log_rules']
        cursor = collection.find(query).sort([('origin', 1), ('host', 1), ('path', 1)])
        res = cursor.to_list(100)
        entries = yield res
        #cursor.count(callback=get_numbers)
        self.render("rules.html", items=entries, item=item, origin=origin, host=host)

    def post(self):
        collection = self.settings['db'].proxyservice['log_rules']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})
        elif action == "enable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": True}})
        elif action == "disable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": False}})

        self.show_list()


class RulesEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_rules']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        item = self.get_argument('item', None)
        origin = entry['origin'] or None if 'origin' in entry else self.get_argument('origin', None)
        host = self.get_argument('host', None)
        reqheaders = entry['reqheaders'] if entry and 'reqheaders' in entry else {}
        respheaders = entry['respheaders'] if entry and 'respheaders' in entry else {}
        fmt = get_format(get_content_type(self.nice_headers(respheaders))) if respheaders else None
        #print array_headers(respheaders)
        respheaders = self.nice_headers(respheaders) if respheaders else respheaders
        reqheaders = self.nice_headers(reqheaders) if reqheaders else reqheaders
        self.render("ruleedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, body=None, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)
        active = self.get_argument('active', False)
        active = active if active is False else True

        rhost = cleanarg(self.get_argument('rhost'), False)
        path = cleanarg(self.get_argument('path'), False)
        query = cleanarg(self.get_argument('query'), False)
        status = cleanarg(self.get_argument('status'), False)
        method = cleanarg(self.get_argument('method'), False)
        response = cleanarg(self.get_argument('response'), False)
        delay = int(cleanarg(self.get_argument('delay', 0), 0))
        body = cleanarg(self.get_argument('body'), False)
        reqheaders = self.get_submitted_headers('reqheader')
        respheaders = self.get_submitted_headers('respheader')

        dynamic = True if response is False and body is False and not respheaders else False

        collection = self.settings['db'].proxyservice['log_rules']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        fmt = get_format(get_content_type(respheaders)) if respheaders else None

        if not rhost and not path and not query and not status:
            respheaders = self.nice_headers(respheaders)
            reqheaders = self.nice_headers(reqheaders)
            self.render("ruleedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
            return

        reqheaders = reqheaders if reqheaders else False

        collection = self.settings['db'].proxyservice['log_rules']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'dynamic': dynamic,
            'host': rhost,
            'path': path,
            'query': query,
            'method': method,
            'status': status,
            'origin': origin,
            'delay': delay,
            'response': response,
            'reqheaders': reqheaders,
            'respheaders': array_headers(respheaders),
            'body': body
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        if host and host == rhost:
            params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rules?' + urllib.urlencode(params))


class RulesAddHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        ruleid = self.get_argument('ruleid', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        body = None
        fmt = None
        reqheaders = {}
        respheaders = {}
        entry = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})
            if entry:
                fs = motor.MotorGridFS(self.settings['db'].proxyservice)
                body = yield get_gridfs_content(fs, entry['response']['fileid'])
                
                if entry:
                    reqheaders = self.nice_headers(entry['request']['headers'])
                    respheaders = self.nice_headers(entry['response']['headers'])
                    fmt = get_format(get_content_type(respheaders)) if respheaders else None
                    status = entry['response']['status']
                    entry = entry['request']
                    entry['status'] = status
        elif ruleid:
            collection = self.settings['db'].proxyservice['log_rules']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ruleid)})
            respheaders = self.nice_headers(entry['respheaders'])
            reqheaders = self.nice_headers(entry['reqheaders'])
            body = entry['body']
            fmt = get_format(get_content_type(respheaders)) if respheaders else None

        self.render("ruleadd.html", tryagain=False, item=item, origin=origin, host=host, entry=entry, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)

    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = cleanarg(self.get_argument('origin', False), False)
        host = self.get_argument('host', None)

        rhost = cleanarg(self.get_argument('rhost'), False)
        path = cleanarg(self.get_argument('path'), False)
        query = cleanarg(self.get_argument('query'), False)
        status = cleanarg(self.get_argument('status'), False)
        method = cleanarg(self.get_argument('method'), False)
        response = cleanarg(self.get_argument('response'), False)
        delay = int(cleanarg(self.get_argument('delay', 0), 0))
        body = cleanarg(self.get_argument('body'), False)

        
        reqheaders = self.get_submitted_headers('reqheader')
        respheaders = self.get_submitted_headers('respheader')
        dynamic = True if response is False and body is False and not respheaders else False
        fmt = get_format(get_content_type(respheaders)) if respheaders else None

        if not rhost and not path and not query and not status:
            response = False
            self.render("ruleadd.html", tryagain=True, item=item, origin=origin, host=host, entry=None, body=body, fmt=fmt, reqheaders=reqheaders, respheaders=respheaders)
            return

        # filter headers, set field to false if nothing has been added
        reqheaders = reqheaders if reqheaders else False

        collection = self.settings['db'].proxyservice['log_rules']

        yield motor.Op(collection.insert, {
            'active': True,
            'dynamic': dynamic,
            'host': rhost,
            'path': path,
            'query': query,
            'method': method,
            'status': status,
            'origin': origin,
            'delay': delay,
            'response': response,
            'reqheaders': reqheaders,
            'respheaders': array_headers(respheaders),
            'body': body
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        if host and host == rhost:
            params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rules?' + urllib.urlencode(params))

class RewritesHandler(BaseRequestHandler):
    def get(self):
        self.show_list()

    @tornado.web.asynchronous
    @gen.engine
    def show_list(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        
        query = {}

        if origin:
            query['origin'] = {'$in': [origin, None]}
        if host:
            query['host'] = {'$in': [host, None]}
        # merge all conditions with an and
        if len(query) > 1:
            query = {'$and': map(lambda x: {x[0]: x[1]}, query.iteritems())}

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        cursor = collection.find(query)
        res = cursor.to_list(100)
        entries = yield res
        self.render("rewrites.html", items=entries, item=item, origin=origin, host=host)

    def post(self):
        collection = self.settings['db'].proxyservice['log_hostrewrite']
        ident = self.get_argument('ident', None)
        action = self.get_argument('action', None)
        if action == "delete":
            collection.remove({'_id': self.get_id(ident)})
        elif action == "enable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": True}})
        elif action == "disable":
            collection.update({'_id': self.get_id(ident)}, {'$set': {"active": False}})

        self.show_list()

class RewritesAddHandler(BaseRequestHandler):


    @tornado.web.asynchronous
    @gen.engine
    def get(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', None)
        host = self.get_argument('host', None)
        entry = None
        if item:
            collection = self.settings['db'].proxyservice['log_logentry']
            entry = yield motor.Op(collection.find_one, {'_id': self.get_id(item)})

        self.render("rewriteadd.html", tryagain=False, origin=origin, host=host, item=item, entry=entry, ohost=None, dhost=None, protocol=None, dprotocol=None)
    
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', False)
        host = self.get_argument('host', None)

        dhost = self.get_argument('dhost', False)
        ohost = self.get_argument('ohost', False)
        
        protocol = self.get_argument('protocol', False)
        dprotocol = self.get_argument('dprotocol', False)

        if not dhost and not dprotocol or not ohost and not protocol:
            self.render("rewriteadd.html", tryagain=True, item=item, origin=origin, host=host, ohost=ohost, dhost=dhost, protocol=protocol, dprotocol=dprotocol)
            return

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        yield motor.Op(collection.insert, {
            'active': True,
            'host': ohost,
            'dhost': dhost,
            'protocol': protocol,
            'dprotocol': dprotocol,
            'origin': origin
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == ohost:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rewrites?' + urllib.urlencode(params))

class RewritesEditHandler(BaseRequestHandler):

    @tornado.web.asynchronous
    @gen.engine
    def get(self, ident):
        collection = self.settings['db'].proxyservice['log_hostrewrite']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})
        if not entry:
            raise tornado.web.HTTPError(404)

        item = self.get_argument('item', None)
        origin = entry['origin'] or None if 'origin' in entry else self.get_argument('origin', None)
        host = self.get_argument('host', None)
        self.render("rewriteedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=False, ohost=entry['host'], dhost=entry['dhost'], protocol=entry['protocol'], dprotocol=entry['dprotocol'])
    
    @tornado.web.asynchronous
    @gen.engine
    def post(self, ident):
        item = self.get_argument('item', None)
        origin = self.get_argument('origin', False)
        host = self.get_argument('host', None)

        ohost = cleanarg(self.get_argument('ohost'), False)
        dhost = cleanarg(self.get_argument('dhost'), False)
        
        protocol = cleanarg(self.get_argument('protocol'), False)
        dprotocol = cleanarg(self.get_argument('dprotocol'), False)

        active = self.get_argument('active', False)
        active = active if active is False else True

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        entry = yield motor.Op(collection.find_one, {'_id': self.get_id(ident)})

        if not dhost and not dprotocol or not ohost and not protocol:
            self.render("rewriteedit.html", entry=entry, item=item, origin=origin, host=host, tryagain=True, ohost=ohost, dhost=dhost, protocol=protocol, dprotocol=dprotocol)
            return

        collection = self.settings['db'].proxyservice['log_hostrewrite']
        collection.update({'_id': self.get_id(ident)}, {
            'active': active,
            'host': ohost,
            'dhost': dhost,
            'origin': origin,
            'protocol': protocol,
            'dprotocol': dprotocol
        })

        params = {}
        if origin:
            params['origin'] = origin
        # this is required otherwise we will filter out this rule after the redirect
        #if host and host == host:
        #    params['host'] = host
        if item:
            params['item'] = item
        self.redirect('/rewrites?' + urllib.urlencode(params))



def open_socket(name):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    filepath = os.path.join(tempfile.gettempdir(), "proxy-sockets", name)
    if not os.path.exists(filepath):
        print "Socket does not exist", filepath
        return None

    # Connect the socket to the port where the server is listening
    print >>sys.stderr, 'connecting to %s' % filepath
    try:
        sock.connect(filepath)
    except socket.error, msg:
        print >>sys.stderr, msg
        return None

    return sock


if __name__ == "__main__":
    TZ = pytz.timezone('Europe/London')

    handlers = [
        (r"/", MainHandler),
        (r"/origin/(?P<origin>[^\/]+)", OriginHandler),
        (r"/all", OriginHandler),
        (r"/origin/(?P<origin>[^\/]+)/host/(?P<host>[^\/]+)", OriginHostHandler),
        (r"/item/(?P<ident>[^\/]+)", ViewHandler),
        (r"/host/(?P<host>[^\/]+)", HostHandler),
        (r"/request", RequestHandler),
        (r"/messages", MessagesHandler),
        (r"/messages/add", MessagesAddHandler),
        (r"/message/(?P<ident>[^\/]+)", MessagesEditHandler),
        (r"/rules", RulesHandler),
        (r"/rules/add", RulesAddHandler),
        (r"/rule/(?P<ident>[^\/]+)", RulesEditHandler),
        (r"/rewrites", RewritesHandler),
        (r"/rewrites/add", RewritesAddHandler),
        (r"/rewrite/(?P<ident>[^\/]+)", RewritesEditHandler),
    ]
        
    EchoRouter = SockJSRouter(EchoConnection, '/listener')
    handlers.extend(EchoRouter.urls)

    BodyRouter = SockJSRouter(BodyConnection, '/body')
    handlers.extend(BodyRouter.urls)

    # Create multiplexer
    router = MultiplexConnection.get(objClass=HijackConnection)

    # Register multiplexer
    HijackRouter = SockJSRouter(router, '/hijack')
    handlers.extend(HijackRouter.urls)

    options = OptionParser()
    options.define("port", default=8002, help="run on the given port", type=int)
    options.define("proxyport", default=8989, help="port the proxy is running on", type=int)
    options.define("proxyhost", default=None, help="host the proxy is running on", type=str)
    options.define("mongourl", default="localhost:27017", help="mongodb url", type=str)

    options.parse_command_line()

    db = motor.MotorClient('mongodb://'+options.mongourl, tz_aware=True)

    ui_methods={'nice_headers': BaseRequestHandler.nice_headers}
    settings = dict(
        handlers=handlers,
        static_path=os.path.join(os.path.dirname(__file__), 'static'),
        db=db,
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        proxyhost=options.proxyhost,
        proxyport=options.proxyport,
        debug=True,
        ui_methods=ui_methods
    )               

    application = tornado.web.Application(
        **settings)

    application.listen(options.port)
    # open a global tailable cursor on log_logentry
    EchoConnection.tail(db.proxyservice['log_logentry'])
    
    IOLoop.instance().start()


