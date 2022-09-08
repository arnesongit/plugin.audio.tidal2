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
import base64
import time
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
from .tidalapi.models import DashInfo

#------------------------------------------------------------------------------
# HTTP Server for Images
#------------------------------------------------------------------------------

class LocalHttpRequestHandler(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.0"

    def do_GET(self):
        try:
            url = urlparse(self.path)
            params = parse_qs(url.query)

            if url.path in ['/', '', '/client']:
                self.send_response(302)
                self.send_header('Location', '/login')
                self.end_headers()

            elif url.path == '/artist_fanart':
                # Load the artist fanart image and send the JPG to the caller
                if 'id' not in params:
                    self.send_error(404, 'Missing Parameter "id"')
                else:
                    self.send_fanart(params['id'])

            elif url.path == '/favicon.ico':
                self.send_error(501)

            elif url.path == '/lyrics':
                if 'id' not in params:
                    self.send_error(404, 'Missing Parameter "id"')
                else:
                    # Get the lyrics of a track and send it back
                    self.send_lyrics(params['id'][0])

            elif url.path == '/manifest.mpd':
                if 'data' not in params:
                    self.send_error(501, 'Missing Parameter "data"')
                else:
                    self.send_mpd_manifest(params['data'][0])

            elif url.path == '/manifest.m3u8':
                if 'data' not in params:
                    self.send_error(501, 'Missing Parameter "data"')
                else:
                    self.send_m3u8_playlist(params['data'][0])

            elif url.path == '/login':
                self.send_login_page()

            elif url.path == '/login_step2':
                # User pressed Login button on the login page
                client_id = params.get('client_id', [''])[0]
                client_secret = params.get('client_secret', [''])[0]
                self.send_login_page2(client_id, client_secret)

            else:
                self.send_error(501, 'Illegal Request: %s' % self.path)

        except Exception as e:
            self.send_error(404, 'Request failed')
            log.logException(e, "HTTP Request failed.")
            traceback.print_exc()

    def log_message(self, format, *args):
        try:
            if self.server.enable_messages:
                log.info("HTTP %s" % format%args)
        except:
            pass

    def _send_headers(self, content_type=None, content_length=0, cacheable=False ):
        if content_type:
            self.send_header('Content-Type', content_type)
        if content_length:
            self.send_header('Content-Length', str(content_length))
        if not cacheable:
            self.send_header('Last-Modified', self.date_time_string(time.time()))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    def send_fanart(self, artist_ids):
        try:
            # If the Fanart is fetched multiple times, it is allready in the buffer
            if self.server.last_fanart_ids == ','.join(artist_ids) and self.server.last_fanart_data:
                self.send_response(200)
                self._send_headers(content_type='image/jpg', content_length=len(self.server.last_fanart_data), cacheable=True)
                self.wfile.write(self.server.last_fanart_data)
                return
        except Exception as e:
            log.logException(e, "Failed to send buffered fanart.")
        try:
            ok = False
            session = Session(config=TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__)))
            session.user = None # No user favorites should be loaded
            for artist_id in artist_ids:
                artist = session.get_artist(artist_id)
                if artist and artist.fanart:
                    jpg_data = requests.get(artist.fanart)
                    if jpg_data.ok:
                        ok = True
                        self.send_response(200)
                        self._send_headers(content_type='image/jpg', content_length=len(jpg_data.content), cacheable=True)
                        self.wfile.write(jpg_data.content)
                        # Save last found Fanart into the buffer, because Kodi fetches the data multiple times
                        self.server.last_fanart_ids = ','.join(artist_ids)
                        self.server.last_fanart_data = jpg_data.content
                        break
            session.cleanup()
            del session
        except Exception as e:
            log.logException(e, "HTTP Request failed.")
            traceback.print_exc()
        finally:
            if not ok:
                self.send_error(404, 'Failed to get fanart for Artist %s' % artist_ids[0])
            session = None

    def send_lyrics(self, track_id):
        try:
            session = Session(config=TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__)))
            if not session._config.enable_lyrics:
                self.send_error(404, 'Lyrics are disabled in settings.')
                return
            r = session.request(method='GET', path='tracks/%s/lyrics' % track_id, params={'countryCode': session._config.user_country_code})
            if not r.ok:
                self.send_error(404, 'No lyrics for track %s' % track_id)
                return
            json_obj = r.json()
            if not json_obj.get('subtitles', None) and not json_obj.get('lyrics', None):
                self.send_error(404, 'No lyrics for track %s' % track_id)
                return
            self.send_response(200)
            self._send_headers(content_type='application/json')
            self.wfile.write(r.text.encode("utf-8"))
            session.cleanup()
            del session
        except Exception as e:
            self.send_error(404, 'No lyrics for track %s' % track_id)
            log.logException(e, txt='Error getting lyrics for track %s' % track_id)
        finally:
            session = None

    def send_mpd_manifest(self, mpd_data):
        # mpd_data is the base64 encoded MPD manifest
        # This call returns the MPD data to play with inputstream.adaptive addon
        mpd_xml = base64.b64decode(mpd_data)
        if xbmcaddon.Addon(__addon_id__).getSetting('debug_json') == 'true':
            log.info("MPD-Data: %s" % mpd_xml)
        self.send_response(200)
        self._send_headers(content_type='application/dash+xml', content_length=len(mpd_xml))
        self.wfile.write(mpd_xml)

    def send_m3u8_playlist(self, mpd_data):
        # mpd_data is the base64 encoded MPD manifest
        # Convert the MPD data into an M3U8 HLS playlist to play with inputstream.ffmpegdirect
        hls = DashInfo.fromBase64(mpd_data)
        if not hls:
            self.send_error(501, 'MPD contains invalid data')
            return
        if xbmcaddon.Addon(__addon_id__).getSetting('debug_json') == 'true':
            log.info("M3U8-Data: %s" % hls.m3u8())
        m3u8 = hls.m3u8().encode("utf-8")
        self.send_response(200)
        self._send_headers(content_type='application/vnd.apple.mpegurl', content_length=len(m3u8))
        self.wfile.write(m3u8)

    def send_login_page(self):
        try:
            try:
                msg = _T(Msg.i30282)
                settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
                if settings.access_token and settings.expire_time:
                    msg = _T(Msg.i30022) + ' %s' % settings.expire_time
            except:
                traceback.print_exc()
            html = Pages().login_page(settings, msg).encode('utf-8')
            del settings
            self.send_response(200)
            self._send_headers(content_type='text/html;charset=utf-8')
            self.wfile.write(html)
        except:
            self.send_error(404, 'Failed to start OAuth login')
            traceback.print_exc()

    def send_login_page2(self, client_id, client_secret):
        try:
            try:
                linkurl = _T(Msg.i30253)
                footer = '&nbsp;'
                settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
                session = Session(config=settings)
                if settings.client_name:
                    # Use ID and secret from the TIDAL APK 
                    client_id = ''
                    client_secret = ''
                    settings.init()
                else:
                    # Reset the authentication settings and use the given client_id and secret
                    settings.client_name = ''
                    settings.init(client_name='', client_id=client_id, client_secret=client_secret)
                    settings.save_client()
                settings.save_session()
            except Exception as e:
                self.send_error(404, 'Failed to start OAuth login')
                log.logException(e, 'Failed to set new client id and secret')
                traceback.print_exc()
                return
            try:
                xbmc.executebuiltin('RunPlugin(%s)' % plugin.url_for_path('/home'), wait=True)
                code = session.login_part1(client_id, client_secret)
                linkurl = code.verificationUriComplete
                xbmc.executebuiltin('RunPlugin(%s)' % plugin.url_with_qs('/login_device_code', **vars(code)))
            except Exception as e:
                log.logException(e, 'Failed to get login url with device code')
                try:
                    footer = '%s' % e.response.json().get('error_description')
                except:
                    footer = '%s' % e
            html = Pages().code_link_page(settings, linkurl, footer=footer).encode('utf-8')
            try:
                session.cleanup() # Cleanup TIDAL session object
                session = None
            except:
                pass
            del settings
            self.send_response(200)
            self._send_headers(content_type='text/html;charset=utf-8')
            self.wfile.write(html)
        except:
            self.send_error(404, 'Failed to start OAuth login')
            traceback.print_exc()


