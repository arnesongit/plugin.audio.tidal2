# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Arne Svenson
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

from __future__ import unicode_literals

import xbmc, xbmcgui

from resources.lib.koditidal2 import TidalConfig2
from resources.lib.koditidal import LoginToken, Quality, debug, addon, _T

log = debug.log

#------------------------------------------------------------------------------
# Service 
#------------------------------------------------------------------------------

class MyMonitor(xbmc.Monitor):

    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self, *args, **kwargs)
        self.config = TidalConfig2()
        self.setLastSettings()

    def setLastSettings(self):
        self.last_session_token_name = self.config.session_token_name
        self.last_stream_token_name = self.config.stream_token_name
        self.last_codec = self.config.codec
        self.last_rtmp = self.config.use_rtmp
        self.last_quality = self.config.quality
        self.last_force_http = self.config.forceHttpVideo

    def reloginNeeded(self):
        # Check if the login session tokens matches to the Streaming Settings
        try:
            self.config.load()
            if self.last_session_token_name == self.config.session_token_name and \
               self.last_stream_token_name == self.config.stream_token_name and \
               self.last_codec == self.config.codec and \
               self.last_rtmp == self.config.use_rtmp and \
               self.last_quality == self.config.quality and \
               self.last_force_http == self.config.forceHttpVideo:
                log('No Streaming Options changed.')
                return False
            self.setLastSettings()
            if self.config.session_id and self.config.user_id and not self.config.session_token_name and not self.config.stream_token_name:
                log('Old Version < 2.0.0-beta13 without Token Names. Relogin needed.')
                return True
            if not self.config.session_id or not self.config.user_id or not self.config.session_token_name or not self.config.stream_token_name:
                log('Not logged in.')
                return False
            api_features = LoginToken.getFeatures(self.config.session_token_name)
            stream_features = LoginToken.getFeatures(self.config.stream_token_name)
            if self.config.forceHttpVideo and api_features.get('videoMode') <> 'HTTP':
                log('Changed HTTP Streaming mode. Relogin needed.')
                return True
            codec = 'AAC' if self.config.quality <> Quality.lossless else self.config.codec
            if codec not in stream_features.get('codecs'):
                log('Changes to Codec needs Relogin.')
                return True
            if self.config.use_rtmp and self.config.codec == 'AAC' and not stream_features.get('rtmp'):
                log('RTMP-Protocol needs Relogin to work.')
                return True
            if not self.config.use_rtmp and self.config.codec == 'AAC' and stream_features.get('rtmp'):
                log('Relogin needed to switch off RTMP-Protocol.')
                return True
        except:
            pass
        log('No Relogin needed.')
        return False

    def onSettingsChanged(self):
        xbmc.Monitor.onSettingsChanged(self)
        if self.reloginNeeded():
            if xbmcgui.Dialog().yesno(heading=addon.getAddonInfo('name'), line1=_T(30256), line2=_T(30257)):
                xbmc.executebuiltin('XBMC.RunPlugin(plugin://%s/login)' % addon.getAddonInfo('id'))
            pass

    def run(self):
        log('MyMonitor: Service Started')
        wait_time = 10
        while not self.abortRequested():
            if self.waitForAbort(wait_time):
                break
        log('MyMonitor: Service Terminated')

#------------------------------------------------------------------------------
# Service 
#------------------------------------------------------------------------------

if __name__ == "__main__":

    monitor = MyMonitor()
    monitor.run()

# End of File