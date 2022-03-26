# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 arneson
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, unicode_literals

import requests
import traceback
from threading import Thread

try:
    # Python 3
    from urllib.parse import urlparse, parse_qs, unquote_plus
except:
    # Python 2.7
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus

try:
    # for Python 3
    from http.server import BaseHTTPRequestHandler, HTTPServer
except:
    # Python 2.7
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from kodi_six import xbmc, xbmcaddon

from .common import plugin, __addon_id__
from .textids import Msg, _T
from .debug import log
from .config import TidalConfig
from .tidalapi import Session

#------------------------------------------------------------------------------
# HTTP Server for Images
#------------------------------------------------------------------------------

class LocalHttpRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            url = urlparse(self.path)
            params = parse_qs(url.query)

            if url.path == '/artist_fanart':
                # Load the artist fanart image and send the JPG to the caller
                if 'id' not in params:
                    self.send_error(404, 'Missing Parameter "id"')
                    return
                session = Session(config=TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__)))
                artist = session.get_artist(params['id'][0])
                if artist and artist.fanart:
                    jpg_data = requests.get(artist.fanart)
                    if jpg_data.ok:
                        self.send_response(200)
                        self.send_header('Content-type', 'image/jpg')
                        self.end_headers()
                        self.wfile.write(jpg_data.content)
                    else:
                        self.send_error(404, 'Artist has no fanart: %s' % self.path)
                else:
                    self.send_error(404, 'Artist has no fanart: %s' % self.path)

            elif url.path == '/lyrics':
                if 'id' not in params:
                    self.send_error(404, 'Missing Parameter "id"')
                    return
                self.send_lyrics(params['id'][0])

            elif url.path == '/client' or url.path == '/':
                self.send_client_config_page()

            elif url.path == '/client_submit':
                client_id = params.get('client_id', [''])[0]
                client_secret = params.get('client_secret', [''])[0]
                self.send_client_submit_page(client_id, client_secret)

            else:
                self.send_error(501, 'Illegal Request: %s' % self.path)
        except Exception as e:
            self.send_error(404, 'Request failed')
            log.logException(e, "HTTP Request failed.")
            traceback.print_exc()

    def log_message(self, *args):
        # Disable the BaseHTTPServer Log
        pass

    def send_lyrics(self, track_id):
        try:
            session = Session(config=TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__)))
            if not session._config.enable_lyrics:
                self.send_error(404, 'Lyrics are disabled in settings.')
                return
            r = session.request(method='GET', path='tracks/%s/lyrics' % track_id)
            if not r.ok:
                self.send_error(404, 'No lyrics for track %s' % track_id)
                return
            json_obj = r.json()
            if not json_obj.get('subtitles', None) and not json_obj.get('lyrics', None):
                self.send_error(404, 'No lyrics for track %s' % track_id)
                return
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(r.text.encode("utf-8"))
        except:
            self.send_error(404, 'No lyrics for track %s' % track_id)
        finally:
            session = None


    def send_client_config_page(self):
        try:
            try:
                msg = _T(Msg.i30282)
                settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
                if settings.access_token and settings.expire_time:
                    msg = _T(Msg.i30022) + ' %s' % settings.expire_time
            except:
                traceback.print_exc()
            html = Pages().client_config_page(msg, settings).encode('utf-8')
            del settings
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html)
            self.wfile.close()
        except:
            self.send_error(404, 'Failed to start OAuth login')
            traceback.print_exc()

    def send_client_submit_page(self, client_id, client_secret):
        try:
            try:
                linkurl = _T(Msg.i30253)
                settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
                session = Session(config=settings)
                code = session.login_part1(client_id, client_secret)
                linkurl = code.verificationUriComplete
                session.cleanup()
                session = None
                xbmc.executebuiltin('RunPlugin(%s)' % plugin.url_with_qs('/login', **vars(code)))
            except:
                traceback.print_exc()
            html = Pages().client_submit_page(linkurl, settings).encode('utf-8')
            del settings
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html)
            self.wfile.close()
        except:
            self.send_error(404, 'Failed to start OAuth login')
            traceback.print_exc()


