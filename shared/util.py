import collections
import tempfile
import json
import uuid
import gzip
import re
import os
import sys
import socket
import StringIO
import urlparse
import urllib
import mimes
import magic
import httpheader
from tornado import gen
from pygments import highlight
from pygments.util import ClassNotFound
from pygments.lexers import JsonLexer, IniLexer, get_lexer_for_mimetype
from pygments.formatters import HtmlFormatter

def QuoteForPOSIX(s):
    '''quote a string so it can be used as an argument in a  posix shell

       According to: http://www.unix.org/single_unix_specification/
          2.2.1 Escape Character (Backslash)

          A backslash that is not quoted shall preserve the literal value
          of the following character, with the exception of a <newline>.

          2.2.2 Single-Quotes

          Enclosing characters in single-quotes ( '' ) shall preserve
          the literal value of each character within the single-quotes.
          A single-quote cannot occur within single-quotes.

    '''
    return "\\'".join("'" + p + "'" for p in s.split("'"))

def ungzip(s):
    data = StringIO.StringIO(s)
    gzipper = gzip.GzipFile(fileobj=data)
    return gzipper.read()

def find_agent(useragent):
    if not useragent:
        return None
    ismatch = re.search("\((?P<agent>[^\)]+)\)", useragent)
    if not ismatch:
        return useragent
    parts = ismatch.groupdict()['agent'].split('; ')
    if len(parts) == 0:
        return useragent
    if len(parts) == 1:
        return parts[0]
    elif len(parts) > 3:
        return ';'.join(parts[3:])
    elif len(parts) > 1:
        return ';'.join(parts)
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
    
def get_uuid(entry):
    return str(uuid.UUID(bytes=entry['uuid'])) if 'uuid' in entry else None

def get_content_type(headers):
    return get_header(headers, 'Content-Type')

def get_content_encoding(headers):
    return get_header(headers, 'Content-Encoding')

def get_header(headers, key, default=None):
    return headers[key] if key in headers else default

# http://www.iana.org/assignments/media-types/media-types.xhtml
# http://en.wikipedia.org/wiki/Internet_media_type#Type_text
def get_format(content):
    if content is None or content == '':
        return None
    mtype = mimes.MIMEType.from_string(content)
    if mtype.format:
        return mtype.format
    elif mtype.type == u"text":
        return mtype.subtype
    elif mtype.type == "application" and mtype.subtype in ["json", "xml"]:
        return mtype.subtype

    return None

def array_headers(headers):
    return {k: [v] for k, v in headers.iteritems()}

def get_body_non_empty_lines(lines, ctype = None):
    return '\n'.join(map(lambda line: nice_body(line, ctype), filter(None, map(lambda line: line.strip(), lines)))) if len(lines) != 0 else []

def get_body_content_type(body, content = None):
    if content is not None:
        mimetype, chars = httpheader.parse_media_type(content, with_parameters=False)
        ctype = '/'.join(filter(None, mimetype))
    elif body is not None:
        ctype = magic.from_buffer(body, mime=True)
    else:
        ctype = None
    return ctype

def nice_body(body, content=None, cssclass=None):
    if not body:
        return None
    cssclasses = ['codehilite']
    if cssclass:
        cssclasses.append(cssclass)
    classes = ' '.join(cssclasses)
    content = get_body_content_type(body, content)
    if content is not None:
        if 'x-www-form-urlencoded' in content:
            lex = IniLexer()
        elif 'json' in content:
            lex = JsonLexer()
        else:
            try:
                lex = get_lexer_for_mimetype(content)
            except ClassNotFound as e:
                return body

        if isinstance(lex, IniLexer):
            parsedbody = urlparse.parse_qsl(body, keep_blank_values=True)
            if body and not parsedbody:
                return tornado.escape.xhtml_escape(body)
            args = collections.OrderedDict(sorted(parsedbody))
            params = "\n".join([k.strip() + "=" + v for k, v in args.iteritems()])
            return highlight(params, IniLexer(), HtmlFormatter(cssclass=classes))
        elif isinstance(lex, JsonLexer):
            try:
                return highlight(json.dumps(json.loads(body), indent=4), JsonLexer(), HtmlFormatter(cssclass=classes))
            except ValueError as e:
                pass

    return highlight(body, lex, HtmlFormatter(cssclass=classes))
    #except Exception as e:
    #    raise e
    #    print e
    #    return tornado.escape.xhtml_escape(body)
    #if headers != None and 'Content-Type' in headers and headers['Content-Type'].split(';')[0] == 'application/json':
    #    return highlight(body, JsonLexer(), HtmlFormatter())
    #    #return json.dumps(json.loads(body), indent=4)
    #return body

def raw_image_html(body, mime):
    encoded = urllib.quote(body.encode("base64"))
    return u'<img src="data:%s;base64,%s" />' % (mime, encoded)

def open_socket(name):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    filepath = os.path.join(tempfile.gettempdir(), "proxy-sockets", name)
    if not os.path.exists(filepath):
        print "Socket does not exist", filepath
        return None

    sock.setblocking(0)

    # Connect the socket to the port where the server is listening
    print >>sys.stderr, 'connecting to %s' % filepath
    try:
        sock.connect(filepath)
    except socket.error, msg:
        print >>sys.stderr, msg
        return None

    return sock

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

def tree(): return collections.defaultdict(tree)

def is_finished(filepath):
    return not os.path.exists(filepath)
    
def getfilepath(fileid):
    return os.path.join(tempfile.gettempdir(), "proxy-service", str(fileid))

def get_uncompressed_body(headers, body):
    ctype = get_content_type(headers)
    # default to x-www-form-urlencoded
    ctype = ctype if ctype is not None else 'application/x-www-form-urlencoded'

    if not body:
        return body, ctype

    if get_content_encoding(headers) == 'gzip':
        body = ungzip(body)
        ctype = get_body_content_type(body)

    return body, ctype

def indent(txt, stops=1):
    spacer = "\t".expandtabs(4) * stops
    for line in txt.splitlines():
        yield "%s%s" % (spacer, line)
