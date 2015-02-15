from sockjs.tornado import SockJSRouter, SockJSConnection

from base import BaseRequestHandler

class BaseSockJSConnection(SockJSConnection, BaseRequestHandler):
    pass
