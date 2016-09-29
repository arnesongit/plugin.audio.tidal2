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

import sys
import os
import datetime
import requests
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
import xbmc
import xbmcgui
import xbmcvfs

from lib.koditidal import AlbumItem, ArtistItem, PlaylistItem, TrackItem, VideoItem, PromotionItem, CategoryItem, FolderItem
from lib.koditidal import plugin, addon, _T, log, TidalSession, TidalConfig
from lib.tidalapi import Favorites, User, SubscriptionType, Quality


FOLDER_MASK = '[COLOR blue]%s[/COLOR]'
FAVORITE_MASK = '[COLOR yellow]%s[/COLOR]'
STREAM_LOCKED_MASK = '[COLOR maroon]%s (%s)[/COLOR]'
USER_PLAYLIST_MASK = ' [COLOR limegreen][%s][/COLOR]'


CACHE_DIR = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
FAVORITES_FILE = os.path.join(CACHE_DIR, 'favorites.cfg')
PLAYLISTS_FILE = os.path.join(CACHE_DIR, 'playlists.cfg')


class AlbumItem2(AlbumItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]

    def getLabel(self):
        label1 = self.artist.name
        if self.artist._isFavorite:
            label1 = FAVORITE_MASK % label1
        label2 = self.title
        if self.type == 'EP':
            label2 += ' (EP)'
        elif self.type == 'SINGLE':
            label2 += ' (Single)'
        if getattr(self, 'year', None):
            label2 += ' (%s)' % self.year
        if self._isFavorite and not '/favorites/' in sys.argv[0]:
            label2 = FAVORITE_MASK % label2
        return '%s - %s' % (label1, label2)