class LocalHTTPServer(HTTPServer):

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        HTTPServer.allow_reuse_address = True
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)

    def process_request(self, request, client_address):
        try:
            # Avoid Broken-Pipe errors
            HTTPServer.process_request(self, request, client_address)
        except:
            pass

#------------------------------------------------------------------------------
# Service 
#------------------------------------------------------------------------------

class TidalMonitor(xbmc.Monitor):

    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.http_server = None
        self.http_thread = None
        self.settings = None

    def __del__(self):
        log.info('TidalMonitor() Object destroyed.')

    def _start_servers(self):
        if self.http_server == None and self.http_thread == None:
            try:
                self.http_server = LocalHTTPServer(('', self.settings.fanart_server_port), LocalHttpRequestHandler)
            except:
                log.error('Fanart Server not startet on port %d' % self.settings.fanart_server_port)
                self.http_server = LocalHTTPServer(('', 0), LocalHttpRequestHandler)
                self.settings.setSetting('fanart_server_port', '%d' % self.http_server.server_address[1])
            self.http_thread = Thread(target=self.http_server.serve_forever)
            self.http_server.server_activate()
            self.http_server.timeout = 2
            self.http_thread.start()
            log.info('Fanart Server started on port %d' % self.http_server.server_address[1])
        else:
            log.warning('Fanart Server already running')

    def _stop_servers(self):
        try:
            if self.http_server != None and self.http_thread != None:
                log.info('Stopping Fanart Server ...')
                self.http_server.shutdown()
                self.http_thread.join(2)
                log.info('Stopped Fanart Server')
        except:
            log.error('Failed to stop Fanart Server')
        finally:
            self.http_server = None
            self.http_thread = None

    def onSettingsChanged(self):
        xbmc.Monitor.onSettingsChanged(self)
        self.settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))

    def run(self):
        log.info('TidalMonitor: Service Started')
        self.settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
        self._start_servers()
        wait_time = 2
        while not self.abortRequested():
            if self.waitForAbort(wait_time):
                break
        self._stop_servers()
        log.info('TidalMonitor: Service Terminated')


