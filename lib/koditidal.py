# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Arne Svenson
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

import os, sys, re
import logging
from urlparse import urlsplit
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
from xbmcgui import ListItem
from routing import Plugin
from tidalapi import Config, Session
from tidalapi.models import Quality, SubscriptionType, BrowsableMedia, Artist, Album, PlayableMedia, Track, Video, Playlist, Promotion, Category
from m3u8 import load as m3u8_load


addon = xbmcaddon.Addon()
plugin = Plugin()
plugin.name = addon.getAddonInfo('name')

_addon_id = addon.getAddonInfo('id')
_addon_icon = os.path.join(addon.getAddonInfo('path'), 'icon.png')
_addon_fanart = os.path.join(addon.getAddonInfo('path'), 'fanart.jpg')

DEBUG_LEVEL = xbmc.LOGSEVERE

def log(msg, level=DEBUG_LEVEL):
    xbmc.log(("[%s] %s" % (plugin.name, msg)).encode('utf-8'), level=level)


def _T(txtid):
    if isinstance(txtid, basestring):
        # Map TIDAL texts to Text IDs
        newid = {'artist':  30101, 'album':  30102, 'playlist':  30103, 'track':  30104, 'video':  30105, 
                 'artists': 30101, 'albums': 30102, 'playlists': 30103, 'tracks': 30104, 'videos': 30105,
                 'featured': 30203, 'rising': 30211, 'discovery': 30212, 'movies': 30115, 'shows': 30116, 'genres': 30117, 'moods': 30118
                 }.get(txtid, None)
        if not newid: return txtid
        txtid = newid
    try:
        txt = addon.getLocalizedString(txtid)
        return txt
    except:
        return '%s' % txtid


def _P(key, default_txt=None):
    # Plurals of some Texts
    newid = {'new': 30111, 'local': 30112, 'exclusive': 30113, 'recommended': 30114, 'top': 30119,
             'artists': 30106, 'albums': 30107, 'playlists': 30108, 'tracks': 30109, 'videos': 30110
             }.get(key, None)
    if newid:
        return _T(newid)
    return default_txt if default_txt else key

# Convert TIDAL-API Media into Kodi List Items

class HasListItem(object):

    _is_logged_in = False

    def getLabel(self):
        return self.name

    def getListItem(self):
        li = ListItem(self.getLabel())
        if isinstance(self, PlayableMedia) and getattr(self, 'available', True):
            li.setProperty('isplayable', 'true')
        artwork = {'thumb': _addon_icon, 'fanart': _addon_fanart}
        if getattr(self, 'image', None):
            artwork['thumb'] = self.image
        if getattr(self, 'fanart', None):
            artwork['fanart'] = self.fanart
        li.setArt(artwork)
        # In Favorites View everything is a Favorite
        if self._is_logged_in and hasattr(self, '_isFavorite') and '/favorites/' in sys.argv[0]:
            self._isFavorite = True
        cm = self.getContextMenuItems()
        if len(cm) > 0:
            li.addContextMenuItems(cm)
        return li

    def getContextMenuItems(self):
        return []