class ArtistItem2(ArtistItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        if self._isFavorite and not '/favorites/' in sys.argv[0]:
            return FAVORITE_MASK % self.name
        return self.name


class PlaylistItem2(PlaylistItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        if self._isFavorite and not '/favorites/' in sys.argv[0]:
            return FAVORITE_MASK % self.name
        return self.name


class TrackItem2(TrackItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]
        self.album = AlbumItem2(self.album)
        if self.explicit and not 'Explicit' in self.title:
            self.title += ' (Explicit)'
        self._userplaylists = {} # Filled by parser

    def getLabel(self):
        label1 = self.artist.name
        if self.artist._isFavorite and self.available:
            label1 = FAVORITE_MASK % label1
        label2 = self.title
        if self._isFavorite and self.available and not '/favorites/' in sys.argv[0]:
            label2 = FAVORITE_MASK % label2
        label = '%s - %s' % (label1, label2)
        if not self.available:
            label = STREAM_LOCKED_MASK % (label, _T(30242))
        txt = []
        plids = self._userplaylists.keys()
        for plid in plids:
            if plid <> self._playlist_id:
                txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if txt:
            label += USER_PLAYLIST_MASK % ', '.join(txt)
        return label

    def getContextMenuItems(self):
        cm = TrackItem.getContextMenuItems(self)
        plids = self._userplaylists.keys()
        idx = 0
        for cmitem in cm:
            idx = idx + 1
            if 'user_playlist' in cmitem[1]:
                break
        for plid in plids:
            if plid <> self._playlist_id:
                cm.insert(idx, ((_T(30247) % self._userplaylists[plid].get('title'), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
                idx = idx + 1
        return cm


class VideoItem2(VideoItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]
        if self.explicit and not 'Explicit' in self.title:
            self.title += ' (Explicit)'
        self._userplaylists = {} # Filled by parser

    def getLabel(self):
        label1 = self.artist.name
        if self.artist._isFavorite and self.available:
            label1 = FAVORITE_MASK % label1
        label2 = self.title
        if getattr(self, 'year', None):
            label2 += ' (%s)' % self.year
        if self._isFavorite and self.available and not '/favorites/' in sys.argv[0]:
            label2 = FAVORITE_MASK % label2
        label = '%s - %s' % (label1, label2)
        if not self.available:
            label = STREAM_LOCKED_MASK % (label, _T(30242))
        txt = []
        plids = self._userplaylists.keys()
        for plid in plids:
            if plid <> self._playlist_id:
                txt.append('%s' % self._userplaylists.get(plid).get('title'))
        if txt:
            label += USER_PLAYLIST_MASK % ', '.join(txt)
        return label

    def getContextMenuItems(self):
        cm = VideoItem.getContextMenuItems(self)
        plids = self._userplaylists.keys()
        idx = 0
        for cmitem in cm:
            idx = idx + 1
            if 'user_playlist' in cmitem[1]:
                break
        for plid in plids:
            if plid <> self._playlist_id:
                cm.insert(idx, ((_T(30247) % self._userplaylists[plid].get('title'), 'RunPlugin(%s)' % plugin.url_for_path('/user_playlist/remove_id/%s/%s' % (plid, self.id)))))
                idx = idx + 1
        return cm


class PromotionItem2(PromotionItem):

    def __init__(self, item):
        if item.type != 'EXTURL' and item.id.startswith('http:'):
            item.type = 'EXTURL' # Fix some defect TIDAL Promotions
        self.__dict__.update(vars(item))

    def getLabel(self):
        if self.type in ['ALBUM', 'VIDEO']:
            label = '%s - %s' % (self.shortHeader, self.shortSubHeader)
        else:
            label = self.shortHeader
        if self._isFavorite:
            label = FAVORITE_MASK % label
        return label


class CategoryItem2(CategoryItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))

    def getLabel(self):
        return FOLDER_MASK % CategoryItem.getLabel(self)


class FolderItem2(FolderItem):

    def __init__(self, folder, url, thumb=None, fanart=None, isFolder=True):
        FolderItem.__init__(self, folder, url, thumb, fanart, isFolder)

    def getLabel(self):
        return FOLDER_MASK % FolderItem.getLabel(self)


class LoginToken(object):
    browser = 'wdgaB1CilGA-S_s2' # Streams HIGH/LOW Quality over RTMP, FLAC and Videos over HTTP, but many Lossless Streams are encrypted.
    token1 = 'kgsOOmYk3zShYrNP'  # All Streams are HTTP Streams. Correct numberOfVideos in Playlists (best Token to use)
    token2 = 'P5Xbeo5LFvESeDy6'  # Same function as token1, but Playlist Headers returns only numberOfTracks (numberOfVideos = 0)
    token3 = 'oIaGpqT_vQPnTr0Q'  # Old WIMP-Token, same as token2, but HIGH/LOW Audio Quality uses RTMP protocol
    token4 = '_KM2HixcUBZtmktH'  # Old WIMP-Token which still works.
    token5 = '4zx46pyr9o8qZNRw'  # Other old Token that still works, but many FLAC streams are encrypted.
    # Tokens which return correct numberOfVideos in Playlists
    api_tokens = [token1, browser]
    # Tokens which streams all FLAC content (no encryped streams)
    hifi_tokens = [token1, token2, token3, token4]
    # All Tokens to play HIGH/LOW quality
    premium_tokens = [token1, browser, token2, token3, token4, token5]


class TidalConfig2(TidalConfig):

    def __init__(self):
        TidalConfig.__init__(self)

    def load(self):
        TidalConfig.load(self)
        self.stream_session_id = addon.getSetting('stream_session_id')
        if not self.stream_session_id:
            self.stream_session_id = self.session_id


class TidalSession2(TidalSession):

    def __init__(self, config=TidalConfig2()):
        TidalSession.__init__(self, config=config)

    def init_user(self, user_id, subscription_type):
        return User2(self, user_id, subscription_type)

    def load_session(self):
        TidalSession.load_session(self)
        self.stream_session_id = self._config.stream_session_id

    def login(self, username, password, subscription_type=None, loginToken=None):
        if loginToken == None:
            ok = TidalSession.login(self, username, password, subscription_type=subscription_type)
            if ok:
                self.stream_session_id = self.session_id
                addon.setSetting('stream_session_id', self.stream_session_id)
                self._config.load()
                return ok
        if not username or not password:
            return False
        if not subscription_type:
            # Set Subscription Type corresponding to the given playback quality
            subscription_type = SubscriptionType.hifi if self._config.quality == Quality.lossless else SubscriptionType.premium
        if loginToken:
            tokens = [loginToken]  # Using only the given token
        elif subscription_type == SubscriptionType.hifi:
            tokens = LoginToken.hifi_tokens  # Using tokens with correct FLAC Streaming
        else:
            tokens = LoginToken.premium_tokens  # Using universal tokens for HIGH/LOW Quality
        if not self.client_unique_key:
            # Generate a random client key if no key is given
            self.client_unique_key = self.generate_client_unique_key()
        url = urljoin(self._config.api_location, 'login/username')
        payload = {
            'username': username,
            'password': password,
            'clientUniqueKey': self.client_unique_key
        }
        log('Using clientUniqueKey "%s"' % self.client_unique_key)
        working_token = ''
        for token in tokens:
            headers = { "X-Tidal-Token": token }
            r = requests.post(url, data=payload, headers=headers)
            if not r.ok:
                try:
                    msg = r.json().get('userMessage')
                except:
                    msg = r.reason
                log(msg, level=xbmc.LOGERROR)
                log('Login-Token "%s" didn\'t work' % token, level=xbmc.LOGERROR)
            else:
                try:
                    body = r.json()
                    self.session_id = body['sessionId']
                    self.stream_session_id = self.session_id
                    self.country_code = body['countryCode']
                    self.user = self.init_user(user_id=body['userId'], subscription_type=subscription_type)
                    working_token = token
                    log('Using Login-Token "%s"' % working_token)
                    break
                except:
                    log('Login-Token "%s" failed.' % token, level=xbmc.LOGERROR)

        if working_token not in LoginToken.api_tokens:
            # Try to get a valid API Token for Videos in Playlists
            for token in LoginToken.api_tokens:
                headers = { "X-Tidal-Token": token }
                r = requests.post(url, data=payload, headers=headers)
                if not r.ok:
                    try:
                        msg = r.json().get('userMessage')
                    except:
                        msg = r.reason
                    log(msg, level=xbmc.LOGERROR)
                    log('API-Token "%s" failed.' % token, level=xbmc.LOGERROR)
                else:
                    try:
                        body = r.json()
                        self.session_id = body['sessionId']
                        if not self.user:
                            # Previous login token(s) failed
                            log('All Login-Tokens failed. Normal API-Key will be used for streaming.', level=xbmc.LOGERROR)
                            self.stream_session_id = self.api_session_id
                            self.country_code = body['countryCode']
                            self.user = self.init_user(user_id=body['userId'], subscription_type=subscription_type)
                        log('Using API-Token "%s"' % token)
                        break
                    except:
                        log('API-Token "%s" failed.' % token, level=xbmc.LOGERROR)

        if self.is_logged_in:
            addon.setSetting('session_id', self.session_id)
            addon.setSetting('stream_session_id', self.stream_session_id)
            addon.setSetting('country_code', self.country_code)
            addon.setSetting('user_id', unicode(self.user.id))
            addon.setSetting('subscription_type', '0' if self.user.subscription.type == SubscriptionType.hifi else '1')
            addon.setSetting('client_unique_key', self.client_unique_key)
            self._config.load()

        return self.is_logged_in

    def logout(self):
        TidalSession.logout(self)
        self.stream_session_id = None
        addon.setSetting('stream_session_id', '')
        self._config.load()

    def _parse_album(self, json_obj, artist=None):
        album = AlbumItem2(TidalSession._parse_album(self, json_obj, artist=artist))
        return album

    def _parse_artist(self, json_obj):
        artist = ArtistItem2(TidalSession._parse_artist(self, json_obj))
        return artist

    def _parse_playlist(self, json_obj):
        playlist = PlaylistItem2(TidalSession._parse_playlist(self, json_obj))
        return playlist

    def _parse_track(self, json_obj):
        track = TrackItem2(TidalSession._parse_track(self, json_obj))
        if self.is_logged_in:
            track._userplaylists = self.user.playlists_of_id(track.id)
        elif track.duration > 30:
            # 30 Seconds Limit in Trial Mode
            track.duration = 30
        return track

    def _parse_video(self, json_obj):
        video = VideoItem2(TidalSession._parse_video(self, json_obj))
        if self.is_logged_in:
            video._userplaylists = self.user.playlists_of_id(video.id)
        elif video.duration > 30:
            # 30 Seconds Limit in Trial Mode
            video.duration = 30
        return video

    def _parse_promotion(self, json_obj):
        promotion = PromotionItem2(TidalSession._parse_promotion(self, json_obj))
        return promotion

    def _parse_category(self, json_obj):
        return CategoryItem2(TidalSession._parse_category(self, json_obj))

    def get_media_url(self, track_id, quality=None):
        oldSessionId = self.session_id
        self.session_id = self.stream_session_id
        url = TidalSession.get_media_url(self, track_id, quality=quality)
        if not '.flac' in url.lower() and (quality == Quality.lossless or (quality == None and self._config.quality == Quality.lossless)):
            xbmcgui.Dialog().notification(plugin.name, 'Only HIGH Quality !' , icon=xbmcgui.NOTIFICATION_WARNING)
        self.session_id = oldSessionId
        return url

    def get_video_url(self, video_id):
        oldSessionId = self.session_id
        self.session_id = self.stream_session_id
        url = TidalSession.get_video_url(self, video_id)
        self.session_id = oldSessionId
        return url

    def add_list_items(self, items, content=None, end=True, withNextPage=False):
        TidalSession.add_list_items(self, items, content=content, end=end, withNextPage=withNextPage)
        if end:
            xbmc.executebuiltin('Container.SetViewMode(506)')

    def add_directory_item(self, title, endpoint, thumb=None, fanart=None, end=False, isFolder=True):
        if callable(endpoint):
            endpoint = plugin.url_for(endpoint)
        item = FolderItem2(title, endpoint, thumb, fanart, isFolder)
        self.add_list_items([item], end=end)


class Favorites2(Favorites):

    def __init__(self, session, user_id):
        Favorites.__init__(self, session, user_id)

    def load_cache(self):
        try:
            fd = xbmcvfs.File(FAVORITES_FILE, 'r')
            self.ids = eval(fd.read())
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
                fd = xbmcvfs.File(FAVORITES_FILE, 'w')
                fd.write(repr(self.ids))
                fd.close()
                log('Saved %s Favorites to disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
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
            self.ids[content_type] = ['%s' % item.id for item in items]
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


class User2(User):

    def __init__(self, session, user_id, subscription_type=SubscriptionType.hifi):
        User.__init__(self, session, user_id, subscription_type)
        self.favorites = Favorites2(session, user_id)
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
        items = self._session.get_playlist_items(playlist=playlist)
        self.playlists_cache.update({playlist.id: {'title': playlist.title, 
                                                   'description': playlist.description,
                                                   'lastUpdated': playlist.lastUpdated,
                                                   'ids': [item.id for item in items]}})
        return True

    def delete_cache(self):
        try:
            if xbmcvfs.exists(PLAYLISTS_FILE):
                xbmcvfs.delete(PLAYLISTS_FILE)
                log('Deleted Playlists file.')
        except:
            return False
        return True

    def playlists_of_id(self, item_id):
        userpl = {}
        if not self.playlists_loaded:
            self.load_cache()
        if not self.playlists_loaded:
            self.playlists()
        plids = self.playlists_cache.keys()
        for plid in plids:
            if item_id in self.playlists_cache.get(plid).get('ids', []):
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

    def remove_playlist_entry(self, playlist_id, entry_no=None, item_id=None):
        ok = User.remove_playlist_entry(self, playlist_id, entry_no=entry_no, item_id=item_id)
        if ok:
            self.playlists()
        return ok

    def delete_playlist(self, playlist_id):
        ok = User.delete_playlist(self, playlist_id)
        if ok:
            self.playlists()
        return ok
