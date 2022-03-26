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

import sys
import datetime

from kodi_six import xbmcgui

from .common import Const, KODI_VERSION, plugin
from .textids import Msg, _T, _P
from .config import settings
from .tidalapi import models as tidal

# Convert TIDAL-API Media into Kodi List Items

class ItemSortType(object):
    DATE = 1
    NAME = 2


class HasListItem(object):

    _is_logged_in = False

    def setLabelFormat(self):
        self._favorites_in_labels = settings.favorites_in_labels
        self._user_playlists_in_labels = settings.user_playlists_in_labels
        self._colored_labels = settings.color_mode
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
            self.DEFAULT_PLAYLIST_MASK = '{label} [COLOR limegreen]({mediatype})[/COLOR]'
            self.MASTER_AUDIO_MASK = '{label} [COLOR blue]MQA[/COLOR]'
            self.DOLBY_ATMOS_MASK = '{label} [COLOR lightblue]Atmos[/COLOR]'
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
            self.DOLBY_ATMOS_MASK = '{label} (Atmos)'

    def getLabel(self, extended=True):
        return self.name

    def getListItem(self):
        li = xbmcgui.ListItem(self.getLabel())
        if isinstance(self, tidal.PlayableMedia) and getattr(self, 'available', True):
            li.setProperty('isplayable', 'true')
        artwork = {'thumb': Const.addon_icon, 'fanart': Const.addon_fanart}
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

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        if sortType == ItemSortType.DATE:
            return '19000101%08d' % self._itemPosition
        return '%s %08d' % (self.getLabel(extended=False), self._itemPosition)


