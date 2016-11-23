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

import traceback
from threading import Thread
from Queue import Queue
import requests
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
import xbmc
import xbmcgui

from koditidal import HasListItem, AlbumItem, ArtistItem, PlaylistItem, TrackItem, VideoItem, PromotionItem, CategoryItem, FolderItem
from koditidal import plugin, addon, log, _T, TidalSession, TidalUser, TidalFavorites, TidalConfig
from tidalapi import SubscriptionType, Quality
from metacache import MetaCache

ALL_SAERCH_FIELDS = ['ARTISTS','ALBUMS','PLAYLISTS','TRACKS','VIDEOS']


class ColoredListItem(HasListItem):

    def setLabelFormat(self):
        HasListItem.setLabelFormat(self)
        if addon.getSetting('color_mode') == 'true':
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


class AlbumItem2(AlbumItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]


class ArtistItem2(ArtistItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))


class PlaylistItem2(PlaylistItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))


class TrackItem2(TrackItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]
        self.album = AlbumItem2(self.album)
        self.titleForLabel = self.title
        if self.explicit and not 'Explicit' in self.title:
            self.titleForLabel += ' (Explicit)'

    def getComment(self):
        txt = TrackItem.getComment(self)
        comments = ['track_id=%s' % self.id]
        if txt:
            comments.append(txt)
        userpl = self._userplaylists.keys()
        if len(userpl) > 0:
            comments.append('UserPlaylists: %s' % ', '.join([self._userplaylists.get(plid).get('title') for plid in userpl]))
        return ', '.join(comments)


class VideoItem2(VideoItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))
        self.artist = ArtistItem2(self.artist)
        self.artists = [ArtistItem2(artist) for artist in self.artists]
        self._ftArtists = [ArtistItem2(artist) for artist in self._ftArtists]
        self.titleForLabel = self.title
        if self.explicit and not 'Explicit' in self.title:
            self.titleForLabel += ' (Explicit)'

    def getComment(self):
        txt = VideoItem.getComment(self)
        comments = ['video_id=%s' % self.id]
        if txt:
            comments.append(txt)
        userpl = self._userplaylists.keys()
        if len(userpl) > 0:
            comments.append('UserPlaylists: %s' % ', '.join([self._userplaylists.get(plid).get('title') for plid in userpl]))
        return ', '.join(comments)


class PromotionItem2(PromotionItem, ColoredListItem):

    def __init__(self, item):
        if item.type != 'EXTURL' and item.id.startswith('http:'):
            item.type = 'EXTURL' # Fix some defect TIDAL Promotions
        self.__dict__.update(vars(item))


class CategoryItem2(CategoryItem, ColoredListItem):

    def __init__(self, item):
        self.__dict__.update(vars(item))


class FolderItem2(FolderItem, ColoredListItem):

    def __init__(self, folder, url, thumb=None, fanart=None, isFolder=True, label=None):
        FolderItem.__init__(self, folder, url, thumb, fanart, isFolder, label)


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
        self.max_http_requests = int('0%s' % addon.getSetting('max_http_requests'))
        self.cache_albums = True if addon.getSetting('album_cache') == 'true' else False


