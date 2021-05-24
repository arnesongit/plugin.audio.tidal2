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

from kodi_six import xbmcvfs

from .common import addon, Const, getLocale
from .tidalapi.models import Config, Quality, Model

#------------------------------------------------------------------------------
# Configuration Class
#------------------------------------------------------------------------------

class TidalConfig(Config):

    def __init__(self):
        Config.__init__(self)
        self.load()

    def getSetting(self, setting):
        return addon.getSetting(setting)

    def setSetting(self, setting, value):
        addon.setSetting(setting, value)

    def getAddonInfo(self, val):
        return addon.getAddonInfo(val)

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

        # Determine the locale of the system
        self.locale = getLocale(self.country_code)

        self.client_id = self.getSetting('client_id')
        self.client_secret = self.getSetting('client_secret')
        self.client_unique_key = self.getSetting('client_unique_key')
        self.session_id = self.getSetting('session_id')
        self.preview_token = self.getSetting('preview_token')
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
        self.maxVideoHeight = [9999, 1080, 720, 540, 480, 360, 240][min(6, int('0%s' % self.getSetting('video_quality')))]
        self.pageSize = max(10, min(9999, int('0%s' % self.getSetting('page_size'))))
        self.debug = True if self.getSetting('debug_log') == 'true' else False
        self.debug_json = True if self.getSetting('debug_json') == 'true' else False

        # Extended Options
        self.color_mode = True if self.getSetting('color_mode') == 'true' else False
        self.favorites_in_labels = True if self.getSetting('favorites_in_labels') == 'true' else False
        self.user_playlists_in_labels = True if self.getSetting('user_playlists_in_labels') == 'true' else False
        self.album_year_in_labels = True if self.getSetting('album_year_in_labels') == 'true' else False
        self.mqa_in_labels = True if self.getSetting('mqa_in_labels') == 'true' else False
        self.set_playback_info = True if self.getSetting('set_playback_info') == 'true' else False
        self.fanart_server_enabled = True if self.getSetting('fanart_server_enabled') == 'true' else False
        self.fanart_server_port = int('0%s' % self.getSetting('fanart_server_port'))

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

    def save_session(self):
        settings.setSetting('user_id', '%s' % self.user_id)
        settings.setSetting('country_code', self.country_code)
        settings.setSetting('subscription_type', self.subscription_type)
        settings.setSetting('session_id', self.session_id)
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