class AlbumItem(Album, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem(self.artist)
        self.artists = [ArtistItem(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem(artist) for artist in self._ftArtists]

    def getLabel(self):
        label = '%s - %s' % (self.artist.name, self.title)
        if getattr(self, 'year', None):
            label += ' (%s)' % self.year
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/album/%s' % self.id)
        li.setInfo('music', {
            'title': self.title, 
            'album': self.title, 
            'artist': self.artist.name,
            'year': getattr(self, 'year', None),
            'tracknumber': self._itemPosition + 1 if self._itemPosition >= 0 else 0
        })
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/albums/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/albums/%s' % self.id)))
        cm.append((_T(30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        return cm


class ArtistItem(Artist, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        return self.name

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/artist/%s' % self.id)
        li.setInfo('music', {'artist': self.name})
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/artists/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/artists/%s' % self.id)))
        return cm


class PlaylistItem(Playlist, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        return self.name

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/playlist/%s' % self.id)
        li.setInfo('music', {
            'artist': self.title,
            'album': self.description,
            'title': _T(30243).format(tracks=self.numberOfTracks, videos=self.numberOfVideos),
            'tracknumber': self._itemPosition + 1 if self._itemPosition >= 0 else 0
        })
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self.type == 'USER':
                cm.append((_T(30235), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/delete/%s' % self.id)))
            else:
                if self._isFavorite:
                    cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/playlists/%s' % self.id)))
                else:
                    cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/playlists/%s' % self.id)))
            cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/playlist/%s' % self.id)))
        return cm

    @property
    def image(self):
        if self.type == 'USER':
            # Add Timestamp to URL to refresh Image in Kodi Thumbnail Cache
            return super(PlaylistItem, self).image + '&dummy=%s' % self.lastUpdated
        return super(PlaylistItem, self).image

    @property
    def fanart(self):
        if self.type == 'USER':
            # Add Timestamp to URL to refresh Image in Kodi Thumbnail Cache
            return super(PlaylistItem, self).fanart + '&dummy=%s' % self.lastUpdated
        return super(PlaylistItem, self).fanart


class TrackItem(Track, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem(self.artist)
        self.artists = [ArtistItem(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem(artist) for artist in self._ftArtists]
        self.album = AlbumItem(self.album)
        if self.explicit and not 'Explicit' in self.title:
            self.title += ' (Explicit)'

    def getLabel(self):
        label = '%s - %s' % (self.artist.name, self.title)
        return label

    def getFtArtistsText(self):
        text = ''
        for item in self._ftArtists:
            if len(text) > 0:
                text = text + ', '
            text = text + item.name
        if len(text) > 0:
            text = 'ft. by ' + text
        return text

    def getListItem(self):
        li = HasListItem.getListItem(self)
        if self.available:
            url = plugin.url_for_path('/play_track/%s' % self.id)
            isFolder = False
        else:
            url = plugin.url_for_path('/stream_locked')
            isFolder = True
        li.setInfo('music', {
            'title': self.title,
            'tracknumber': self._playlist_pos + 1 if self._playlist_id else self._itemPosition + 1 if self._itemPosition >= 0 else self.trackNumber,
            'discnumber': self.volumeNumber,
            'duration': self.duration,
            'artist': self.artist.name,
            'album': self.album.title,
            'year': getattr(self, 'year', None),
            'rating': '%s' % int(round(self.popularity / 20.0)),
            'comment': self.getFtArtistsText()
        })
        return (url, li, isFolder)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/tracks/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/tracks/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(30240), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
            else:
                cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/track/%s' % self.id)))
        cm.append((_T(30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        cm.append((_T(30245), 'Container.Update(%s)' % plugin.url_for_path('/album/%s' % self.album.id)))
        cm.append((_T(30222), 'Container.Update(%s)' % plugin.url_for_path('/track_radio/%s' % self.id)))
        cm.append((_T(30223), 'Container.Update(%s)' % plugin.url_for_path('/recommended/tracks/%s' % self.id)))
        return cm


class VideoItem(Video, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem(self.artist)
        self.artists = [ArtistItem(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem(artist) for artist in self._ftArtists]
        if self.explicit and not 'Explicit' in self.title:
            self.title += ' (Explicit)'

    def getLabel(self):
        label = '%s - %s' % (self.artist.name, self.title)
        return label

    def getFtArtistsText(self):
        text = ''
        for item in self._ftArtists:
            if len(text) > 0:
                text = text + ', '
            text = text + item.name
        if len(text) > 0:
            text = 'ft. by ' + text
        return text

    def getListItem(self):
        li = HasListItem.getListItem(self)
        if self.available:
            url = plugin.url_for_path('/play_video/%s' % self.id)
            isFolder = False
        else:
            url = plugin.url_for_path('/stream_locked')
            isFolder = True
        li.setInfo('video', {
            'artist': [self.artist.name],
            'title': self.title,
            'tracknumber': self._playlist_pos + 1 if self._playlist_id else self._itemPosition + 1,
            'year': getattr(self, 'year', None),
            'plotoutline': self.getFtArtistsText()
        })
        li.addStreamInfo('video', { 'codec': 'h264', 'aspect': 1.78, 'width': 1920,
                         'height': 1080, 'duration': self.duration })
        li.addStreamInfo('audio', { 'codec': 'AAC', 'language': 'en', 'channels': 2 })
        return (url, li, isFolder)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/videos/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/videos/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(30240), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
            else:
                cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/video/%s' % self.id)))
        cm.append((_T(30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        cm.append((_T(30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class PromotionItem(Promotion, HasListItem):

    def __init__(self, item):
        if item.type != 'EXTURL' and item.id.startswith('http:'):
            item.type = 'EXTURL' # Fix some defect TIDAL Promotions
        self.__dict__.update(vars(item))

    def getLabel(self):
        if self.type in ['ALBUM', 'VIDEO']:
            return '%s - %s' % (self.shortHeader, self.shortSubHeader)
        return self.shortHeader

    def getListItem(self):
        li = HasListItem.getListItem(self)
        isFolder = True
        if self.type == 'PLAYLIST':
            url = plugin.url_for_path('/playlist/%s' % self.id)
        elif self.type == 'ALBUM':
            url = plugin.url_for_path('/album/%s' % self.id)
            li.setInfo('music', {
                'artist': self.shortHeader,
                'album': self.shortSubHeader,
                'title': self.shortSubHeader
            })
        elif self.type == 'VIDEO':
            url = plugin.url_for_path('/play_video/%s' % self.id)
            li.setInfo('video', {
                'artist': [self.shortHeader],
                'title': self.shortSubHeader
            })
            li.setProperty('isplayable', 'true')
            isFolder = False
            li.addStreamInfo('video', { 'codec': 'h264', 'aspect': 1.78, 'width': 1920,
                             'height': 1080, 'duration': self.duration })
            li.addStreamInfo('audio', { 'codec': 'AAC', 'language': 'en', 'channels': 2 })
        else:
            return (None, None, False)
        return (url, li, isFolder)

    def getContextMenuItems(self):
        cm = []
        if self.type == 'PLAYLIST':
            if self._is_logged_in:
                if self._isFavorite:
                    cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/playlists/%s' % self.id)))
                else:
                    cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/playlists/%s' % self.id)))
        elif self.type == 'ALBUM':
            if self._is_logged_in:
                if self._isFavorite:
                    cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/albums/%s' % self.id)))
                else:
                    cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/albums/%s' % self.id)))
        elif self.type == 'VIDEO':
            if self._is_logged_in:
                if self._isFavorite:
                    cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/videos/%s' % self.id)))
                else:
                    cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/videos/%s' % self.id)))
            cm.append((_T(30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class CategoryItem(Category, HasListItem):

    _force_subfolders = False
    _label = None

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        return self._label

    def getListItems(self):
        content_types = self.content_types
        items = []
        if len(content_types) > 1 and self._group in ['moods', 'genres'] and not self._force_subfolders:
            # Use sub folders for multiple Content Types
            url = plugin.url_for_path('/category/%s/%s' % (self._group, self.path))
            self._label = _P(self.path, self.name)
            li = HasListItem.getListItem(self)
            li.setInfo('music', {
                'artist': self._label
            })
            items.append((url, li, True))
        else:
            for content_type in content_types:
                url = plugin.url_for_path('/category/%s/%s/%s/%s' % (self._group, self.path, content_type, 0))
                if len(content_types) > 1:
                    if self._force_subfolders:
                        # Show only Content Type as sub folders
                        self._label = _P(content_type)
                    else:
                        # Show Path and Content Type as sub folder
                        self._label = '%s %s' % (_P(self.path, self.name), _P(content_type))
                else:
                    # Use Path as folder because content type is shows as sub foldes
                    self._label = _P(self.path, self.name)
                li = HasListItem.getListItem(self)
                li.setInfo('music', {
                    'artist': _P(self.path, self.name),
                    'album': _P(content_type)
                })
                items.append((url, li, True))
        return items


class FolderItem(BrowsableMedia, HasListItem):

    def __init__(self, label, url, thumb=None, fanart=None, isFolder=True):
        self.name = label
        self._url = url
        self._thumb = thumb
        self._fanart = fanart
        self._isFolder = isFolder

    def getLabel(self):
        return self.name

    def getListItem(self):
        li = HasListItem.getListItem(self)
        li.setInfo('music', {
            'artist': self.name
        })
        return (self._url, li, self._isFolder)

    @property
    def image(self):
        return self._thumb if self._thumb else HasListItem.image

    @property
    def fanart(self):
        return self._fanart if self._fanart else HasListItem.fanart


# Session from the TIDAL-API to parse Items into Kodi List Items

class TidalConfig(Config):

    def __init__(self):
        Config.__init__(self)
        self.load()

    def load(self):
        self.session_id = addon.getSetting('session_id')
        self.country_code = addon.getSetting('country_code')
        self.user_id = addon.getSetting('user_id')
        self.subscription_type = [SubscriptionType.hifi, SubscriptionType.premium][int('0' + addon.getSetting('subscription_type'))]
        self.client_unique_key = addon.getSetting('client_unique_key')
        self.quality = [Quality.lossless, Quality.high, Quality.low][int('0' + addon.getSetting('quality'))]
        self.maxVideoHeight = [9999, 1080, 720, 540, 480, 360, 240][int('0%s' % addon.getSetting('video_quality'))]
        self.pageSize = max(10, min(999, int('0%s' % addon.getSetting('page_size'))))


class TidalSession(Session):

    errorCodes = []

    def __init__(self, config=TidalConfig()):
        Session.__init__(self, config=config)

    def load_session(self):
        if not self._config.country_code:
            self._config.country_code = self.local_country_code()
            addon.setSetting('country_code', self._config.country_code)
        Session.load_session(self, self._config.session_id, self._config.country_code, self._config.user_id, 
                             self._config.subscription_type, self._config.client_unique_key)

    def generate_client_unique_key(self):
        unique_key = addon.getSetting('client_unique_key')
        if not unique_key:
            unique_key = Session.generate_client_unique_key(self)
        return unique_key

    def login(self, username, password, subscription_type=None):
        if addon.getSetting('client_unique_key') == '' and subscription_type == SubscriptionType.hifi:
            addon.setSetting('quality', '0') # Switch to Lossless Quality
        ok = Session.login(self, username, password, subscription_type=subscription_type)
        if ok:
            addon.setSetting('session_id', self.session_id)
            addon.setSetting('country_code', self.country_code)
            addon.setSetting('user_id', unicode(self.user.id))
            addon.setSetting('subscription_type', '0' if self.user.subscription.type == SubscriptionType.hifi else '1')
            addon.setSetting('client_unique_key', self.client_unique_key)
        return ok

    def logout(self):
        Session.logout(self)
        addon.setSetting('session_id', '')
        addon.setSetting('user_id', '')

    def get_album_tracks(self, album_id, withAlbum=True):
        items = Session.get_album_tracks(self, album_id)
        if withAlbum:
            album = self.get_album(album_id)
            if album:
                for item in items:
                    item.album = album
        return items

    def _parse_album(self, json_obj, artist=None):
        album = AlbumItem(Session._parse_album(self, json_obj, artist=artist))
        album._is_logged_in = self.is_logged_in
        return album

    def _parse_artist(self, json_obj):
        artist = ArtistItem(Session._parse_artist(self, json_obj))
        artist._is_logged_in = self.is_logged_in
        return artist

    def _parse_playlist(self, json_obj):
        playlist = PlaylistItem(Session._parse_playlist(self, json_obj))
        playlist._is_logged_in = self.is_logged_in
        return playlist

    def _parse_track(self, json_obj):
        track = TrackItem(Session._parse_track(self, json_obj))
        track._is_logged_in = self.is_logged_in
        if not self.is_logged_in and track.duration > 30:
            # 30 Seconds Limit in Trial Mode
            track.duration = 30
        return track

    def _parse_video(self, json_obj):
        video = VideoItem(Session._parse_video(self, json_obj))
        video._is_logged_in = self.is_logged_in
        if not self.is_logged_in and video.duration > 30:
            # 30 Seconds Limit in Trial Mode
            video.duration = 30
        return video

    def _parse_promotion(self, json_obj):
        promotion = PromotionItem(Session._parse_promotion(self, json_obj))
        promotion._is_logged_in = self.is_logged_in
        return promotion

    def _parse_category(self, json_obj):
        return CategoryItem(Session._parse_category(self, json_obj))

    def newPlaylistDialog(self):
        dialog = xbmcgui.Dialog()
        title = dialog.input(_T(30233), type=xbmcgui.INPUT_ALPHANUM)
        item = None
        if title:
            description = dialog.input(_T(30234), type=xbmcgui.INPUT_ALPHANUM)
            item = self.user.create_playlist(title, description)
        return item

    def selectPlaylistDialog(self, headline=None, allowNew=False, item_type=None):
        if not self.is_logged_in:
            return None
        xbmc.executebuiltin("ActivateWindow(busydialog)")
        try:
            if not headline:
                headline = _T(30238)
            items = self.user.playlists()
            dialog = xbmcgui.Dialog()
            item_list = [item.title for item in items]
            if allowNew:
                item_list.append(_T(30237))
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            return None
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        selected = dialog.select(headline, item_list)
        if selected >= len(items):
            item = self.newPlaylistDialog()
            return item
        elif selected >= 0:
            return items[selected]
        return None

    def get_video_url(self, video_id):
        url = Session.get_video_url(self, video_id)
        if self._config.maxVideoHeight <> 9999 and url.lower().find('.m3u8') > 0:
            log('Parsing M3U8 Playlist: %s' % url)
            m3u8obj = m3u8_load(url)
            if m3u8obj.is_variant and not m3u8obj.cookies:
                # Variant Streams with Cookies have to be played without stream selection.
                # You can change the Bandwidth Limit in Kodi Settings to select other streams !
                # Select stream with highest resolution <= maxVideoHeight
                selected_height = 0
                for playlist in m3u8obj.playlists:
                    try:
                        width, height = playlist.stream_info.resolution
                        if height > selected_height and height <= self._config.maxVideoHeight:
                            if re.match(r'https?://', playlist.uri):
                                url = playlist.uri
                            else:
                                url = m3u8obj.base_uri + playlist.uri
                            selected_height = height
                    except:
                        pass
        return url

    def add_list_items(self, items, content=None, end=True, withNextPage=False):
        if content:
            xbmcplugin.setContent(plugin.handle, content)
        list_items = []
        for item in items:
            if isinstance(item, Category):
                category_items = item.getListItems()
                for url, li, isFolder in category_items:
                    if url and li:
                        list_items.append((url, li, isFolder))
            elif isinstance(item, BrowsableMedia):
                url, li, isFolder = item.getListItem()
                if url and li:
                    list_items.append((url, li, isFolder))
        if withNextPage and len(items) > 0:
            # Add folder for next page
            try:
                totalNumberOfItems = items[0]._totalNumberOfItems
                nextOffset = items[0]._offset + self._config.pageSize
                if nextOffset < totalNumberOfItems and len(items) >= self._config.pageSize:
                    path = urlsplit(sys.argv[0]).path or '/'
                    path = path.split('/')[:-1]
                    path.append(str(nextOffset))
                    url = '/'.join(path)
                    self.add_directory_item(_T(30244).format(pos1=nextOffset, pos2=min(nextOffset+self._config.pageSize, totalNumberOfItems)), plugin.url_for_path(url))
            except:
                log('Next Page for URL %s not set' % sys.argv[0], xbmc.LOGERROR)
        if len(list_items) > 0:
            xbmcplugin.addDirectoryItems(plugin.handle, list_items)
        if end:
            xbmcplugin.endOfDirectory(plugin.handle)

    def add_directory_item(self, title, endpoint, thumb=None, fanart=None, end=False, isFolder=True):
        if callable(endpoint):
            endpoint = plugin.url_for(endpoint)
        item = FolderItem(title, endpoint, thumb, fanart, isFolder)
        self.add_list_items([item], end=end)


class KodiLogHandler(logging.StreamHandler):

    def __init__(self, modules):
        logging.StreamHandler.__init__(self)
        self._modules = modules
        prefix = b"[%s] " % plugin.name
        formatter = logging.Formatter(prefix + b'%(name)s: %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        if record.levelno < logging.WARNING and self._modules and not record.name in self._modules:
            # Log INFO and DEBUG only with enabled modules
            return 
        levels = {
            logging.CRITICAL: xbmc.LOGFATAL,
            logging.ERROR: xbmc.LOGERROR,
            logging.WARNING: xbmc.LOGWARNING,
            logging.INFO: xbmc.LOGDEBUG,
            logging.DEBUG: xbmc.LOGSEVERE,
            logging.NOTSET: xbmc.LOGNONE,
        }
        try:
            xbmc.log(self.format(record), levels[record.levelno])
        except UnicodeEncodeError:
            xbmc.log(self.format(record).encode('utf-8', 'ignore'), levels[record.levelno])

    def flush(self):
        pass