class TidalSession2(TidalSession):

    def __init__(self, config=TidalConfig2()):
        TidalSession.__init__(self, config=config)
        # Album Cache
        self.metaCache = MetaCache()
        self.albumJsonBuffer = {}
        self.abortAlbumThreads = True
        self.albumQueue = Queue()

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

    def search(self, field, value, limit=50):
        search_field = field
        if isinstance(search_field, basestring) and search_field.upper() == 'ALL':
            search_field = ALL_SAERCH_FIELDS
        results = TidalSession.search(self, search_field, value, limit=limit)
        self.update_albums_in_items(results.tracks)
        return results

    def get_album(self, album_id, withCache=True):
        if withCache and self._config.cache_albums:
            # Try internal buffer first
            json_obj = self.albumJsonBuffer.get('%s' % album_id, None)
            if json_obj == None:
                # Now read from Cache Database
                json_obj = self.metaCache.getAlbumJson(album_id)
                if json_obj != None and 'id' in json_obj:
                    # Transfer into the local buffer
                    self.albumJsonBuffer['%s' % json_obj.get('id')] = json_obj
            if json_obj:
                return self._parse_album(json_obj)
        return TidalSession.get_album(self, album_id)

    def get_album_items(self, album_id, ret='playlistitems'):
        items = TidalSession.get_album_items(self, album_id, ret=ret)
        videos = [item for item in items if isinstance(item, VideoItem)]
        if len(videos) == 0 and self._config.cache_albums and not ret.startswith('track'):
            self.metaCache.delete('album_with_videos', album_id)
        return items

    def get_playlist_items(self, playlist_id=None, playlist=None, offset=0, limit=9999, ret='playlistitems'):
        items = TidalSession.get_playlist_items(self, playlist_id=playlist_id, playlist=playlist, offset=offset, limit=limit, ret=ret)
        self.update_albums_in_items(items)
        return items

    def get_playlist_tracks(self, playlist_id, offset=0, limit=9999):
        items = TidalSession.get_playlist_tracks(self, playlist_id, offset=offset, limit=limit)
        self.update_albums_in_items(items)
        return items

    def get_category_content(self, group, path, content_type, offset=0, limit=999):
        items = TidalSession.get_category_content(self, group, path, content_type, offset=offset, limit=limit)
        if content_type.startswith('track'):
            self.update_albums_in_items(items)
        elif content_type.startswith('album'):
            self.save_album_cache()
        return items

    def _parse_one_item(self, json_obj, ret):
        if self._config.cache_albums and ret.startswith('album') and json_obj and 'id' in json_obj:
            # Update local Album Buffer
            self.albumJsonBuffer['%s' % json_obj.get('id')] = json_obj
        return TidalSession._parse_one_item(self, json_obj, ret=ret)

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
        return track

    def _parse_video(self, json_obj):
        video = VideoItem2(TidalSession._parse_video(self, json_obj))
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
            xbmcgui.Dialog().notification(plugin.name, _T(30504) , icon=xbmcgui.NOTIFICATION_WARNING)
        self.session_id = oldSessionId
        return url

    def get_video_url(self, video_id, maxHeight=-1):
        oldSessionId = self.session_id
        self.session_id = self.stream_session_id
        url = TidalSession.get_video_url(self, video_id, maxHeight)
        self.session_id = oldSessionId
        return url

    def add_list_items(self, items, content=None, end=True, withNextPage=False):
        TidalSession.add_list_items(self, items, content=content, end=end, withNextPage=withNextPage)
        if end:
            try:
                self.save_album_cache()
                kodiVersion = xbmc.getInfoLabel('System.BuildVersion').split()[0]
                kodiVersion = kodiVersion.split('.')[0]
                skinTheme = xbmc.getSkinDir().lower()
                if 'onfluence' in skinTheme:
                    if kodiVersion <= '16' or content <> 'musicvideos':
                        xbmc.executebuiltin('Container.SetViewMode(506)')
                    else:
                        xbmc.executebuiltin('Container.SetViewMode(511)')
                elif 'estuary' in skinTheme:
                    xbmc.executebuiltin('Container.SetViewMode(55)')
            except:
                pass

    def add_directory_item(self, title, endpoint, thumb=None, fanart=None, end=False, isFolder=True, label=None):
        if callable(endpoint):
            endpoint = plugin.url_for(endpoint)
        item = FolderItem2(title, endpoint, thumb, fanart, isFolder, label)
        self.add_list_items([item], end=end)

    def get_album_json_thread(self):
        try:
            while not xbmc.abortRequested and not self.abortAlbumThreads:
                try:
                    album_id = self.albumQueue.get_nowait()
                except:
                    break
                try:
                    self.get_album(album_id, withCache=False)
                except requests.HTTPError as e:
                    r = e.response
                    msg = _T(30505)
                    try:
                        msg = r.reason
                        msg = r.json().get('userMessage')
                    except:
                        pass
                    log('Error getting Album ID %s' % album_id, xbmc.LOGERROR)
                    if r.status_code == 429 and not self.abortAlbumThreads:
                        self.abortAlbumThreads = True
                        log('Too many requests. Aborting Workers ...', xbmc.LOGERROR)
                        self.albumQueue._init(9999)
                        xbmcgui.Dialog().notification(plugin.name, msg, xbmcgui.NOTIFICATION_ERROR)
        except Exception, e:
            traceback.print_exc()

    def update_albums_in_items(self, items):
        if self._config.cache_albums:
            # Step 1: Read all available Albums from Cache
            self.albumQueue = Queue()
            missing_ids = []
            missing_items = []
            track_count = 0
            self.abortAlbumThreads = False
            for item in items:
                if isinstance(item, TrackItem):
                    track_count += 1
                    try:
                        isAlbum = abs(int('%s' % item.id) - int('%s' % item.album.id)) > 1
                    except:
                        isAlbum = True
                    if item.available and not item.album.releaseDate and isAlbum:
                        #(item.title <> item.album.title or item.trackNumber > 1):
                        # Try to read Album from Cache
                        json_obj = self.albumJsonBuffer.get('%s' % item.album.id, None)
                        if json_obj == None:
                            json_obj = self.metaCache.getAlbumJson(item.album.id)
                        if json_obj != None:
                            item.album = self._parse_album(json_obj)
                        else:
                            missing_items.append(item)
                            if not item.album.id in missing_ids:
                                missing_ids.append(item.album.id)
                                self.albumQueue.put('%s' % item.album.id)
            # Step 2: Load JSon-Data from all missing Albums
            if len(missing_ids) <= 5 or self._config.max_http_requests <= 1:
                # Without threads
                self.get_album_json_thread()
            else:
                log('Starting Threads to load Albums')
                runningThreads = []
                while len(runningThreads) < self._config.max_http_requests:
                    try:
                        worker = Thread(target=self.get_album_json_thread)
                        worker.start()
                        runningThreads.append(worker)
                    except Exception, e:
                        log(str(e), xbmc.LOGERROR)
                log('Waiting until all Threads are terminated')
                for worker in runningThreads:
                    worker.join(20)
                    if worker.isAlive():
                        log('Worker %s is still running ...' % worker.ident, xbmc.LOGWARNING)
            # Step 3: Save JsonData into MetaCache
            if len(missing_items) > 0:
                numAlbums = self.save_album_cache()
                log('Cached %s from %s missing Albums for %s TrackItems' % (numAlbums, len(missing_items), track_count))
                # Step 4: Fill missing Albums into the TrackItems
                for item in missing_items:
                    json_obj = self.albumJsonBuffer.get('%s' % item.album.id, None)
                    if json_obj != None:
                        item.album = self._parse_album(json_obj)

    def save_album_cache(self):
        numAlbums = 0
        if self._config.cache_albums:
            album_ids = self.albumJsonBuffer.keys()
            for album_id in album_ids:
                if xbmc.abortRequested:
                    break
                json_obj = self.albumJsonBuffer.get(album_id, None)
                if json_obj != None and 'id' in json_obj and not json_obj.get('_cached', False):
                    numAlbums += 1
                    self.metaCache.insertAlbumJson(json_obj)
            if numAlbums > 0:
                log('Wrote %s from %s Albums into the MetaCache' % (numAlbums, len(album_ids)))
        return numAlbums

    def albums_with_videos(self):
        items = []
        if self.metaCache:
            jsonList = self.metaCache.fetchAllData('album_with_videos')
            for json in jsonList:
                items.append(self._parse_one_item(json, ret='album'))
        return items


class Favorites2(TidalFavorites):

    def __init__(self, session, user_id):
        TidalFavorites.__init__(self, session, user_id)


class User2(TidalUser):

    def __init__(self, session, user_id, subscription_type=SubscriptionType.hifi):
        TidalUser.__init__(self, session, user_id, subscription_type)
        self.favorites = Favorites2(session, user_id)

    def delete_cache(self):
        ok = TidalUser.delete_cache(self)
        try:
            if getattr(self._session, 'metaCache'):
                ok = self._session.metaCache.deleteDatabase()
        except:
            return False
        return ok 