class AlbumItem(tidal.Album, HasListItem):

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
        if self.type == tidal.AlbumType.ep:
            longTitle += ' (EP)'
        elif self.type == tidal.AlbumType.single:
            longTitle += ' (Single)'
        if self.explicit and not 'Explicit' in self.title:
            longTitle += ' (Explicit)'
        if getattr(self, 'year', None) and settings.album_year_in_labels:
            if self.releaseDate and self.releaseDate > datetime.datetime.now():
                longTitle += ' (%s)' % _T(Msg.i30268).format(self.releaseDate)
            else:
                longTitle += ' (%s)' % self.year
        if self.isMasterAlbum and settings.mqa_in_labels:
            longTitle = self.MASTER_AUDIO_MASK.format(label=longTitle)
        if self.isDolbyAtmos and settings.mqa_in_labels:
            longTitle = self.DOLBY_ATMOS_MASK.format(label=longTitle)
        return longTitle

    def getSortText(self, mode=None):
        return '%s - (%s) %s' % (self.artist.getLabel(extended=False), getattr(self, 'year', ''), self.getLongTitle())

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.releaseDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.releaseDate.year, self.releaseDate.month, self.releaseDate.day, self._itemPosition)
                elif isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

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
                cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/albums/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/albums/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(Msg.i30240).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
                cm.append((_T(Msg.i30248).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, self._playlist_track_id))))
            cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/album/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    cm.append(((_T(Msg.i30247).format(name=self._userplaylists[plid].get('title'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_album/%s/%s' % (plid, self.id)))))
            if len(self.artists) > 1:
                cm.append((_T(Msg.i30221), 'RunPlugin(%s)' % plugin.url_for_path('/artists/%s' % '-'.join(['%s' % artist.id for artist in self.artists]))))
            else:
                cm.append((_T(Msg.i30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        return cm


class ArtistItem(tidal.Artist, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self._isLocked = True if tidal.VARIOUS_ARTIST_ID == '%s' % self.id else False

    def getLabel(self, extended=True):
        self.setLabelFormat()
        if extended and self._isFavorite and not '/favorites/artists' in sys.argv[0]:
            return self.FAVORITE_MASK.format(label=self.name)
        if self._isLocked and '/favorites/artists' in sys.argv[0]:
            return self.STREAM_LOCKED_MASK.format(label=self.name, info=_T(Msg.i30260))
        return self.name

    def getSortCriteria(self, sortType=None):
        return HasListItem.getSortCriteria(self, sortType=ItemSortType.NAME)

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
                cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/artists/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/artists/%s' % self.id)))
            if '/favorites/artists' in sys.argv[0]:
                if self._isLocked:
                    cm.append((_T(Msg.i30262), 'RunPlugin(%s)' % plugin.url_for_path('/unlock_artist/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30261), 'RunPlugin(%s)' % plugin.url_for_path('/lock_artist/%s' % self.id)))
        return cm

    @property
    def fanart(self):
        if self.picture:
            return tidal.IMG_URL.format(picture=self.picture.replace('-', '/'), size='1080x720')
        if settings.fanart_server_enabled:
            return 'http://localhost:%s/artist_fanart?id=%s' % (settings.fanart_server_port, self.id)
        return None


class FolderItem(tidal.Folder, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.name
        if extended:
            label = self.FOLDER_MASK.format(label=label)
            if str(self.id) == settings.default_folder_id:
                return self.DEFAULT_PLAYLIST_MASK.format(label=label, mediatype=_P('playlists'))
        return label

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/user_folders/%s' % self.id)
        infoLabel = {
            'artist': self.name,
            'title': '%s: %s' % (_P('playlists'), self.totalNumberOfItems),
            'genre': '%s: %s' % (_P('playlists'), self.totalNumberOfItems),
            'tracknumber': self._itemPosition + 1 if self._itemPosition >= 0 else 0
        }
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'mediatype': 'music'})
        try:
            if self.lastModifiedAt:
                infoLabel.update({'date': self.lastModifiedAt.date().strftime('%d.%m.%Y')})
            elif self.createdAt:
                infoLabel.update({'date': self.createdAt.date().strftime('%d.%m.%Y')})
        except:
            pass
        li.setInfo('music', infoLabel)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        cm.append((_T(Msg.i30251).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/rename/%s' % self.id)))
        if self.totalNumberOfItems == 0:
            cm.append((_T(Msg.i30235).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/delete/%s' % self.id)))
        cm.append((_T(Msg.i30237).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/create')))
        if str(self.id) == settings.default_folder_id:
            cm.append((_T(Msg.i30250).format(what=_P('playlist')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/folder')))
        else:
            cm.append((_T(Msg.i30249).format(what=_P('playlist')), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/folder/%s' % self.id)))
        return cm


class MixItem(tidal.Mix, HasListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.getLongTitle()
        if extended and self._isFavorite and not '/favorites/' in sys.argv[0] and not '/folder/' in sys.argv[0]:
            label = self.FAVORITE_MASK.format(label=label)
        return label

    def getLongTitle(self):
        self.setLabelFormat()
        longTitle = '%s' % self.name
        if 'MASTER' in self.mixType and settings.mqa_in_labels:
            longTitle = self.MASTER_AUDIO_MASK.format(label=longTitle)
        if 'DOLBY' in self.mixType and settings.mqa_in_labels:
            longTitle = self.DOLBY_ATMOS_MASK.format(label=longTitle)
        return longTitle

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.dateAdded, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.dateAdded.year, self.dateAdded.month, self.dateAdded.day, self._itemPosition)
                elif isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

    def getListItem(self):
        li = HasListItem.getListItem(self)
        url = plugin.url_for_path('/mix/%s' % self.id)
        infoLabel = {
            'title': self.title,
            'album': self.subTitle
        }
        if KODI_VERSION >= (17, 0):
            infoLabel.update({'mediatype': 'music'})
        li.setInfo('music', infoLabel)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/mixes/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/mixes/%s' % self.id)))
        return cm


class PlaylistItem(tidal.Playlist, HasListItem):

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
        self._parentFolderIdFromCache = False

    def getLabel(self, extended=True):
        self.setLabelFormat()
        label = self.name
        if extended and self._isFavorite and not '/favorites/' in sys.argv[0] and not '/folder/' in sys.argv[0]:
            label = self.FAVORITE_MASK.format(label=label)
        if self.isUserPlaylist and ('user_playlists' in sys.argv[0] or 'user_folders' in sys.argv[0]):
            defaultpl = []
            if str(self.id) == settings.default_trackplaylist_id:
                defaultpl.append(_P('tracks'))
            if str(self.id) == settings.default_videoplaylist_id:
                defaultpl.append(_P('videos'))
            if str(self.id) == settings.default_albumplaylist_id:
                defaultpl.append(_P('albums'))
            if len(defaultpl) > 0:
                return self.DEFAULT_PLAYLIST_MASK.format(label=label, mediatype=', '.join(defaultpl))
        if extended and self.parentFolderId and not 'user_folders' in sys.argv[0]:
            label = self.USER_PLAYLIST_MASK.format(label=label, userpl=self.parentFolderName)
        return label

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.dateAdded, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.dateAdded.year, self.dateAdded.month, self.dateAdded.day, self._itemPosition)
                elif isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

    def getListItem(self):
        li = HasListItem.getListItem(self)
        path = '/playlist/%s/items'
        if self.isUserPlaylist and settings.album_playlist_tag in self.description:
            path = '/playlist/%s/albums'
        url = plugin.url_for_path(path % self.id)
        infoLabel = {
            'artist': self.title,
            'album': self.description,
            'title': _T(Msg.i30243).format(tracks=self.numberOfTracks, videos=self.numberOfVideos),
            'genre': _T(Msg.i30243).format(tracks=self.numberOfTracks, videos=self.numberOfVideos),
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
            infoLabel.update({'mediatype': 'music',
                              'userrating': '%s' % int(round(self.popularity / 10.0))})
        li.setInfo('music', infoLabel)
        return (url, li, True)

    def getContextMenuItems(self):
        cm = []
        if self.numberOfVideos > 0:
            cm.append((_T(Msg.i30252), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/tracks' % self.id)))
        if self.isUserPlaylist and settings.album_playlist_tag in self.description:
            cm.append((_T(Msg.i30254), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/items' % self.id)))
        else:
            cm.append((_T(Msg.i30255), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/albums' % self.id)))
        if self._is_logged_in:
            if self.isUserPlaylist: # and ('user_playlists' in sys.argv[0] or 'user_folders' in sys.argv[0]):
                cm.append((_T(Msg.i30266).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist_cm/%s' % self.id)))
            else:
                if self._isFavorite:
                    cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/playlists/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/playlists/%s' % self.id)))
            cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/playlist/%s' % self.id)))
            if self.parentFolderId:
                cm.append((_T(Msg.i30240).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/remove/%s/%s' % (self.parentFolderId, self.id))))
                cm.append((_T(Msg.i30248).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/move/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30239).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/add/%s' % self.id)))
        return cm


class TrackItem(tidal.Track, HasListItem):

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
            label = self.STREAM_LOCKED_MASK.format(label=label, info=_T(Msg.i30242))
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
        if self.isMqa and settings.mqa_in_labels:
            longTitle = self.MASTER_AUDIO_MASK.format(label=longTitle)
        if self.isDolbyAtmos and settings.mqa_in_labels:
            longTitle = self.DOLBY_ATMOS_MASK.format(label=longTitle)
        return longTitle

    def getSortText(self, mode=None):
        if mode == 'ALBUM':
            return self.album.getSortText(mode=mode)
        return self.getLabel(extended=False)

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

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

    def getListItem(self, lyrics=None):
        li = HasListItem.getListItem(self)
        if self.available:
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
        if lyrics:
            infoLabel.update({'lyrics': lyrics.subtitles})
            li.setProperty('culrc.source', Const.addon_id)
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
                cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/tracks/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/tracks/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(Msg.i30240).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
                cm.append((_T(Msg.i30248).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, self.id))))
            else:
                cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/track/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    playlist = self._userplaylists[plid]
                    if '%s' % self.album.id in playlist.get('album_ids', []):
                        cm.append(((_T(Msg.i30247).format(name=playlist.get('title'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_album/%s/%s' % (plid, self.album.id)))))
                    else:
                        cm.append(((_T(Msg.i30247).format(name=playlist.get('title'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
        if len(self.artists) > 1:
            cm.append((_T(Msg.i30221), 'RunPlugin(%s)' % plugin.url_for_path('/artists/%s' % '-'.join(['%s' % artist.id for artist in self.artists]))))
        else:
            cm.append((_T(Msg.i30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        cm.append((_T(Msg.i30245), 'Container.Update(%s)' % plugin.url_for_path('/album/%s' % self.album.id)))
        cm.append((_T(Msg.i30222), 'Container.Update(%s)' % plugin.url_for_path('/track_radio/%s' % self.id)))
        cm.append((_T(Msg.i30223), 'Container.Update(%s)' % plugin.url_for_path('/recommended/tracks/%s' % self.id)))
        return cm


class VideoItem(tidal.Video, HasListItem):

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
            label = self.STREAM_LOCKED_MASK.format(label=label, info=_T(Msg.i30242))
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

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

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
        # li.setInfo('music', musicLabel)
        li.addStreamInfo('video', { 'codec': 'h264', 'aspect': 1.78, 'width': 1920,
                         'height': 1080, 'duration': self.duration })
        li.addStreamInfo('audio', { 'codec': 'AAC', 'language': 'en', 'channels': 2 })
        return (url, li, isFolder)

    def getContextMenuItems(self):
        cm = []
        if self._is_logged_in:
            if self._isFavorite:
                cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/videos/%s' % self.id)))
            else:
                cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/videos/%s' % self.id)))
            if self._playlist_type == 'USER':
                cm.append((_T(Msg.i30240).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove/%s/%s' % (self._playlist_id, self._playlist_pos))))
                cm.append((_T(Msg.i30248).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/move/%s/%s/%s' % (self._playlist_id, self._playlist_pos, self.id))))
            else:
                cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/video/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                if plid != self._playlist_id:
                    cm.append(((_T(Msg.i30247).format(name=self._userplaylists[plid].get('title'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
        if len(self.artists) > 1:
            cm.append((_T(Msg.i30221), 'RunPlugin(%s)' % plugin.url_for_path('/artists/%s' % '-'.join(['%s' % artist.id for artist in self.artists]))))
        else:
            cm.append((_T(Msg.i30221), 'Container.Update(%s)' % plugin.url_for_path('/artist/%s' % self.artist.id)))
        cm.append((_T(Msg.i30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class PromotionItem(tidal.Promotion, HasListItem):

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
        if extended:
            if self.type == 'PLAYLIST':
                if extended and self.parentFolderId and not 'user_folders' in sys.argv[0]:
                    label = self.USER_PLAYLIST_MASK.format(label=label, userpl=self.parentFolderName)
            else:
                txt = []
                plids = list(self._userplaylists.keys())
                for plid in plids:
                    txt.append('%s' % self._userplaylists.get(plid).get('title'))
                if txt:
                    label = self.USER_PLAYLIST_MASK.format(label=label, userpl=', '.join(txt))
        return label

    def getSortCriteria(self, sortType=ItemSortType.DATE):
        criteria = HasListItem.getSortCriteria(self, sortType=sortType)
        try:
            if sortType == ItemSortType.DATE:
                if isinstance(self.streamStartDate, datetime.datetime):
                    criteria = '%04d%02d%02d%08d' % (self.streamStartDate.year, self.streamStartDate.month, self.streamStartDate.day, self._itemPosition)
        except:
            pass
        return criteria

    def getListItem(self):
        li = HasListItem.getListItem(self)
        isFolder = True
        if self.type == 'PLAYLIST':
            url = plugin.url_for_path('/playlist/%s/items' % self.id)
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
                    cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/playlists/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/playlists/%s' % self.id)))
                cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/playlist/%s' % self.id)))
                if self.parentFolderId:
                    cm.append((_T(Msg.i30240).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/remove/%s/%s' % (self.parentFolderId, self.id))))
                    cm.append((_T(Msg.i30248).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/move/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30239).format(what=_T('folder'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_folder/add/%s' % self.id)))
            cm.append((_T(Msg.i30255), 'Container.Update(%s)' % plugin.url_for_path('/playlist/%s/albums' % self.id)))
        elif self.type == 'ALBUM':
            if self._is_logged_in:
                if self._isFavorite:
                    cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/albums/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/albums/%s' % self.id)))
        elif self.type == 'VIDEO':
            if self._is_logged_in:
                if self._isFavorite:
                    cm.append((_T(Msg.i30220), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/remove/videos/%s' % self.id)))
                else:
                    cm.append((_T(Msg.i30219), 'RunPlugin(%s)' % plugin.url_for_path('/favorites/add/videos/%s' % self.id)))
                cm.append((_T(Msg.i30239).format(what=_T('playlist'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/add/video/%s' % self.id)))
            plids = list(self._userplaylists.keys())
            for plid in plids:
                cm.append(((_T(Msg.i30247).format(name=self._userplaylists[plid].get('title'))+' ...', 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
            cm.append((_T(Msg.i30224), 'Container.Update(%s)' % plugin.url_for_path('/recommended/videos/%s' % self.id)))
        return cm


class CategoryItem(tidal.Category, HasListItem):

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
                url = plugin.url_for_path('/category/%s/%s/%s' % (self._group, self.path, content_type))
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


class DirectoryItem(tidal.BrowsableMedia, HasListItem):

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


# End of File