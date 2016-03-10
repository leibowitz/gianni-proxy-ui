#!/usr/bin/env python

from setuptools import setup
import glob
#from distutils.core import setup

static_files = glob.glob("static/*.js") + glob.glob("static/*.css") + ['static/ca.crt', 'static/e3c54992.0']
static_fonts = glob.glob("fonts/*.otf") + glob.glob("fonts/*.eot") + glob.glob("fonts/*.svg") + glob.glob("fonts/*.ttf") + glob.glob("fonts/*.woff") + glob.glob("fonts/*.woff2")

setup(name='gianni-proxy-ui',
      version='0.1',
      description='GUI for gianni-proxy',
      author='Gianni Moschini',
      author_email='gianni.proxy@gmail.com',
      py_modules=['main', '__main__', 'multiplex'],
      include_package_data=True,
      packages=['handlers', 'shared'],
      data_files=[
           ('templates', glob.glob("templates/*.html")),
           ('static', static_files),
           ('css', glob.glob("css/*.css")),
           ('fonts', static_fonts),
           ],
      #package_data={'': ['templates/*.html', 'static/*', 'fonts/*', 'css/*']},
      requires=[
               'pymongo', 
               'motor', 
               'requests', 
               'sockjs.tornado', 
               'tornado', 
               'mimes', 
               'magic', 
               'httpheader', 
               'pygments',
               'pytz',
               'uuid',
               'tempfile',
               'bson',
               'gridfs',
               'urllib',
               'urlparse',
               'StringIO',
               'socket'
          ],
     )
