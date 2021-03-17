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
import locale
import json
import datetime
from urlparse import urlsplit
import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon
import xbmcplugin
from xbmcgui import ListItem
from routing import Plugin

PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str
else:
    string_types = basestring


from tidalapi import Config, Session, User, Favorites
from tidalapi.models import Quality, SubscriptionType, AlbumType, BrowsableMedia, Artist, Album, PlayableMedia, Track, Video, Mix, Playlist, Promotion, Category, CutInfo, IMG_URL
from m3u8 import load as m3u8_load
from debug import DebugHelper

class KodiPlugin(Plugin):
    def __init__(self, base_url=None):
        try:
            # Creates a Dump is sys.argv[] is empty !
            Plugin.__init__(self, base_url=base_url)
        except:
            pass
        self.base_url = base_url

_addon_id = 'plugin.audio.tidal2'
addon = xbmcaddon.Addon(id=_addon_id)
plugin = KodiPlugin(base_url = "plugin://" + _addon_id)
plugin.name = addon.getAddonInfo('name')
_addon_icon = os.path.join(addon.getAddonInfo('path').decode('utf-8'), 'icon.png')
_addon_fanart = os.path.join(addon.getAddonInfo('path').decode('utf-8'), 'fanart.jpg')

debug = DebugHelper(pluginName=addon.getAddonInfo('name'), 
                    detailLevel=2 if addon.getSetting('debug_log') == 'true' else 1, 
                    enableTidalApiLog= True if addon.getSetting('debug_log') == 'true' else False)

log = debug.log

try:
    version = json.loads(xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["version", "name"]}, "id": 1 }'))['result']['version']
    KODI_VERSION = (version['major'], version['minor'])
except:
    KODI_VERSION = (16, 1)

CACHE_DIR = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
FAVORITES_FILE = os.path.join(CACHE_DIR, 'favorites.cfg')
LOCKED_ARTISTS_FILE = os.path.join(CACHE_DIR, 'locked_artists.cfg')
PLAYLISTS_FILE = os.path.join(CACHE_DIR, 'playlists.cfg')
ALBUM_PLAYLIST_TAG = 'ALBUM'
VARIOUS_ARTIST_ID = '2935'


def _T(txtid):
    if isinstance(txtid, string_types):
        # Map TIDAL texts to Text IDs
        newid = {'artist':  30101, 'album':  30102, 'playlist':  30103, 'track':  30104, 'video':  30105,
                 'artists': 30101, 'albums': 30102, 'playlists': 30103, 'tracks': 30104, 'videos': 30105,
                 'featured': 30203, 'rising': 30211, 'discovery': 30212, 'movies': 30115, 'shows': 30116, 'genres': 30117, 'moods': 30118
                 }.get(txtid.lower(), None)
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
             }.get(key.lower(), None)
    if newid:
        return _T(newid)
    return default_txt if default_txt else key


# Convert TIDAL-API Media into Kodi List Items

class HasListItem(object):

    _is_logged_in = False

    def setLabelFormat(self):
        self._favorites_in_labels = True if addon.getSetting('favorites_in_labels') == 'true' else False
        self._user_playlists_in_labels = True if addon.getSetting('user_playlists_in_labels') == 'true' else False
        self._colored_labels = True if addon.getSetting('color_mode') == 'true' else False
        if self._colored_labels:
            self.FOLDER_MASK = '[COLOR blue]{label}[/COLOR]'
            if self._favorites_in_labels:
                self.FAVORITE_MASK = '[COLOR yellow]{label}[/COLOR]'
            else:
                self.FAVORITE_MASK = '{label}'
            self.STREAM_LOCKED_MASK = '[COLOR maroon]{label} ({info})[/COLOR]'
            if self._user_playlists_in_labels:
                self.USER_PLAYLIST_MASK = '{label} [COLOR limegreen][{userpl}][/COLOR]'
            else:
                self.USER_PLAYLIST_MASK = '{label}'
            self.DEFAULT_PLAYLIST_MASK = '[COLOR limegreen]{label} ({mediatype})[/COLOR]'
            self.MASTER_AUDIO_MASK = '{label} [COLOR blue]MQA[/COLOR]'
        else:
            self.FOLDER_MASK = '{label}'
            if self._favorites_in_labels:
                self.FAVORITE_MASK = '<{label}>'
            else:
                self.FAVORITE_MASK = '{label}'
            self.STREAM_LOCKED_MASK = '{label} ({info})'
            if self._user_playlists_in_labels:
                self.USER_PLAYLIST_MASK = '{label} [{userpl}]'
            else:
                self.USER_PLAYLIST_MASK = '{label}'
            self.DEFAULT_PLAYLIST_MASK = '{label} ({mediatype})'
            self.MASTER_AUDIO_MASK = '{label} (MQA)'

    def getLabel(self, extended=True):
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
        # In Favorites View everything as a Favorite
        if self._is_logged_in and hasattr(self, '_isFavorite') and '/favorites/' in sys.argv[0]:
            self._isFavorite = True
        cm = self.getContextMenuItems()
        if len(cm) > 0:
            li.addContextMenuItems(cm)
        return li

    def getContextMenuItems(self):
        return []

    def getSortText(self, mode=None):
        return self.getLabel(extended=False)