class LocalHTTPServer(HTTPServer):

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        HTTPServer.allow_reuse_address = True
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)
        self.socket.settimeout(float(2))
        self.timeout = 2
        self.enable_messages = True
        # Cache for the last Fanart (because Kodi calls the same URL multiple times)
        self.last_fanart_ids = ''
        self.last_fanart_data = b''

    def process_request(self, request, client_address):
        try:
            # Avoid Broken-Pipe errors in error log
            HTTPServer.process_request(self, request, client_address)
        except:
            pass

    def serve_forever(self, poll_interval=0.5):
        log.info('Starting HTTP-Server ...')
        HTTPServer.serve_forever(self, poll_interval=poll_interval)
        log.info('HTTP-Server terminated.')

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
                self.http_server.enable_messages = self.settings.debug_json
            except:
                log.error('HTTP Server not startet on port %d' % self.settings.fanart_server_port)
                self.http_server = LocalHTTPServer(('', 0), LocalHttpRequestHandler)
                self.settings.setSetting('fanart_server_port', '%d' % self.http_server.server_address[1])
            self.http_thread = Thread(target=self.http_server.serve_forever)
            self.http_thread.start()
            log.info('HTTP Server started on port %d' % self.http_server.server_address[1])
        else:
            log.warning('HTTP Server already running')

    def _stop_servers(self):
        try:
            if self.http_server != None and self.http_thread != None:
                log.info('Stopping HTTP Server ...')
                self.http_server.shutdown()
                self.http_server.server_close()
                self.http_thread.join(5)
                log.info('Stopped HTTP Server')
        except Exception as e:
            log.logException(e, 'Failed to stop HTTP Server')
        finally:
            self.http_server = None
            self.http_thread = None

    def onSettingsChanged(self):
        xbmc.Monitor.onSettingsChanged(self)
        self.settings = TidalConfig(tidal_addon=xbmcaddon.Addon(__addon_id__))
        if self.http_server:
            self.http_server.enable_messages = self.settings.debug_json

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

    html = {
        'css':
            'body { background: #141718; }\n'
            'h5 { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; font-weight: 600; width: 615px; height: 20px;\n'
            '     background: #0f84a5; padding: 5px 30px 5px 30px; border: 5px solid #0f84a5; margin: 0px; }\n'
            'span { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; display: block; float: left; width: 615px; }\n'
            'big { font-family: Arial, Helvetica, sans-serif; font-size: 32px; color: #fff; height: 36px; }\n'
            'small { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #fff; }\n'
            'a:link { color: #fff; }\n'
            'a:visited { color: #fff; }\n'
            '.center { margin: auto; width: 615px; padding: 10px; }\n'
            '.textcenter { margin: auto; width: 615px; padding: 10px; text-align: center; }\n'
            '.content { width: 615px; height: 220px; background: #1a2123; padding: 30px 30px 15px 30px; border: 5px solid #1a2123; }\n'
            '.config_form { width: 615px; height: 220px; font-size: 16px; background: #1a2123;  padding: 30px 30px 15px 30px; border: 5px solid #1a2123; }\n'
            '.config_form input[type=submit],\n'
            '.config_form input[type=button],\n'
            '.config_form input[type=text],\n'
            '.config_form textarea,\n'
            '.config_form label { font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #fff; }\n'
            '.config_form label { display:block; margin-bottom: 10px; }\n'
            '.config_form label > span { display: inline-block; float: left; width: 140px; }\n'
            '.config_form input[type=text] { background: transparent; border: none; border-bottom: 1px solid #147a96; width: 440px; outline: none; padding: 0px 0px 0px 0px; }\n'
            '.config_form input[type=text]:focus { border-bottom: 1px dashed #0f84a5; }\n'
            '.config_form input[type=submit],\n'
            '.config_form input[type=button] { width: 210px; background: #141718; border: none; padding: 8px 0px 8px 10px; border-radius: 5px; color: #fff; margin-top: 10px }\n'
            '.config_form input[type=submit]:hover,\n'
            '.config_form input[type=button]:hover { background: #0f84a5; }\n',

        'login_page':
            '<!doctype html>\n<html>\n'
            '<head>\n\t<meta charset="utf-8">\n'
            '  <title>{title}</title>\n'
            '  <style>\n{css}\t</style>\n'
            '</head>\n<body>\n'
            '  <div class="center">\n'
            '  <h5>{header}</h5>\n'
            '  <form action="/login_step2" class="config_form" autocomplete="off">\n'
            '    <label for="client_name">\n'
            '    <span>{client_name_head}°</span>{client_name_value}&nbsp;\n'
            '    </label>\n'
            '    <label for="client_id">\n'
            '    <span>{client_id_head}</span><input type="{d}" name="client_id" value="{client_id_value}" size="50" {required}/>\n'
            '    </label>\n'
            '    <label for="client_secret">\n'
            '    <span>{client_secret_head}</span><input type="{d}" name="client_secret" value="{client_secret_value}" size="50"/>\n'
            '    </label>\n'
            '    <label for="msg">\n'
            '    <span>{msg_head}</span>{msg_text}\n'
            '    <br><br>{remark}\n'
            '    </label>\n'
            '    <input type="submit" value="{submit}"><br>\n'
            '  </form>\n'
            '  </div>\n'
            '</body>\n</html>',

        'ok_page':
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

    def css(self, width=615, height=220, label_width=140):
        substrings = [ ['615px', '%spx' % width],
                       ['220px', '%spx' % height],
                       ['140px', '%spx' % label_width],
                       ['440px', '%spx' % (width - label_width - 20)] ]
        html = self.html['css']
        for s in substrings: html = html.replace(s[0], s[1])
        return html

    def login_page(self, settings, msg):
        # Prepare login screen
        html = self.html['login_page']
        html = html.format(css=self.css(), title=settings.getAddonInfo('name'), header=_T(Msg.i30280),
                           client_name_head=_T(Msg.i30028),
                           client_name_value=settings.client_name,
                           client_id_head='' if settings.client_name else _T(Msg.i30026),
                           client_id_value='' if settings.client_name else settings.client_id,
                           required='' if settings.client_name else 'required',
                           client_secret_head='' if settings.client_name else _T(Msg.i30009),
                           client_secret_value='' if settings.client_name else settings.client_secret,
                           remark= _T(Msg.i30287) if settings.client_name else _T(Msg.i30288),
                           d='hidden' if settings.client_name else 'text',
                           submit=_T(Msg.i30208),  msg_head=_T(Msg.i30281), msg_text=msg)
        return html

    def code_link_page(self, settings, url, footer='&nbsp;'):
        html = self.html['ok_page']
        if url.lower().startswith('http'):
            redirect = '<a href="{url}">{url}</a>'
        else:
            redirect = '{url}'
        html = html.format(css=self.css(), title=settings.getAddonInfo('name'), header=_T(Msg.i30280),
                           line1=_T(Msg.i30209),
                           line2='&nbsp;',
                           line3='&nbsp;',
                           line4=redirect.format(url=url),
                           footer=footer)
        return html

# End of File