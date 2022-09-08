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

import os
import datetime
import base64
import pyaes

from kodi_six import xbmc, xbmcvfs

from .common import addon, Const, getLocale, isAddonInstalled
from .tidalapi.models import Config, Quality, Model

#------------------------------------------------------------------------------
# Configuration Class
#------------------------------------------------------------------------------

class TidalConfig(Config):

    def __init__(self, tidal_addon=None):
        Config.__init__(self)
        self.addon = tidal_addon if tidal_addon else addon
        self.load()

    def init(self, **kwargs):
        if self.client_name:
            # Re-Encode Client-ID and Secret
            old_secret = self.token_secret
            self.refresh_token = ''
            self.client_name = self.client_name
            self.client_id = base64.b64encode(pyaes.AESModeOfOperationCTR(self.token_secret).encrypt(pyaes.AESModeOfOperationCTR(old_secret).decrypt(base64.b64decode(self.client_id)))).decode('utf-8')
            if self.client_secret:
                self.client_secret = base64.b64encode(pyaes.AESModeOfOperationCTR(self.token_secret).encrypt(pyaes.AESModeOfOperationCTR(old_secret).decrypt(base64.b64decode(self.client_secret)))).decode('utf-8')
            self.save_client()
        Config.init(self, **kwargs)

    def getSetting(self, setting):
        return self.addon.getSetting(setting)

    def setSetting(self, setting, value):
        self.addon.setSetting(setting, value)

    def getAddonInfo(self, val):
        return self.addon.getAddonInfo(val)

    def load(self):
        self.album_playlist_tag = 'ALBUM'

        self.cache_dir = Const.addon_profile_path
        self.favorites_file = os.path.join(self.cache_dir, 'favorites.cfg')
        self.locked_artist_file = os.path.join(self.cache_dir, 'locked_artists.cfg')
        self.playlist_file = os.path.join(self.cache_dir, 'playlists.cfg')
        self.folders_file = os.path.join(self.cache_dir, 'folders.cfg')

        self.default_trackplaylist_id = self.getSetting('default_trackplaylist_id')
        self.default_videoplaylist_id = self.getSetting('default_videoplaylist_id')
        self.default_albumplaylist_id = self.getSetting('default_albumplaylist_id')
        self.default_folder_id = self.getSetting('default_folder_id')

        self.default_trackplaylist_title = self.getSetting('default_trackplaylist_title')
        self.default_videoplaylist_title = self.getSetting('default_videoplaylist_title')
        self.default_albumplaylist_title = self.getSetting('default_albumplaylist_title')
        self.default_folder_name = self.getSetting('default_folder_name')

        self.unplayable_m4a = os.path.join(self.getAddonInfo('path'), 'resources', 'media', 'unplayable.m4a')

        self.handle_deprecated_settings()

        # Tidal User Settings
        self.user_id = self.getSetting('user_id')
        self.country_code = self.getSetting('country_code')
        self.subscription_type = self.getSetting('subscription_type')
        self.user_country_code = self.getSetting('user_country_code')
        if not self.user_country_code and self.country_code:
            self.user_country_code = self.country_code
            self.setSetting('user_country_code', self.country_code)
        self.enable_lyrics = True if self.getSetting('enable_lyrics') == 'true' else False

        # Set playback modes for MPD Dash streams
        self.dash_aac_mode = [Const.is_hls, Const.is_adaptive, Const.is_ffmpegdirect][min(2,int('0%s' % self.getSetting('dash_aac_mode')))]
        self.dash_flac_mode = [Const.is_hls, Const.is_ffmpegdirect][min(1,int('0%s' % self.getSetting('dash_flac_mode')))]
        self.ffmpegdirect_has_mpd = True if self.getSetting('ffmpegdirect_has_mpd') == 'true' else False

        # Determine the locale of the system
        self.locale = getLocale(self.country_code)

        self.use_drm = True if self.getSetting('use_drm') == 'true' else False
        self.client_name = self.getSetting('client_name')
        self.client_id = self.getSetting('client_id')
        self.client_secret = self.getSetting('client_secret')
        self.token_type = self.getSetting('token_type')
        self.access_token = self.getSetting('access_token')
        self.refresh_token = self.getSetting('refresh_token')
        self.login_time = Model().parse_date(self.getSetting('login_time'))
        if not self.login_time:
            self.login_time = datetime.datetime.now()
        self.refresh_time = Model().parse_date(self.getSetting('refresh_time'))
        if not self.refresh_time:
            self.refresh_time = self.login_time
        self.expire_time = Model().parse_date(self.getSetting('expire_time'))
        if not self.expire_time:
            self.expire_time = self.refresh_time + datetime.timedelta(seconds=604800)

        # Options
        self.quality = [Quality.hi_res, Quality.lossless, Quality.high, Quality.low][min(3, int('0' + self.getSetting('quality')))]
        self.maxVideoHeight = [9999, 1080, 720, 540, 480, 360, 240, 0][min(7, int('0%s' % self.getSetting('video_quality')))]
        self.pageSize = max(10, min(9999, int('0%s' % self.getSetting('page_size'))))
        self.debug = True if self.getSetting('debug_log') == 'true' else False
        self.debug_json = True if self.getSetting('debug_json') == 'true' else False

        # Extended Options
        self.ffmpegdirect_is_default_player = True if self.getSetting('ffmpegdirect_is_default') == 'true' else False
        self.color_mode = True if self.getSetting('color_mode') == 'true' else False
        self.favorites_in_labels = True if self.getSetting('favorites_in_labels') == 'true' else False
        self.user_playlists_in_labels = True if self.getSetting('user_playlists_in_labels') == 'true' else False
        self.album_year_in_labels = True if self.getSetting('album_year_in_labels') == 'true' else False
        self.mqa_in_labels = True if self.getSetting('mqa_in_labels') == 'true' else False
        self.set_playback_info = True if self.getSetting('set_playback_info') == 'true' else False
        self.fanart_server_enabled = True
        self.fanart_server_port = int('0%s' % self.getSetting('fanart_server_port'))

    @property
    def token_secret(self):
        if len(self.refresh_token) >= 35:
            return self.refresh_token[3:35].encode('utf-8')
        return Config.token_secret.fget(self)

    def handle_deprecated_settings(self):
        # Delete or convert deprecated settings values from older addon versions
        if self.getSetting('username') != '': self.setSetting('username', '')
        if self.getSetting('password') != '': self.setSetting('password', '')
        if self.getSetting('session_token_name') != '':
            self.setSetting('client_unique_key', '')
            self.setSetting('session_token_name', '')
            self.setSetting('session_id', '')
            self.setSetting('stream_token_name', '')
            self.setSetting('stream_session_id', '')
            self.setSetting('video_token_name', '')
            self.setSetting('video_session_id', '')
            if xbmcvfs.exists(self.playlist_file):
                xbmcvfs.delete(self.playlist_file)
            if xbmcvfs.exists(self.favorites_file):
                xbmcvfs.delete(self.favorites_file)
        if self.getSetting('preview_token'):
            self.setSetting('preview_token', '')
        if not self.getSetting('user_country_code'):
            # New in V2.1.1: Test if inputstream.adaptive or inputstream.ffmpegdirect is installed
            # To overwrite the default value which uses HLS converter to play the streams
            if isAddonInstalled(Const.is_adaptive):
                self.setSetting('dash_aac_mode', '1')
            if isAddonInstalled(Const.is_ffmpegdirect):
                self.setSetting('dash_flac_mode', '1')
                if xbmc.getCondVisibility('system.platform.windows') or xbmc.getCondVisibility('system.platform.osx'):
                    self.setSetting('ffmpegdirect_has_mpd', 'true')
                if xbmc.getCondVisibility('system.platform.windows') or xbmc.getCondVisibility('system.platform.android'):
                    self.setSetting('ffmpegdirect_is_default', 'true')
            pass


    def save_client(self):
        settings.setSetting('client_name', self.client_name)
        settings.setSetting('client_id', self.client_id)
        settings.setSetting('client_secret', self.client_secret)

    def save_session(self):
        settings.setSetting('user_id', '%s' % self.user_id)
        settings.setSetting('country_code', self.country_code)
        settings.setSetting('user_country_code', self.user_country_code)
        settings.setSetting('subscription_type', self.subscription_type)
        settings.setSetting('token_type', self.token_type)
        settings.setSetting('access_token', self.access_token)
        settings.setSetting('refresh_token', self.refresh_token)
        settings.setSetting('login_time',  self.login_time.isoformat())
        settings.setSetting('refresh_time',  self.refresh_time.isoformat())
        settings.setSetting('expire_time',  self.expire_time.isoformat())


#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

settings = TidalConfig()


# End of File