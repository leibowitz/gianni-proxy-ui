import urllib
import os
from sockjs.tornado import SockJSRouter
from multiplex import MultiplexConnection
from tornado.ioloop import IOLoop
from tornado.options import OptionParser
import tornado.web
import motor

from handlers import *

if __name__ == "__main__":
    handlers = [
        (r"/", HomeHandler),
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
        
    ListenerRouter = SockJSRouter(ListenerConnection, '/listener')
    handlers.extend(ListenerRouter.urls)

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
    ListenerConnection.tail(db.proxyservice['log_logentry'])
    
    IOLoop.instance().start()


