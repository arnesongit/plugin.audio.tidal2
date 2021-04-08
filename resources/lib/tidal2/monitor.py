# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Arne Svenson
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
from threading import Thread
try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except:
    # Python 2.7
    from urlparse import urlparse, parse_qs

try:
    # for Python 3
    from http.server import BaseHTTPRequestHandler, HTTPServer
except:
    # Python 2.7
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from kodi_six import xbmc, xbmcgui

from .textids import Msg, _T
from .debug import log
from .config import settings
from .koditidal import LoginToken, Quality
from .tidalapi import Session

#------------------------------------------------------------------------------
# HTTP Server for Images
#------------------------------------------------------------------------------

class LocalHttpRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            url = urlparse(self.path)
            params = parse_qs(url.query)
            if 'id' not in params:
                self.send_error(404, 'No id')
            elif url.path == '/artist_fanart':
                artist = Session().get_artist(params['id'][0])
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
            else:
                self.send_error(404, 'Wrong call: %s' % self.path)
        except:
            self.send_error(404, 'Request failed')

    def log_message(self, *args):
        # Disable the BaseHTTPServer Log
        pass


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
        self.config = settings
        self.setLastSettings()
        self.http_server = None
        self.http_thread = None

    def __del__(self):
        log.info('TidalMonitor() Object destroyed.')

    def _start_servers(self):
        if self.http_server == None and self.http_thread == None:
            try:
                self.http_server = LocalHTTPServer(('', self.config.fanart_server_port), LocalHttpRequestHandler)
            except:
                log.error('Fanart Server not startet on port %d' % self.config.fanart_server_port)
                self.http_server = LocalHTTPServer(('', 0), LocalHttpRequestHandler)
                self.config.setSetting('fanart_server_port', '%d' % self.http_server.server_address[1])
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
                #self.http_server.server_close()
                self.http_server.shutdown()
                self.http_thread.join()
                log.info('Stopped Fanart Server')
        except:
            log.error('Failed to stop Fanart Server')
        finally:
            self.http_server = None
            self.http_thread = None

    def setLastSettings(self):
        self.last_session_token_name = self.config.session_token_name
        self.last_stream_token_name = self.config.stream_token_name
        self.last_codec = self.config.codec
        self.last_quality = self.config.quality

    def reloginNeeded(self):
        # Check if the login session tokens matches to the Streaming Settings
        try:
            fanart_server_enabled = self.config.fanart_server_enabled
            fanart_server_port = self.config.fanart_server_port
            self.config.load()
            if self.config.fanart_server_enabled:
                if self.config.fanart_server_port != fanart_server_port or not fanart_server_enabled:
                    self._stop_servers()
                    self._start_servers()
            else:
                self._stop_servers()
            if self.last_session_token_name == self.config.session_token_name and \
               self.last_stream_token_name == self.config.stream_token_name and \
               self.last_codec == self.config.codec and \
               self.last_quality == self.config.quality:
                log.info('No Streaming Options changed.')
                return False
            self.setLastSettings()
            if self.config.session_id and self.config.user_id and not self.config.session_token_name and not self.config.stream_token_name:
                log.info('Old Version < 2.0.0-beta13 without Token Names. Relogin needed.')
                return True
            if not self.config.session_id or not self.config.user_id or not self.config.session_token_name or not self.config.stream_token_name:
                log.info('Not logged in.')
                return False
            stream_features = LoginToken.getFeatures(self.config.stream_token_name)
            codec = 'AAC' if self.config.quality != Quality.lossless else self.config.codec
            if codec not in stream_features.get('codecs'):
                log.info('Changes to Codec needs Relogin.')
                return True
        except:
            pass
        log.info('No Relogin needed.')
        return False

    def onSettingsChanged(self):
        xbmc.Monitor.onSettingsChanged(self)
        if self.reloginNeeded():
            if xbmcgui.Dialog().yesno(heading=self.config.getAddonInfo('name'), line1=_T(Msg.i30256), line2=_T(Msg.i30257)):
                xbmc.executebuiltin('RunPlugin(plugin://%s/login)' % self.config.getAddonInfo('id'))
            pass

    def run(self):
        log.info('TidalMonitor: Service Started')
        self._start_servers()
        wait_time = 5
        while not self.abortRequested():
            if self.waitForAbort(wait_time):
                break
        self._stop_servers()
        log.info('TidalMonitor: Service Terminated')
        # Cleanup for Garbage Collector
        self.config = None

# End of File