class Pages(object):

    client_configuration = {
        'css':
            'body { background: #141718; }\n'
            '.center { margin: auto; width: 640px; padding: 10px; }\n'
            '.config_form { width: 615px; height: 220px; font-size: 16px; background: #1a2123;  padding: 30px 30px 15px 30px; border: 5px solid #1a2123; }\n'
            'h5 { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; font-weight: 600; width: 615px; height: 20px;\n'
            '  background: #0f84a5; padding: 5px 30px 5px 30px; border: 5px solid #0f84a5; margin: 0px; }\n'
            '.config_form input[type=submit],\n'
            '.config_form input[type=button],\n'
            '.config_form input[type=text],\n'
            '.config_form textarea,\n'
            '.config_form label { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; }\n'
            '.config_form label { display:block; margin-bottom: 10px; }\n'
            '.config_form label > span { display: inline-block; float: left; width: 150px; }\n'
            '.config_form input[type=text] { background: transparent; border: none; border-bottom: 1px solid #147a96; width: 440px; outline: none; padding: 0px 0px 0px 0px; }\n'
            '.config_form input[type=text]:focus { border-bottom: 1px dashed #0f84a5; }\n'
            '.config_form input[type=submit],\n'
            '.config_form input[type=button] { width: 150px; background: #141718; border: none; padding: 8px 0px 8px 10px; border-radius: 5px; color: #fff; margin-top: 10px }\n'
            '.config_form input[type=submit]:hover,\n'
            '.config_form input[type=button]:hover { background: #0f84a5; }\n',

        'html':
            '<!doctype html>\n<html>\n'
            '<head>\n\t<meta charset="utf-8">\n'
            '  <title>{title}</title>\n'
            '  <style>\n{css}\t</style>\n'
            '</head>\n<body>\n'
            '  <div class="center">\n'
            '  <h5>{header}</h5>\n'
            '  <form action="/client_submit" class="config_form">\n'
            '    <label for="client_name">\n'
            '    <span>{client_name_head}°</span>{client_name_value}&nbsp;\n'
            '    </label>\n'
            '    <label for="client_id">\n'
            '    <span>{client_id_head}</span><input type="{d}" name="client_id" value="{client_id_value}" size="50"/>\n'
            '    </label>\n'
            '    <label for="client_secret">\n'
            '    <span>{client_secret_head}</span><input type="{d}" name="client_secret" value="{client_secret_value}" size="50"/>\n'
            '    </label>\n'
            '    <label for="msg">\n'
            '    <span>{msg_head}</span>{msg_text}<br><br>{remark}\n'
            '    </label>\n'
            '    <span>&nbsp;</span>\n'
            '    <input type="submit" value="{submit}">\n'
            '  </form>\n'
            '  </div>\n'
            '</body>\n</html>'
    }

    client_submit = {
         'css':
            'body { background: #141718; }\n'
            '.center { margin: auto; width: 640px; padding: 10px; }\n'
            '.textcenter { margin: auto; width: 615px; padding: 10px; text-align: center; }\n'
            '.content { width: 615px; height: 140px; background: #1a2123; padding: 30px 30px 15px 30px; border: 5px solid #1a2123; }\n'
            'h5 { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; font-weight: 600; width: 615px; height: 20px;\n'
            '  background: #0f84a5; padding: 5px 30px 5px 30px; border: 5px solid #0f84a5; margin: 0px; }\n'
            'span { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; display: block; float: left; width: 615px; }\n'
            'big { font-family: Arial, Helvetica, sans-serif; font-size: 32px; color: #fff; height: 36px; }\n'
            'a:link { color: #fff; }\n'
            'a:visited { color: #fff; }\n'
            'small { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #fff; }\n',

        'html':
            '<!doctype html>\n<html>\n'
            '<head>\n\t<meta charset="utf-8">\n'
            '  <title>{title}</title>\n'
            '  <style>\n{css}\t</style>\n'
            '</head>\n<body>\n'
            '  <div class="center">\n'
            '    <h5>{header}</h5>\n'
            '    <div class="content">\n'
            '      <span>{line1}</span>\n'
            '      <span>{line2}</span>\n'
            '      <span>{line3}</span>\n'
            '      <div class="textcenter">\n'
            '        <span><big>{line4}</big></span>\n'
            '      </div>\n'
            '      <span>&nbsp;</span>\n'
            '      <span>&nbsp;</span>\n'
            '      <div class="textcenter">\n'
            '        <span><small>{footer}</small></span>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</body>\n</html>'
    }

    def client_config_page(self, msg, settings):
        html = self.client_configuration.get('html')
        css = self.client_configuration.get('css')
        html = html.format(css=css, title=settings.getAddonInfo('name'), header=_T(Msg.i30280),
                           client_name_head=_T(Msg.i30028), 
                           client_name_value=settings.client_name, 
                           client_id_head='' if settings.client_name else _T(Msg.i30026), 
                           client_id_value=settings.client_id, 
                           client_secret_head='' if settings.client_name else _T(Msg.i30009), 
                           client_secret_value=settings.client_secret,
                           remark= _T(Msg.i30287) if settings.client_name else _T(Msg.i30288),
                           d='hidden' if settings.client_name else 'text',
                           submit=_T(Msg.i30208),  msg_head=_T(Msg.i30281), msg_text=msg)
        return html

    def client_submit_page(self, url, settings):
        html = self.client_submit.get('html')
        css = self.client_submit.get('css')
        if url.lower().startswith('http'):
            # redirect = '<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
            redirect = '<a href="{url}">{url}</a>'
        else:
            redirect = '{url}'
        html = html.format(css=css, title=settings.getAddonInfo('name'), header=_T(Msg.i30280),
                           line1=_T(Msg.i30209), line2='&nbsp;', line3='&nbsp;', line4=redirect.format(url=url), footer='&nbsp;')
        return html

# End of File