class AlbumItem(Album, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem(self.artist)
        self.artists = [ArtistItem(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem(artist) for artist in self._ftArtists]
        self._userplaylists = {}    # Filled by parser
        self._playlist_id = None    # ID of the Playlist
        self._playlist_pos = -1     # Item position in playlist
        self._etag = None           # ETag for User Playlists
        self._playlist_name = None  # Name of Playlist
        self._playlist_type = ''    # Playlist Type
        self._playlist_track_id = 0 # Track-ID of item which is shown as Album Item

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.getLongTitle()
        if extended and self._isFavorite and not '/favorites/' in sys.argv[0]:
            label = self.FAVORITE_MASK.format(label=label)
        label = '%s - %s' % (self.artist.getLabel(extended), label)
        txt = []
        plids = list(self._userplaylists.keys())
        for plid in plids:
            if plid != self._playlist_id:
                txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if extended and txt:
            label = self.USER_PLAYLIST_MASK.format(label=label, userpl=', '.join(txt))
        return label

    def getLongTitle(self):
        self.setLabelFormat()
        longTitle = '%s' % self.title
        if self.type == AlbumType.ep:
            longTitle += ' (EP)'
        elif self.type == AlbumType.single:
            longTitle += ' (Single)'
        if self.explicit and not 'Explicit' in self.title:
            longTitle += ' (Explicit)'
        if getattr(self, 'year', None) and addon.getSetting('album_year_in_labels') == 'true':
            if self.releaseDate and self.releaseDate > datetime.datetime.now():
                longTitle += ' (%s)' % _T(30268).format(self.releaseDate)
            else:
                longTitle += ' (%s)' % self.year
        if self.audioQuality == Quality.hi_res and addon.getSetting('mqa_in_labels') == 'true':
            longTitle = self.MASTER_AUDIO_MASK.format(label=longTitle)
        return longTitle

    def getSortText(self, mode=None):
        return '%s - (%s) %s' % (self.artist.getLabel(extended=False), getattr(self, 'year', ''), self.getLongTitle())

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/album/%s' % self.id)
        infoLabels = {
            'title': self.title,
            'album': self.title,
            'artist': self.artist.name,
            'year': getattr(self, 'year', None),
            'tracknumber': self._itemPosition + 1 if self._itemPosition >= 0 else 0,
        }
        try:
            if self.streamStartDate:
                infoLabels.update({'date': self.streamStartDate.date().strftime('%d.%m.%Y')})
            elif self.releaseDate:
                infoLabels.update({'date': self.releaseDate.date().strftime('%d.%m.%Y')})
        except:
            pass
        if KODI_VERSION >= (17, 0):
            infoLabels.update({'mediatype': 'album',
                               'rating': '%s' % int(round(self.popularity / 10.0)),
                               'userrating': '%s' % int(round(self.popularity / 10.0))
                               })
        li.setInfo('music', infoLabels)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/albums/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/albums/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(30240), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
                cm.append((_T(30248), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, self._playlist_track_id))))
            cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/album/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    cm.append(((_T(30247).format(name=self._userplaylists[plid].get('title')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_album/%s/%s' % (plid, self.id)))))
            cm.append((_T(30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        return cm


class ArtistItem(Artist, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self._isLocked = True if VARIOUS_ARTIST_ID == '%s' % self.id else False

    def getLabel(self, extended=True):
        self.setLabelFormat()
        if extended and self._isFavorite and not '/favorites/artists' in sys.argv[0]:
            return self.FAVORITE_MASK.format(label=self.name)
        if self._isLocked and '/favorites/artists' in sys.argv[0]:
            return self.STREAM_LOCKED_MASK.format(label=self.name, info=_T(30260))
        return self.name

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/artist/%s' % self.id)
        infoLabel = {'artist': self.name}
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'mediatype': 'artist',
                              'rating': '%s' % int(round(self.popularity / 10.0)),
                              'userrating': '%s' % int(round(self.popularity / 10.0))
                              })
        li.setInfo('music', infoLabel)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/artists/%s' % self.id)))
            else:
                cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/artists/%s' % self.id)))
            if '/favorites/artists' in sys.argv[0]:
                if self._isLocked:
                    cm.append((_T(30262), 'RunPlugin(%s)' % plugin.url_for_path('/unlock_artist/%s' % self.id)))
                else:
                    cm.append((_T(30261), 'RunPlugin(%s)' % plugin.url_for_path('/lock_artist/%s' % self.id)))
        return cm

    @property
    def fanart(self):
        if self.picture:
            return IMG_URL.format(picture=self.picture.replace('-', '/'), size='1080x720')
        if addon.getSetting('fanart_server_enabled') == 'true':
            return 'http://localhost:%s/artist_fanart?id=%s' % (addon.getSetting('fanart_server_port'), self.id)
        return None


class MixItem(Mix, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.name
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/mix/%s' % self.id)
        infoLabel = {
            'title': self.title,
            'album': self.subTitle
        }
        li.setInfo('music', infoLabel)
        return (url, li, True)


class PlaylistItem(Playlist, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        # Fix negative number of tracks/videos in playlist
        if self.numberOfItems > 0 and self.numberOfTracks < 0:
            self.numberOfVideos += self.numberOfTracks
            self.numberOfTracks = 0
        if self.numberOfItems > 0 and self.numberOfVideos < 0:
            self.numberOfTracks += self.numberOfVideos
            self.numberOfVideos = 0
        if self.numberOfItems < 0:
            self.numberOfTracks = self.numberOfVideos = 0

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.name
        if extended and self._isFavorite and not '/favorites/' in sys.argv[0]:
            label = self.FAVORITE_MASK.format(label=label)
        if self.type == 'USER' and sys.argv[0].lower().find('user_playlists') >= 0:
            defaultpl = []
            if str(self.id) == addon.getSetting('default_trackplaylist_id'):
                defaultpl.append(_P('tracks'))
            if str(self.id) == addon.getSetting('default_videoplaylist_id'):
                defaultpl.append(_P('videos'))
            if str(self.id) == addon.getSetting('default_albumplaylist_id'):
                defaultpl.append(_P('albums'))
            if len(defaultpl) > 0:
                return self.DEFAULT_PLAYLIST_MASK.format(label=label, mediatype=', '.join(defaultpl))
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        path = '/playlist/%s/items/0'
        if self.type == 'USER' and ALBUM_PLAYLIST_TAG in self.description:
            path = '/playlist/%s/albums/0'
        url = plugin.url_for_path(path % self.id)
        infoLabel = {
            'artist': self.title,
            'album': self.description,
            'title': _T(30243).format(tracks=self.numberOfTracks, videos=self.numberOfVideos),
            'genre': _T(30243).format(tracks=self.numberOfTracks, videos=self.numberOfVideos),
            'tracknumber': self._itemPosition + 1 if self._itemPosition >= 0 else 0
        }
        try:
            if self.lastUpdated:
                infoLabel.update({'date': self.lastUpdated.date().strftime('%d.%m.%Y')})
            elif self.creationDate:
                infoLabel.update({'date': self.creationDate.date().strftime('%d.%m.%Y')})
        except:
            pass
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'userrating': '%s' % int(round(self.popularity / 10.0))})
        li.setInfo('music', infoLabel)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self.numberOfVideos > 0:
            cm.append((_T(30252), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/tracks/0' % self.id)))
        if self.type == 'USER' and ALBUM_PLAYLIST_TAG in self.description:
            cm.append((_T(30254), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/items/0' % self.id)))
        else:
            cm.append((_T(30255), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/albums/0' % self.id)))
        if self._is_logged_in:
            if self.type == 'USER':
                cm.append((_T(30251), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/rename/%s' % self.id)))
                if self.numberOfItems > 0:
                    cm.append((_T(30258), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/clear/%s' % self.id)))
                cm.append((_T(30235), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/delete/%s' % self.id)))
            else:
                if self._isFavorite:
                    cm.append((_T(30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/playlists/%s' % self.id)))
                else:
                    cm.append((_T(30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/playlists/%s' % self.id)))
            cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/playlist/%s' % self.id)))
            if self.type == 'USER' and sys.argv[0].lower().find('user_playlists') >= 0:
                if str(self.id) == addon.getSetting('default_trackplaylist_id'):
                    cm.append((_T(30250).format(what=_T('Track')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/tracks')))
                else:
                    cm.append((_T(30249).format(what=_T('Track')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/tracks/%s' % self.id)))
                if str(self.id) == addon.getSetting('default_videoplaylist_id'):
                    cm.append((_T(30250).format(what=_T('Video')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/videos')))
                else:
                    cm.append((_T(30249).format(what=_T('Video')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/videos/%s' % self.id)))
                if str(self.id) == addon.getSetting('default_albumplaylist_id'):
                    cm.append((_T(30250).format(what=_T('Album')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/albums')))
                else:
                    cm.append((_T(30249).format(what=_T('Album')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/albums/%s' % self.id)))
        return cm


class TrackItem(Track, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        if self.version and not self.version in self.title:
            self.title += ' (%s)' % self.version
            self.version = None
        self.artist = ArtistItem(self.artist)
        self.artists = [ArtistItem(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem(artist) for artist in self._ftArtists]
        self.album = AlbumItem(self.album)
        self._userplaylists = {} # Filled by parser

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label1 = self.artist.getLabel(extended=extended if self.available else False)
        label2 = self.getLongTitle()
        if extended and self._isFavorite and self.available and not '/favorites/' in sys.argv[0]:
            label2 = self.FAVORITE_MASK.format(label=label2)
        label = '%s - %s' % (label1, label2)
        if extended and not self.available:
            label = self.STREAM_LOCKED_MASK.format(label=label, info=_T(30242))
        txt = []
        plids = list(self._userplaylists.keys())
        for plid in plids:
            if plid != self._playlist_id:
                txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if extended and txt:
            label = self.USER_PLAYLIST_MASK.format(label=label, userpl=', '.join(txt))
        return label

    def getLongTitle(self):
        self.setLabelFormat()
        longTitle = self.title
        if self.version and not self.version in self.title:
            longTitle += ' (%s)' % self.version
        if self.explicit and not 'Explicit' in self.title:
            longTitle += ' (Explicit)'
        if self.editable and isinstance(self._cut, CutInfo):
            if self._cut.name:
                longTitle += ' (%s)' % self._cut.name
        if self.audioQuality == Quality.hi_res and addon.getSetting('mqa_in_labels') == 'true':
            longTitle = self.MASTER_AUDIO_MASK.format(label=longTitle)
        return longTitle

    def getSortText(self, mode=None):
        if mode == 'ALBUM':
            return self.album.getSortText(mode=mode)
        return self.getLabel(extended=False)

    def getFtArtistsText(self):
        text = ''
        for item in self._ftArtists:
            if len(text) > 0:
                text = text + ', '
            text = text + item.name
        if len(text) > 0:
            text = 'ft. by ' + text
        return text

    def getComment(self):
        txt = self.getFtArtistsText()
        comments = ['track_id=%s' % self.id]
        if txt:
            comments.append(txt)
        #if self.replayGain != 0:
        #    comments.append("gain:%0.3f, peak:%0.3f" % (self.replayGain, self.peak))
        return ', '.join(comments)

    def getListItem(self):
        li = HasListItem.getListItem(self)
        if self.available:
            if isinstance(self._cut, CutInfo):
                url = plugin.url_for_path('/play_track_cut/%s/%s/%s' % (self.id, self._cut.id, self.album.id))
            else:
                url = plugin.url_for_path('/play_track/%s/%s' % (self.id, self.album.id))
            isFolder = False
        else:
            url = plugin.url_for_path('/stream_locked')
            isFolder = True
        longTitle = self.title
        if self.explicit and not 'Explicit' in self.title:
            longTitle += ' (Explicit)'
        infoLabel = {
            'title': longTitle,
            'tracknumber': self._playlist_pos + 1 if self._playlist_id else self._itemPosition + 1 if self._itemPosition >= 0 else self.trackNumber,
            'discnumber': self.volumeNumber,
            'duration': self.duration,
            'artist': self.artist.name,
            'album': self.album.title,
            'year': getattr(self, 'year', None),
            'rating': '%s' % int(round(self.popularity / 10.0)),
            'comment': self.getComment()
        }
        try:
            if self.streamStartDate:
                infoLabel.update({'date': self.streamStartDate.date().strftime('%d.%m.%Y')})
            elif self.releaseDate:
                infoLabel.update({'date': self.releaseDate.date().strftime('%d.%m.%Y')})
        except:
            pass
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'mediatype': 'song',
                              'userrating': '%s' % int(round(self.popularity / 10.0))
                              })
        li.setInfo('music', infoLabel)
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
                item_id = self.id if not isinstance(self._cut, CutInfo) else self._cut.id
                cm.append((_T(30248), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, item_id))))
            else:
                cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/track/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    playlist = self._userplaylists[plid]
                    if '%s' % self.album.id in playlist.get('album_ids', []):
                        cm.append(((_T(30247).format(name=playlist.get('title')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_album/%s/%s' % (plid, self.album.id)))))
                    else:
                        cm.append(((_T(30247).format(name=playlist.get('title')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
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
        self.album = AlbumItem(self.album) if self.album else None
        self._userplaylists = {} # Filled by parser

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label1 = self.artist.name
        if extended and self.artist._isFavorite and self.available:
            label1 = self.FAVORITE_MASK.format(label=label1)
        label2 = self.getLongTitle()
        if extended and self._isFavorite and self.available and not '/favorites/' in sys.argv[0]:
            label2 = self.FAVORITE_MASK.format(label=label2)
        label = '%s - %s' % (label1, label2)
        if extended and not self.available:
            label = self.STREAM_LOCKED_MASK.format(label=label, info=_T(30242))
        txt = []
        plids = list(self._userplaylists.keys())
        for plid in plids:
            if plid != self._playlist_id:
                txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if extended and txt:
            label = self.USER_PLAYLIST_MASK.format(label=label, userpl=', '.join(txt))
        return label

    def getLongTitle(self):
        longTitle = self.title
        if self.explicit and not 'Explicit' in self.title:
            longTitle += ' (Explicit)'
        if getattr(self, 'year', None):
            longTitle += ' (%s)' % self.year
        return longTitle

    def getFtArtistsText(self):
        text = ''
        for item in self._ftArtists:
            if len(text) > 0:
                text = text + ', '
            text = text + item.name
        if len(text) > 0:
            text = 'ft. by ' + text
        return text

    def getComment(self):
        txt = self.getFtArtistsText()
        comments = ['video_id=%s' % self.id]
        if txt:
            comments.append(txt)
        return ', '.join(comments)

    def getListItem(self):
        li = HasListItem.getListItem(self)
        if self.available:
            url = plugin.url_for_path('/play_video/%s' % self.id)
            isFolder = False
        else:
            url = plugin.url_for_path('/stream_locked')
            isFolder = True
        infoLabel = {
            'artist': [self.artist.name],
            'title': self.title,
            'tracknumber': self._playlist_pos + 1 if self._playlist_id else self._itemPosition + 1,
            'year': getattr(self, 'year', None),
            'plotoutline': self.getComment(),
            'plot': self.getFtArtistsText()
        }
        musicLabel = {
            'artist': self.artist.name,
            'title': self.title,
            'tracknumber': self._playlist_pos + 1 if self._playlist_id else self._itemPosition + 1,
            'year': getattr(self, 'year', None),
            'comment': self.getComment()
        }
        try:
            if self.streamStartDate:
                infoLabel.update({'date': self.streamStartDate.date().strftime('%d.%m.%Y')})
                musicLabel.update({'date': self.streamStartDate.date().strftime('%d.%m.%Y')})
            elif self.releaseDate:
                infoLabel.update({'date': self.releaseDate.date().strftime('%d.%m.%Y')})
                musicLabel.update({'date': self.releaseDate.date().strftime('%d.%m.%Y')})
        except:
            pass
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'mediatype': 'musicvideo',
                              'rating': '%s' % int(round(self.popularity / 10.0)),
                              'userrating': '%s' % int(round(self.popularity / 10.0))
                              })
        li.setInfo('video', infoLabel)
        li.setInfo('music', musicLabel)
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
                cm.append((_T(30248), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, self.id))))
            else:
                cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/video/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    cm.append(((_T(30247).format(name=self._userplaylists[plid].get('title')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
        cm.append((_T(30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        cm.append((_T(30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class PromotionItem(Promotion, HasListItem):

    def __init__(self, item):
        if item.type != 'EXTURL' and item.id.startswith('http:'):
            item.type = 'EXTURL' # Fix some defect TIDAL Promotions
        self.__dict__.update(vars(item))
        self._userplaylists = {} # Filled by parser

    def getLabel(self, extended=True):
        self.setLabelFormat()
        if self.type in ['ALBUM', 'VIDEO']:
            label = '%s - %s' % (self.shortHeader, self.shortSubHeader)
        else:
            label = self.shortHeader
        if extended and self._isFavorite:
            label = self.FAVORITE_MASK.format(label=label)
        txt = []
        plids = list(self._userplaylists.keys())
        for plid in plids:
            txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if extended and txt:
            label = self.USER_PLAYLIST_MASK.format(label=label, userpl=', '.join(txt))
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        isFolder = True
        if self.type == 'PLAYLIST':
            url = plugin.url_for_path('/playlist/%s/items/0' % self.id)
            infoLabel = {
                'artist': self.shortHeader,
                'album': self.text,
                'title': self.shortSubHeader
            }
            if KODI_VERSION >= (17, 0):
                infoLabel.update({'userrating': '%s' % int(round(self.popularity / 10.0))})
            li.setInfo('music', infoLabel)
        elif self.type == 'ALBUM':
            url = plugin.url_for_path('/album/%s' % self.id)
            infoLabel = {
                'artist': self.shortHeader,
                'album': self.text,
                'title': self.shortSubHeader
            }
            if KODI_VERSION >= (17, 0):
                infoLabel.update({'mediatype': 'album',
                                  'userrating': '%s' % int(round(self.popularity / 10.0))
                                  })
            li.setInfo('music', infoLabel)
        elif self.type == 'VIDEO':
            url = plugin.url_for_path('/play_video/%s' % self.id)
            infoLabel = {
                'artist': [self.shortHeader],
                'album': self.text,
                'title': self.shortSubHeader
            }
            if KODI_VERSION >= (17, 0):
                infoLabel.update({'mediatype': 'musicvideo',
                                  'userrating': '%s' % int(round(self.popularity / 10.0))
                                  })
            li.setInfo('video', infoLabel)
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
            cm.append((_T(30255), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/albums/0' % self.id)))
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
                cm.append((_T(30239), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/video/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                cm.append(((_T(30247).format(name=self._userplaylists[plid].get('title')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
            cm.append((_T(30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class CategoryItem(Category, HasListItem):

    _force_subfolders = False
    _label = None

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self, extended=True):
        self.setLabelFormat()
        if extended:
            return self.FOLDER_MASK.format(label=self._label)
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

    def __init__(self, label, url, thumb=None, fanart=None, isFolder=True, otherLabel=None):
        self.name = label
        self._url = url
        self._thumb = thumb
        self._fanart = fanart
        self._isFolder = isFolder
        self._otherLabel = otherLabel

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self._otherLabel if self._otherLabel else self.name
        if extended:
            label = self.FOLDER_MASK.format(label=label)
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        li.setInfo('music', {
            'artist': self.name
        })
        return (self._url, li, self._isFolder)

    @property
    def image(self):
        return self._thumb

    @property
    def fanart(self):
        return self._fanart


class LoginToken(object):

    ios    = '_DSTon1kC8pABnTw' # Apple IOS Token with AAC, ALAC with MQA and videos (best token so far)
    native = '4zx46pyr9o8qZNRw' # Token from native TIDAL app, but FLAC streams are encrypted
    amarra = 'wc8j_yBJd20zOmx0' # Plays AAC, FLAC and with MQA but no video (only audio of videos)
    # Unkown working Tokens
    ios2   = 'hZ9wuySZCmpLLiui' # Same as ios Token but returns 'numberOfVideos = 0' in Playlists
    tizen  = 'M6ztoSvmny6alVCD' # Only AAC no Lossless but HLS Video and numberOfVideos in Playlists ok.
    vizio  = 'Y40WSvVnnG0ql0L0' # No music but HLS Video and numberOfVideos in Playlists ok.
    tv     = 'NIh99tUmaAyLNmEA' # No music but HLS Video and numberOfVideos in Playlists ok.

    features = {
        # token: Login-Token to get a Session-ID
        # codecs: Supported Audio Codecs without encryption (ALAC_MQA and FLAC_MQA plays music in master quality)
        # videoOk: True: play music videos as HLS streams, False: only audio of videos is played
        # apiOk: True: numberOfVideos in Playlists is correct, False: returns 'numberOfVideos = 0' in Playlists
        # user-agent: Special User-Agent in HTTP-Request-Header
        'ios':    { 'token': ios,    'codecs': ['AAC', 'ALAC'], 'mqaOk': True,  'videoOk': True,  'apiOk': True,  'user-agent': 'TIDAL/546 CFNetwork/808.2.16 Darwin/16.3.0' },
        'ios2':   { 'token': ios2,   'codecs': ['AAC', 'ALAC'], 'mqaOk': True,  'videoOk': True,  'apiOk': False, 'user-agent': 'TIDAL/546 CFNetwork/808.2.16 Darwin/16.3.0' },
        'native': { 'token': native, 'codecs': ['AAC'],         'mqaOk': False, 'videoOk': True,  'apiOk': True,  'user-agent': 'TIDAL_NATIVE_PLAYER/OSX/2.3.20' },
        'amarra': { 'token': amarra, 'codecs': ['AAC', 'FLAC'], 'mqaOk': True,  'videoOk': False, 'apiOk': False, 'user-agent': 'Amarra for TIDAL/2.2.1261 CFNetwork/807.2.14 Darwin/16.3.0 (x86_64)' },
        # Unknown working Tokens
        'tizen':  { 'token': tizen,  'codecs': ['AAC'],         'mqaOk': False, 'videoOk': True,  'apiOk': True,  'user-agent': None },
        'vizio':  { 'token': vizio,  'codecs': [],              'mqaOk': False, 'videoOk': True,  'apiOk': True,  'user-agent': None },
        'tv':     { 'token': tv,     'codecs': [],              'mqaOk': False, 'videoOk': True,  'apiOk': True,  'user-agent': None }
    }

    priority = ['ios', 'ios2', 'native', 'amarra', 'tizen', 'vizio', 'tv']

    @staticmethod
    def getFeatures(tokenName='ios'):
        return LoginToken.features.get(tokenName, None)

    @staticmethod
    def getToken(tokenName='ios'):
        return LoginToken.getFeatures(tokenName).get('token')

    @staticmethod
    def select(codec):
        tokens1 = [] # perfect tokens
        tokens2 = [] # tokens for everything but MQA
        tokens3 = [] # tokens for right codec
        tokens4 = [] # tokens for api and videos
        tokens5 = [] # tokens for api only
        tokens6 = [] # everything else
        ignoreMqa = True if codec == 'AAC' else False
        for tokenName in LoginToken.priority:
            token = LoginToken.getFeatures(tokenName)
            if codec in token.get('codecs') and (token.get('mqaOk') or ignoreMqa) and token.get('apiOk') and token.get('videoOk'):
                tokens1.append(tokenName)
            elif codec in token.get('codecs') and token.get('apiOk') and token.get('videoOk'):
                tokens2.append(tokenName)
            elif codec in token.get('codecs'):
                tokens3.append(tokenName)
            elif token.get('apiOk') and token.get('videoOk'):
                tokens4.append(tokenName)
            elif token.get('apiOk'):
                tokens5.append(tokenName)
            else:
                tokens6.append(tokenName)
        tokens = tokens1 + tokens2 + tokens3 + tokens4 + tokens5 + tokens6
        if not tokens:
            log('No Token found for Codec:%s' % codec)
        return tokens


class TidalConfig(Config):

    def __init__(self):
        Config.__init__(self)
        self.load()

    def load(self):
        self.session_id = addon.getSetting('session_id')
        self.session_token_name = addon.getSetting('session_token_name')
        self.stream_session_id = addon.getSetting('stream_session_id')
        self.stream_token_name = addon.getSetting('stream_token_name')
        if not self.stream_session_id:
            self.stream_session_id = self.session_id
            self.stream_token_name = self.session_token_name
        self.video_session_id = addon.getSetting('video_session_id')
        self.video_token_name = addon.getSetting('video_token_name')
        if not self.video_session_id:
            self.video_session_id = self.stream_session_id
            self.video_token_name = self.stream_token_name
        self.country_code = addon.getSetting('country_code')
        # Determine the locale of the system
        self.locale = None
        try:
            self.locale = locale.getdefaultlocale()[0]
        except:
            pass
        if not self.locale:
            try:
                self.locale = locale.getlocale()[0]
            except:
                pass
        if not self.locale:
            try:
                langval = json.loads(xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Settings.GetSettingValue", "params": {"setting": "locale.language"}, "id": 1 }'))['result']['value'].split('.')[-1]
                self.locale = locale.locale_alias.get(langval).split('.')[0]
            except:
                pass
        if not self.locale:
            # If no locale is found take the US locale
            self.locale = 'en_US'
        self.user_id = addon.getSetting('user_id')
        self.subscription_type = [SubscriptionType.hifi, SubscriptionType.premium][min(1, int('0' + addon.getSetting('subscription_type')))]
        self.client_unique_key = addon.getSetting('client_unique_key')
        self.quality = [Quality.lossless, Quality.high, Quality.low][min(2, int('0' + addon.getSetting('quality')))]
        self.codec = ['FLAC', 'AAC', 'AAC'][min([2, int('0' + addon.getSetting('quality'))])]
        if addon.getSetting('music_option') == '1' and self.quality == Quality.lossless:
            self.codec = 'ALAC'
        self.maxVideoHeight = [9999, 1080, 720, 540, 480, 360, 240][min(6, int('0%s' % addon.getSetting('video_quality')))]
        self.pageSize = max(10, min(9999, int('0%s' % addon.getSetting('page_size'))))
        self.debug = True if addon.getSetting('debug_log') == 'true' else False
        self.debug_json = True if addon.getSetting('debug_json') == 'true' else False
        self.mqa_in_labels = True if addon.getSetting('mqa_in_labels') == 'true' and self.codec == 'MQA' else False
        self.fanart_server_enabled = True if addon.getSetting('fanart_server_enabled') == 'true' else False
        self.fanart_server_port = int('0%s' % addon.getSetting('fanart_server_port'))


class TidalSession(Session):

    errorCodes = []

    def __init__(self, config=TidalConfig()):
        Session.__init__(self, config=config)

    def halt(self):
        debug.halt()

    def init_user(self, user_id, subscription_type):
        return TidalUser(self, user_id, subscription_type)

    def load_session(self):
        if not self._config.country_code:
            self._config.country_code = self.local_country_code()
            addon.setSetting('country_code', self._config.country_code)
        Session.load_session(self, self._config.session_id, self._config.country_code, self._config.user_id,
                             self._config.subscription_type, self._config.client_unique_key)
        self.stream_session_id = self._config.stream_session_id
        self.video_session_id = self._config.video_session_id

    def generate_client_unique_key(self):
        unique_key = addon.getSetting('client_unique_key')
        if not unique_key:
            unique_key = Session.generate_client_unique_key(self)
        return unique_key

    def login_with_token(self, username, password, subscription_type, tokenName):
        old_token = self._config.api_token
        old_session_id = self.session_id
        self._config.api_token = LoginToken.getToken(tokenName)
        self.session_id = None
        Session.login(self, username, password, subscription_type)
        retval = self.session_id
        self.session_id = old_session_id
        self._config.api_token = old_token
        return retval

    def login(self, username, password, subscription_type=None):
        if not username or not password:
            return False
        if not subscription_type:
            # Set Subscription Type corresponding to the given playback quality
            subscription_type = SubscriptionType.hifi if self._config.quality == Quality.lossless else SubscriptionType.premium
        if not self.client_unique_key:
            # Generate a random client key if no key is given
            self.client_unique_key = self.generate_client_unique_key()
        api_token = ''
        stream_token = ''
        video_token = ''
        fallback_token = ''
        fallback_session_id = None
        # Get tokens in an order to try login with
        tokenNames = LoginToken.select(codec=self._config.codec)
        if not tokenNames:
            # Get tokens for default playback
            tokenNames = LoginToken.select(codec='AAC')
        # Try login with everey token until all playback features are ok.
        for tokenName in tokenNames:
            log('Try Login with %s Token %s ...' % (tokenName, LoginToken.getToken(tokenName)))
            new_session_id = self.login_with_token(username, password, subscription_type, tokenName)
            if new_session_id:
                token = LoginToken.getFeatures(tokenName)
                if not fallback_session_id or self._config.codec in token.get('codecs'):
                    fallback_token = tokenName
                    fallback_session_id = new_session_id
                if token.get('apiOk') and not api_token:
                    log('Token is ok for API')
                    api_token = tokenName
                    self.session_id = new_session_id
                if self._config.codec in token.get('codecs') and not stream_token:
                    log('Token is ok for %s music playback' % self._config.codec)
                    stream_token = tokenName
                    self.stream_session_id = new_session_id
                if token.get('videoOk') and not video_token:
                    log('Token is ok for video playback')
                    video_token = tokenName
                    self.video_session_id = new_session_id
                if api_token and stream_token and video_token:
                    break
        # Set fallback session
        if not api_token:
            api_token = fallback_token
            self.session_id = fallback_session_id
        if not stream_token:
            stream_token = fallback_token
            self.stream_session_id = fallback_session_id
        if not video_token:
            video_token = fallback_token
            self.video_session_id = fallback_session_id
        # Save Session Data into Addon-Settings
        if self.is_logged_in:
            addon.setSetting('session_id', self.session_id)
            addon.setSetting('session_token_name', api_token)
            addon.setSetting('stream_session_id', self.stream_session_id)
            addon.setSetting('stream_token_name', stream_token)
            addon.setSetting('video_session_id', self.video_session_id)
            addon.setSetting('video_token_name', video_token)
            addon.setSetting('country_code', self.country_code)
            addon.setSetting('user_id', unicode(self.user.id))
            addon.setSetting('subscription_type', '0' if self.user.subscription.type == SubscriptionType.hifi else '1')
            addon.setSetting('client_unique_key', self.client_unique_key)
            # Reload the Configuration after Settings are saved.
            self._config.load()
            self.load_session()
        return self.is_logged_in

    def logout(self):
        Session.logout(self)
        self.stream_session_id = None
        addon.setSetting('session_id', '')
        addon.setSetting('session_token_name', '')
        addon.setSetting('stream_session_id', '')
        addon.setSetting('stream_token_name', '')
        addon.setSetting('video_session_id', '')
        addon.setSetting('video_token_name', '')
        addon.setSetting('user_id', '')
        self._config.load()

    def get_album_tracks(self, album_id, withAlbum=True):
        items = Session.get_album_tracks(self, album_id)
        if withAlbum:
            album = self.get_album(album_id)
            if album:
                for item in items:
                    item.album = album
        return items

    def get_playlist_tracks(self, playlist_id, offset=0, limit=9999):
        # keeping 1st parameter as playlist_id for backward compatibility 
        if isinstance(playlist_id, Playlist):
            playlist = playlist_id
            playlist_id = playlist.id
        else:
            playlist = self.get_playlist(playlist_id)
        # Don't read empty playlists
        if not playlist or playlist.numberOfItems == 0:
            return []
        items = Session.get_playlist_tracks(self, playlist.id, offset=offset, limit=limit)
        if items:
            for item in items:
                item._etag = playlist._etag
                item._playlist_name = playlist.title
                item._playlist_type = playlist.type
        return items

    def get_item_albums(self, items):
        albums = []
        for item in items:
            album = item.album
            if not album.releaseDate:
                album.releaseDate = item.streamStartDate
            # Item-Position in the Kodi-List (filled by _map_request)
            album._itemPosition = item._itemPosition
            album._offset = item._offset
            album._totalNumberOfItems = item._totalNumberOfItems
            # Infos for Playlist-Item-Position (filled by get_playlist_tracks, get_playlist_items)
            album._playlist_id = item._playlist_id
            album._playlist_pos = item._playlist_pos
            album._etag = item._etag
            album._playlist_name = item._playlist_name
            album._playlist_type = item._playlist_type
            album._userplaylists = self.user.playlists_of_id(None, album.id)
            # Track-ID in TIDAL-Playlist
            album._playlist_track_id = item.id
            album.audioQuality = item.audioQuality
            albums.append(album)
        return albums

    def get_playlist_albums(self, playlist, offset=0, limit=9999):
        return self.get_item_albums(self.get_playlist_items(playlist, offset=offset, limit=limit))

    def get_artist_top_tracks(self, artist_id, offset=0, limit=999):
        items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=limit)
        if not items and limit >= 100:
            items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=100)
        if not items and limit >= 50:
            items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=50)
        if not items:
            items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=20)
        return items

    def get_artist_radio(self, artist_id, offset=0, limit=999):
        items = Session.get_artist_radio(self, artist_id, offset=offset, limit=limit)
        if not items and limit >= 100:
            items = Session.get_artist_radio(self, artist_id, offset=offset, limit=100)
        if not items and limit >= 50:
            items = Session.get_artist_radio(self, artist_id, offset=offset, limit=50)
        if not items:
            items = Session.get_artist_radio(self, artist_id, offset=offset, limit=20)
        return items

    def get_track_radio(self, track_id, offset=0, limit=999):
        items = Session.get_track_radio(self, track_id, offset=offset, limit=limit)
        if not items and limit >= 100:
            items = Session.get_track_radio(self, track_id, offset=offset, limit=100)
        if not items and limit >= 50:
            items = Session.get_track_radio(self, track_id, offset=offset, limit=50)
        if not items:
            items = Session.get_track_radio(self, track_id, offset=offset, limit=20)
        return items

    def get_recommended_items(self, content_type, item_id, offset=0, limit=999):
        items = Session.get_recommended_items(self, content_type, item_id, offset=offset, limit=limit)
        if not items and limit >= 100:
            items = Session.get_recommended_items(self, content_type, item_id, offset=offset, limit=100)
        if not items and limit >= 50:
            items = Session.get_recommended_items(self, content_type, item_id, offset=offset, limit=50)
        if not items:
            items = Session.get_recommended_items(self, content_type, item_id, offset=offset, limit=20)
        return items

    def _parse_album(self, json_obj, artist=None):
        album = AlbumItem(Session._parse_album(self, json_obj, artist=artist))
        album._is_logged_in = self.is_logged_in
        if self.is_logged_in:
            album._userplaylists = self.user.playlists_of_id(None, album.id)
        return album

    def _parse_artist(self, json_obj):
        artist = ArtistItem(Session._parse_artist(self, json_obj))
        if self.is_logged_in and self.user.favorites:
            artist._isLocked = self.user.favorites.isLockedArtist(artist.id)
        artist._is_logged_in = self.is_logged_in
        return artist

    def _parse_mix(self, json_obj):
        mix = MixItem(Session._parse_mix(self, json_obj))
        mix._is_logged_in = self.is_logged_in
        return mix

    def _parse_playlist(self, json_obj):
        playlist = PlaylistItem(Session._parse_playlist(self, json_obj))
        playlist._is_logged_in = self.is_logged_in
        return playlist

    def _parse_track(self, json_obj):
        track = TrackItem(Session._parse_track(self, json_obj))
        if not getattr(track.album, 'streamStartDate', None):
            track.album.streamStartDate = track.streamStartDate
        track.album.explicit = track.explicit
        track._is_logged_in = self.is_logged_in
        if self.is_logged_in:
            track._userplaylists = self.user.playlists_of_id(track.id, track.album.id)
        elif track.duration > 30:
            # 30 Seconds Limit in Trial Mode
            track.duration = 30
        return track

    def _parse_video(self, json_obj):
        video = VideoItem(Session._parse_video(self, json_obj))
        video._is_logged_in = self.is_logged_in
        if self.is_logged_in:
            video._userplaylists = self.user.playlists_of_id(video.id, video.album.id if video.album else None)
        elif video.duration > 30:
            # 30 Seconds Limit in Trial Mode
            video.duration = 30
        return video

    def _parse_promotion(self, json_obj):
        promotion = PromotionItem(Session._parse_promotion(self, json_obj))
        promotion._is_logged_in = self.is_logged_in
        if self.is_logged_in and promotion.type == 'VIDEO':
            promotion._userplaylists = self.user.playlists_of_id(promotion.id)
        return promotion

    def _parse_category(self, json_obj):
        return CategoryItem(Session._parse_category(self, json_obj))

    def get_media_url(self, track_id, quality=None, cut_id=None, fallback=False):
        # return Session.get_media_url(self, track_id, quality=quality, cut_id=cut_id, fallback=fallback)
        soundQuality = quality if quality else self._config.quality
        media = self.get_track_url(track_id, quality=soundQuality, cut_id=cut_id, fallback=True)
        if not media:
            return None
        return media.url

    def get_track_url(self, track_id, quality=None, cut_id=None, fallback=True):
        oldSessionId = self.session_id
        self.session_id = self.stream_session_id
        soundQuality = quality if quality else self._config.quality
        #if soundQuality == Quality.lossless and self._config.codec == 'MQA' and not cut_id:
        #    soundQuality = Quality.hi_res
        media = Session.get_track_url(self, track_id, quality=soundQuality, cut_id=cut_id)
        if fallback and soundQuality == Quality.lossless and (media == None or media.isEncrypted):
            log(media.url, level=xbmc.LOGWARNING)
            if media:
                log('Got encryptionKey "%s" for track %s, trying HIGH Quality ...' % (media.encryptionKey, track_id), level=xbmc.LOGWARNING)
            else:
                log('No Lossless stream for track %s, trying HIGH Quality ...' % track_id, level=xbmc.LOGWARNING)
            media = self.get_track_url(track_id, quality=Quality.high, cut_id=cut_id, fallback=False)
        if media:
            if quality == Quality.lossless and media.codec not in ['FLAC', 'ALAC', 'MQA']:
                xbmcgui.Dialog().notification(plugin.name, _T(30504), icon=xbmcgui.NOTIFICATION_WARNING)
            log('Got stream with soundQuality:%s, codec:%s' % (media.soundQuality, media.codec))
        self.session_id = oldSessionId
        return media

    def get_video_url(self, video_id, maxHeight=-1):
        oldSessionId = self.session_id
        self.session_id = self.video_session_id
        maxVideoHeight = maxHeight if maxHeight > 0 else self._config.maxVideoHeight
        media = Session.get_video_url(self, video_id, quality=None)
        if maxVideoHeight != 9999 and media.url.lower().find('.m3u8') > 0:
            log('Parsing M3U8 Playlist: %s' % media.url)
            m3u8obj = m3u8_load(media.url)
            if m3u8obj.is_variant:
                # Select stream with highest resolution <= maxVideoHeight
                selected_height = 0
                selected_bandwidth = -1
                for playlist in m3u8obj.playlists:
                    try:
                        width, height = playlist.stream_info.resolution
                        bandwidth = playlist.stream_info.average_bandwidth
                        if not bandwidth:
                            bandwidth = playlist.stream_info.bandwidth
                        if not bandwidth:
                            bandwidth = 0
                        if (height > selected_height or (height == selected_height and bandwidth > selected_bandwidth)) and height <= maxVideoHeight:
                            if re.match(r'https?://', playlist.uri):
                                media.url = playlist.uri
                            else:
                                media.url = m3u8obj.base_uri + playlist.uri
                            if height == selected_height and bandwidth > selected_bandwidth:
                                log('Bandwidth %s > %s' % (bandwidth, selected_bandwidth))
                            log('Selected %sx%s %s: %s' % (width, height, bandwidth, playlist.uri.split('?')[0].split('/')[-1]))
                            selected_height = height
                            selected_bandwidth = bandwidth
                            media.width = width
                            media.height = height
                            media.bandwidth = bandwidth
                        elif height > maxVideoHeight:
                            log('Skipped %sx%s %s: %s' % (width, height, bandwidth, playlist.uri.split('?')[0].split('/')[-1]))
                    except:
                        pass
        self.session_id = oldSessionId
        return media

    def add_list_items(self, items, content=None, end=True, withNextPage=False):
        if content:
            xbmcplugin.setContent(plugin.handle, content)
        list_items = []
        for item in items:
            if isinstance(item, Category):
                category_items = item.getListItems()
                for url, li, isFolder in category_items:
                    if url and li:
                        list_items.append(('%s/' % url if isFolder else url, li, isFolder))
            elif isinstance(item, BrowsableMedia):
                url, li, isFolder = item.getListItem()
                if url and li:
                    list_items.append(('%s/' % url if isFolder else url, li, isFolder))
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
            try:
                kodiVersion = xbmc.getInfoLabel('System.BuildVersion').split()[0]
                kodiVersion = kodiVersion.split('.')[0]
                skinTheme = xbmc.getSkinDir().lower()
                if 'onfluence' in skinTheme:
                    if kodiVersion <= '16':
                        xbmc.executebuiltin('Container.SetViewMode(506)')
                    elif content == 'musicvideos':
                        xbmc.executebuiltin('Container.SetViewMode(511)')
                    elif content == 'artists':
                        xbmc.executebuiltin('Container.SetViewMode(512)')
                    else:
                        xbmc.executebuiltin('Container.SetViewMode(506)')
                elif 'estuary' in skinTheme:
                    xbmc.executebuiltin('Container.SetViewMode(55)')
            except:
                pass

    def add_directory_item(self, title, endpoint, thumb=None, fanart=None, end=False, isFolder=True, label=None):
        if callable(endpoint):
            endpoint = plugin.url_for(endpoint)
        item = FolderItem(title, endpoint, thumb, fanart, isFolder, label)
        self.add_list_items([item], end=end)

    def master_albums(self, offset=0, limit=999):
        items = self.get_category_content('master', 'recommended', 'albums', offset=offset, limit=limit)
        return items

    def master_playlists(self, offset=0, limit=999):
        items = self.get_category_content('master', 'recommended', 'playlists', offset=offset, limit=limit)
        return items

    def show_busydialog(self, headline='', textline=''):
        self.progressWindow = xbmcgui.DialogProgressBG()
        self.progressWindow.create(heading=headline, message=textline)
        self.progressWindow.update(percent=50)

    def hide_busydialog(self):
        try:
            if self.progressWindow:
                self.progressWindow.close()
        except:
            pass
        self.progressWindow = None


class TidalFavorites(Favorites):

    def __init__(self, session, user_id):
        Favorites.__init__(self, session, user_id)

    def load_cache(self):
        try:
            fd = xbmcvfs.File(FAVORITES_FILE, 'r')
            self.ids_content = fd.read()
            self.ids = eval(self.ids_content)
            if not 'locked_artists' in self.ids:
                try:
                    fd2 = xbmcvfs.File(LOCKED_ARTISTS_FILE, 'r')
                    self.ids['locked_artists'] = eval(fd2.read())
                    fd2.close()
                except:
                    self.ids['locked_artists'] = [VARIOUS_ARTIST_ID]
            fd.close()
            self.ids_loaded = not (self.ids['artists'] == None or self.ids['albums'] == None or
                                   self.ids['playlists'] == None or self.ids['tracks'] == None or
                                   self.ids['videos'] == None)
            if self.ids_loaded:
                log('Loaded %s Favorites from disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
        except:
            self.ids_loaded = False
            self.reset()
        return self.ids_loaded

    def save_cache(self):
        try:
            if self.ids_loaded:
                new_ids = repr(self.ids)
                if new_ids != self.ids_content:
                    fd = xbmcvfs.File(FAVORITES_FILE, 'w')
                    fd.write(new_ids)
                    fd.close()
                    log('Saved %s Favorites to disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
                    if 'locked_artists' in self.ids:
                        fd = xbmcvfs.File(LOCKED_ARTISTS_FILE, 'w')
                        fd.write(repr(self.ids['locked_artists']))
                        fd.close()
        except:
            return False
        return True

    def delete_cache(self):
        try:
            if xbmcvfs.exists(FAVORITES_FILE):
                xbmcvfs.delete(FAVORITES_FILE)
                log('Deleted Favorites file.')
        except:
            return False
        return True

    def load_all(self, force_reload=False):
        if not force_reload and self.ids_loaded:
            return self.ids
        if not force_reload:
            self.load_cache()
        if force_reload or not self.ids_loaded:
            Favorites.load_all(self, force_reload=force_reload)
            self.save_cache()
        return self.ids

    def get(self, content_type, limit=9999):
        items = Favorites.get(self, content_type, limit=limit)
        if items:
            self.load_all()
            self.ids[content_type] = sorted(['%s' % item.id for item in items])
            self.save_cache()
        return items

    def add(self, content_type, item_ids):
        ok = Favorites.add(self, content_type, item_ids)
        if ok:
            self.get(content_type)
        return ok

    def remove(self, content_type, item_id):
        ok = Favorites.remove(self, content_type, item_id)
        if ok:
            self.get(content_type)
        return ok

    def isFavoriteArtist(self, artist_id):
        self.load_all()
        return Favorites.isFavoriteArtist(self, artist_id)

    def isFavoriteAlbum(self, album_id):
        self.load_all()
        return Favorites.isFavoriteAlbum(self, album_id)

    def isFavoritePlaylist(self, playlist_id):
        self.load_all()
        return Favorites.isFavoritePlaylist(self, playlist_id)

    def isFavoriteTrack(self, track_id):
        self.load_all()
        return Favorites.isFavoriteTrack(self, track_id)

    def isFavoriteVideo(self, video_id):
        self.load_all()
        return Favorites.isFavoriteVideo(self, video_id)

    def isLockedArtist(self, artist_id):
        self.load_all()
        return '%s' % artist_id in self.ids.get('locked_artists', [])

    def setLockedArtist(self, artist_id, lock=True):
        self.load_all()
        actually_locked = self.isLockedArtist(artist_id)
        ok = True
        if lock != actually_locked:
            try:
                if lock:
                    self.ids['locked_artists'].append('%s' % artist_id)
                    self.ids['locked_artists'] = sorted(self.ids['locked_artists'])
                else:
                    self.ids['locked_artists'].remove('%s' % artist_id)
                self.save_cache()
            except:
                ok = False
        return ok


class TidalUser(User):

    def __init__(self, session, user_id, subscription_type=SubscriptionType.hifi):
        User.__init__(self, session, user_id, subscription_type)
        self.favorites = TidalFavorites(session, user_id)
        self.playlists_loaded = False
        self.playlists_cache = {}

    def load_cache(self):
        try:
            fd = xbmcvfs.File(PLAYLISTS_FILE, 'r')
            self.playlists_cache = eval(fd.read())
            fd.close()
            self.playlists_loaded = True
            log('Loaded %s Playlists from disk.' % len(self.playlists_cache.keys()))
        except:
            self.playlists_loaded = False
            self.playlists_cache = {}
        return self.playlists_loaded

    def save_cache(self):
        try:
            if self.playlists_loaded:
                fd = xbmcvfs.File(PLAYLISTS_FILE, 'w')
                fd.write(repr(self.playlists_cache))
                fd.close()
                log('Saved %s Playlists to disk.' % len(self.playlists_cache.keys()))
        except:
            return False
        return True

    def check_updated_playlist(self, playlist):
        if self.playlists_cache.get(playlist.id, {}).get('lastUpdated', datetime.datetime.fromordinal(1)) == playlist.lastUpdated:
            # Playlist unchanged
            return False
        #if playlist.numberOfVideos == 0:
        #    items = self._session.get_playlist_tracks(playlist)
        #else:
        items = self._session.get_playlist_items(playlist)
        album_ids = []
        if ALBUM_PLAYLIST_TAG in playlist.description:
            album_ids = ['%s' % item.album.id for item in items if (isinstance(item, TrackItem) or (isinstance(item, VideoItem) and item.album))]
        # Save Track-IDs into Buffer
        self.playlists_cache.update({playlist.id: {'title': playlist.title,
                                                   'description': playlist.description,
                                                   'lastUpdated': playlist.lastUpdated,
                                                   'ids': ['%s' % item.id for item in items],
                                                   'album_ids': album_ids}})
        return True

    def delete_cache(self):
        try:
            if xbmcvfs.exists(PLAYLISTS_FILE):
                xbmcvfs.delete(PLAYLISTS_FILE)
                log('Deleted Playlists file.')
                self.playlists_loaded = False
                self.playlists_cache = {}
        except:
            return False
        return True

    def playlists_of_id(self, item_id, album_id=None):
        userpl = {}
        if not self.playlists_loaded:
            self.load_cache()
        if not self.playlists_loaded:
            self.playlists()
        plids = self.playlists_cache.keys()
        for plid in plids:
            if item_id and '%s' % item_id in self.playlists_cache.get(plid).get('ids', []):
                userpl.update({plid: self.playlists_cache.get(plid)})
            if album_id and '%s' % album_id in self.playlists_cache.get(plid).get('album_ids', []):
                userpl.update({plid: self.playlists_cache.get(plid)})
        return userpl

    def playlists(self):
        items = User.playlists(self, offset=0, limit=9999)
        # Refresh the Playlist Cache
        if not self.playlists_loaded:
            self.load_cache()
        buffer_changed = False
        act_ids = [item.id for item in items]
        saved_ids = self.playlists_cache.keys()
        # Remove Deleted Playlists from Cache
        for plid in saved_ids:
            if plid not in act_ids:
                self.playlists_cache.pop(plid)
                buffer_changed = True
        # Update modified Playlists in Cache
        self.playlists_loaded = True
        for item in items:
            if self.check_updated_playlist(item):
                buffer_changed = True
        if buffer_changed:
            self.save_cache()
        return items

    def add_playlist_entries(self, playlist=None, item_ids=[]):
        ok = User.add_playlist_entries(self, playlist=playlist, item_ids=item_ids)
        if ok:
            self.playlists()
        return ok

    def remove_playlist_entry(self, playlist, entry_no=None, item_id=None):
        ok = User.remove_playlist_entry(self, playlist, entry_no=entry_no, item_id=item_id)
        if ok:
            self.playlists()
        return ok

    def delete_playlist(self, playlist_id):
        ok = User.delete_playlist(self, playlist_id)
        if ok:
            self.playlists()
        return ok

    def renamePlaylistDialog(self, playlist):
        dialog = xbmcgui.Dialog()
        title = dialog.input(_T(30233), playlist.title, type=xbmcgui.INPUT_ALPHANUM)
        ok = False
        if title:
            description = dialog.input(_T(30234), playlist.description, type=xbmcgui.INPUT_ALPHANUM)
            ok = self.rename_playlist(playlist, title, description)
        return ok

    def newPlaylistDialog(self):
        dialog = xbmcgui.Dialog()
        title = dialog.input(_T(30233), type=xbmcgui.INPUT_ALPHANUM)
        item = None
        if title:
            description = dialog.input(_T(30234), type=xbmcgui.INPUT_ALPHANUM)
            item = self.create_playlist(title, description)
        return item

    def selectPlaylistDialog(self, headline=None, allowNew=False):
        if not self._session.is_logged_in:
            return None
        try:
            if not headline:
                headline = _T(30238)
            items = self.playlists()
            dialog = xbmcgui.Dialog()
            item_list = [item.title for item in items]
            if allowNew:
                item_list.append(_T(30237))
        except Exception as e:
            log(str(e), level=xbmc.LOGERROR)
            return None
        selected = dialog.select(headline, item_list)
        if selected >= len(items):
            item = self.newPlaylistDialog()
            return item
        elif selected >= 0:
            return items[selected]
        return None


