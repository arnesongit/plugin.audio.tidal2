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

import os

from .common import addon, Const
from .tidalapi.models import Config, SubscriptionType, Quality

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
        # Addon Info
        self.album_playlist_tag = 'ALBUM'

        self.cache_dir = Const.addon_profile_path
        self.favorites_file = os.path.join(self.cache_dir, 'favorites.cfg')
        self.locked_artist_file = os.path.join(self.cache_dir, 'locked_artists.cfg')
        self.playlist_file = os.path.join(self.cache_dir, 'playlists.cfg')

        self.default_trackplaylist_id = self.getSetting('default_trackplaylist_id')
        self.default_videoplaylist_id = self.getSetting('default_videoplaylist_id')
        self.default_albumplaylist_id = self.getSetting('default_albumplaylist_id')

        self.default_trackplaylist_title = self.getSetting('default_trackplaylist_title')
        self.default_videoplaylist_title = self.getSetting('default_videoplaylist_title')
        self.default_albumplaylist_title = self.getSetting('default_albumplaylist_title')

        self.unplayable_m4a = os.path.join(self.getAddonInfo('path'), 'resources', 'media', 'unplayable.m4a')

        # Determine the locale of the system
        self.locale = Const.locale

        # Tidal User Settings
        self.session_id = self.getSetting('session_id')
        self.session_token_name = self.getSetting('session_token_name')
        self.stream_session_id = self.getSetting('stream_session_id')
        self.stream_token_name = self.getSetting('stream_token_name')
        if not self.stream_session_id:
            self.stream_session_id = self.session_id
            self.stream_token_name = self.session_token_name
        self.video_session_id = self.getSetting('video_session_id')
        self.video_token_name = self.getSetting('video_token_name')
        if not self.video_session_id:
            self.video_session_id = self.stream_session_id
            self.video_token_name = self.stream_token_name
        self.country_code = self.getSetting('country_code')
        self.user_id = self.getSetting('user_id')
        self.subscription_type = [SubscriptionType.hifi, SubscriptionType.premium][min(1, int('0' + self.getSetting('subscription_type')))]
        self.client_unique_key = self.getSetting('client_unique_key')

        # Options
        self.quality = [Quality.lossless, Quality.high, Quality.low][min(2, int('0' + self.getSetting('quality')))]
        self.codec = ['FLAC', 'AAC', 'AAC'][min([2, int('0' + self.getSetting('quality'))])]
        if self.getSetting('music_option') == '1' and self.quality == Quality.lossless:
            self.codec = 'ALAC'
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
        self.fanart_server_enabled = True if self.getSetting('fanart_server_enabled') == 'true' else False
        self.fanart_server_port = int('0%s' % self.getSetting('fanart_server_port'))


#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

settings = TidalConfig()


# End of File