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
import traceback
import datetime

from kodi_six import xbmc, xbmcvfs, xbmcgui, xbmcplugin
from requests import HTTPError

from .common import KODI_VERSION, plugin
from .textids import Msg, _T
from .debug import log
from .config import settings
from .tidalapi import Session, PKCE_Authenticator, AuthenticationError, User, Favorites, models as tidal
from .items import AlbumItem, ArtistItem, PlaylistItem, TrackItem, VideoItem, MixItem, \
                   FolderItem, CategoryItem, PromotionItem, DirectoryItem, TrackUrlItem, VideoUrlItem, \
                   UserProfileItem, UserPromptItem, BroadcastItem, BroadcastUrlItem


class TidalSession(Session):

    errorCodes = []

    def __init__(self, config=None):
        self._config = config if config else settings
        self._cursor = ''
        self._cursor_pos = 0
        self.user = TidalUser(self)
        self.load_session()

    def cleanup(self):
        if self._config:
            self._config.addon = None
        Session.cleanup(self)

    def load_session(self):
        if not self._config.country_code or self._config.country_code == 'WW':
            self._config.country_code = self.get_country_code()
            if not self._config.country_code or self._config.country_code == 'WW':
                log.error('Failed to retrieve Country Code')
            else:
                settings.setSetting('country_code', self._config.country_code)
                log.info('Initialized Country Code to "%s"' % self._config.country_code)
        if not self._config.user_country_code or self._config.user_country_code == 'WW':
            self._config.user_country_code = self._config.country_code
        if self.is_logged_in:
            self.user.favorites.load_cache()
            self.user.load_cache()

    def check_subscription(self):
        abo = None
        if not self.is_logged_in:
            return abo
        try:
            abo = self.user.subscription()
            if abo:
                self._config.subscription_type = abo.subscription['type']
                log.info('Subscription type is: %s' % self._config.subscription_type)
                settings.setSetting('subscription_type', self._config.subscription_type)
        except Exception as e:
            log.logException(e, 'Failed to get users subscription type')
        return abo

    def login_part1(self, client_id=None, client_secret=None):
        try:
            return Session.login_part1(self, client_id=client_id, client_secret=client_secret)
        except HTTPError as e:
            log.info(str(e))
        return False

    def login_part2(self, device_code=None):
        try:
            auth = None
            progress = None
            start_time = datetime.datetime.now()
            message = _T(Msg.i30209)+'\n'+device_code.verificationUriComplete
            progress = xbmcgui.DialogProgress()
            progress.create(_T(Msg.i30280), message)
            monitor = xbmc.Monitor()
            percent = 0
            while percent < 100:
                progress.update(percent)
                auth = Session.login_part2(self, device_code)
                if auth.success:
                    settings.save_client()
                    settings.save_session()
                    break
                if not auth.authorizationPending or progress.iscanceled() or monitor.waitForAbort(timeout=1):
                    log.warning('Login Session aborted')
                    break
                percent = int(100 * min(device_code.expiresIn, (datetime.datetime.now() - start_time).seconds) / device_code.expiresIn)
        except Exception as e:
            log.logException(e, 'Login failed !')
            xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30253) , icon=xbmcgui.NOTIFICATION_ERROR)
        finally:
            if progress:
                progress.close()
        if auth and not auth.success and not auth.authorizationPending and auth.error:
            xbmcgui.Dialog().ok(plugin.name, '\n'.join([_T(Msg.i30253), auth.error]))
        if auth and auth.success:
            xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30293), icon=xbmcgui.NOTIFICATION_INFO)
        return auth

    def login_pkce_part2(self, pkce):
        try:
            ok = False
            auth = Session.login_pkce_part2(self, pkce)
            if auth.success:
                settings.save_client()
                settings.save_session()
                self.user = TidalUser(self)
                if self.is_logged_in:
                    self.check_subscription()
                    xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30293), icon=xbmcgui.NOTIFICATION_INFO)
                    ok = True
            if not ok:
                if auth.sub_status == 11003:
                    xbmcgui.Dialog().ok(plugin.name, '\n'.join([_T(Msg.i30294), auth.error_description or auth.error]))
                else:
                    xbmcgui.Dialog().ok(plugin.name, '\n'.join([_T(Msg.i30253), auth.error_description or auth.error]))
        except AuthenticationError as e:
            log.logException(e, 'Login failed !')
            xbmcgui.Dialog().ok(plugin.name, 'Authentication failed!\n' + str(e))
        except Exception as e:
            log.logException(e, 'Login failed !')
            xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30253), icon=xbmcgui.NOTIFICATION_ERROR)
        log.info('PKCE login succeeded !' if ok else 'Login process aborted.')
        return ok

    def login_with_code(self, args):
        try:
            ok = False
            if 'code' in args:
                pkce = PKCE_Authenticator(self._config,
                                          client_unique_key = args['client_unique_key'][0],
                                          code_verifier = args['code_verifier'][0],
                                          code = args['code'][0])
                ok = self.login_pkce_part2(pkce)
        except Exception as e:
            log.logException(e, 'PKCE Authentication failed !')
            xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30253), icon=xbmcgui.NOTIFICATION_ERROR)
        return ok

    def logout(self):
        Session.logout(self, signoff=False)
        settings.save_session()
        self._config.load()

    def token_refresh(self):
        token = Session.token_refresh(self)
        if token.success:
            settings.save_session()
        return token

    def get_album_tracks(self, album_id, withAlbum=True):
        items = Session.get_album_tracks(self, album_id)
        if withAlbum:
            album = self.get_album(album_id)
            if album:
                for item in items:
                    item.album = album
        return items

    def get_playlist_items(self, playlist, offset=0, limit=9999, ret='playlistitems'):
        if not isinstance(playlist, tidal.Playlist):
            playlist = self.get_playlist(playlist)
        items = Session.get_playlist_items(self, playlist, offset=offset, limit=limit, ret=ret)
        return items

    def get_playlist_tracks(self, playlist_id, offset=0, limit=9999):
        # keeping 1st parameter as playlist_id for backward compatibility 
        if isinstance(playlist_id, tidal.Playlist):
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
            album.audioModes = item.audioModes
            album.mediaMetadata = item.mediaMetadata
            albums.append(album)
        return albums

    def get_playlist_albums(self, playlist, offset=0, limit=9999):
        return self.get_item_albums(self.get_playlist_items(playlist, offset=offset, limit=limit))

    def get_artist_top_tracks(self, artist_id, offset=0, limit=999):
        items = []
        try:
            items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=limit)
        except:
            pass
        if not items and limit >= 100:
            try:
                items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=100)
            except:
                pass
        if not items and limit >= 50:
            try:
                items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=50)
            except:
                pass
        if not items:
            items = Session.get_artist_top_tracks(self, artist_id, offset=offset, limit=20)
        return items

    def get_artist_radio(self, artist_id, offset=0, limit=100):
        items = []
        try:
            items = Session.get_artist_radio(self, artist_id, offset=offset, limit=limit)
        except:
            pass
        if not items and limit >= 100:
            try:
                items = Session.get_artist_radio(self, artist_id, offset=offset, limit=100)
            except:
                pass
        if not items and limit >= 50:
            try:
                items = Session.get_artist_radio(self, artist_id, offset=offset, limit=50)
            except:
                pass
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

    def get_category_items(self, group):
        return Session.get_category_items(self, group)

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

    def _parse_broadcast(self, json_obj):
        item = BroadcastItem(Session._parse_broadcast(self, json_obj))
        return item

    def _parse_broadcast_url(self, json_obj):
        item = BroadcastUrlItem(Session._parse_broadcast_url(self, json_obj))
        return item

    def _parse_folder(self, json_obj):
        item = FolderItem(Session._parse_folder(self, json_obj))
        return item

    def _parse_playlist(self, json_obj):
        playlist = PlaylistItem(Session._parse_playlist(self, json_obj))
        playlist._is_logged_in = self.is_logged_in
        if self.is_logged_in and not playlist.parentFolderId:
            cached = self.user.folders_cache.get(playlist.id, None)
            if cached:
                playlist.parentFolderId = cached.get('parentFolderId', None)
                playlist.parentFolderName = cached.get('parentFolderName', '')
                log.debug('Cached: %s %s' % (playlist.id, playlist.parentFolderName))
                playlist._parentFolderIdFromCache = True
        if self.is_logged_in and not playlist.creatorName and playlist.creatorId:
            cached = self.user.profiles_cache.get('%s' % playlist.creatorId, None)
            if cached:
                playlist.creatorName = cached.get('name', '')
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

    def _parse_track_url(self, json_obj):
        item = TrackUrlItem(Session._parse_track_url(self, json_obj))
        return item

    def _parse_video(self, json_obj):
        video = VideoItem(Session._parse_video(self, json_obj))
        video._is_logged_in = self.is_logged_in
        if self.is_logged_in:
            video._userplaylists = self.user.playlists_of_id(video.id, video.album.id if video.album else None)
        if video.duration > 30 and (not self.is_logged_in or self._config.isFreeSubscription() and self._config.maxVideoHeight > 0):
            # 30 Seconds Limit in Trial Mode
            video.duration = 30
        return video

    def _parse_video_url(self, json_obj):
        media = VideoUrlItem(Session._parse_video_url(self, json_obj))
        if media.isEncrypted or not media.url:
            media.url = settings.unplayable_m4a
        return media

    def _parse_promotion(self, json_obj):
        promotion = PromotionItem(Session._parse_promotion(self, json_obj))
        promotion._is_logged_in = self.is_logged_in
        if self.is_logged_in and promotion.type == 'VIDEO':
            promotion._userplaylists = self.user.playlists_of_id(promotion.id)
        if self.is_logged_in and not promotion.parentFolderId and promotion.type == 'PLAYLIST':
            cached = self.user.folders_cache.get(promotion.id, None)
            if cached:
                promotion.parentFolderId = cached.get('parentFolderId', None)
                promotion.parentFolderName = cached.get('parentFolderName', '')
                log.debug('Cached: %s %s' % (promotion.id, promotion.parentFolderName))
                promotion._parentFolderIdFromCache = True
        return promotion

    def _parse_category(self, json_obj):
        return CategoryItem(Session._parse_category(self, json_obj))

    def _parse_userprofile(self, json_obj):
        item = UserProfileItem(Session._parse_userprofile(self, json_obj))
        if self.is_logged_in:
            self.user.check_cached_userprofile(item)
        return item

    def _parse_userprompt(self, json_obj):
        return UserPromptItem(Session._parse_userprompt(self, json_obj))

    def get_track_url(self, track_id, quality=None):
        try:
            soundQuality = quality if quality else self._config.quality
            media = Session.get_track_url(self, track_id, quality=soundQuality)
            if media.isEncrypted:
                log.warning('Got encrypted track %s ! Playing silence track to avoid kodi to crash ...' % track_id)
                xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30279).format(what=_T('track')), icon=xbmcgui.NOTIFICATION_WARNING)
                return TrackUrlItem.unplayableItem()
            if media.codec == tidal.Codec.SONY360RA:
                log.warning('Sony 360 RA not supported ! Playing silence track to avoid kodi to crash ...')
                xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30296).format(codec=tidal.AudioMode.sony_360), icon=xbmcgui.NOTIFICATION_WARNING)
                return TrackUrlItem.unplayableItem()
            if media.codec == tidal.Codec.AC4:
                log.warning('Dolby AC4 not supported ! Playing silence track to avoid kodi to crash ...')
                xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30296).format(codec=tidal.Codec.AC4), icon=xbmcgui.NOTIFICATION_WARNING)
                return TrackUrlItem.unplayableItem()
            if quality in [tidal.Quality.lossless, tidal.Quality.hi_res, tidal.Quality.hi_res_lossless] and media.codec not in tidal.Codec.HQCodecs:
                xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30504), icon=xbmcgui.NOTIFICATION_WARNING)
            log.info('Got stream with soundQuality:%s, codec:%s' % (media.soundQuality, media.codec))
            return media
        except HTTPError as e:
            r = e.response
            if r.status_code in [401, 403]:
                msg = _T(Msg.i30210)
            else:
                msg = r.reason
            try:
                msg = msg + '. ' + r.json().get('userMessage')
            except:
                pass
            xbmcgui.Dialog().notification('%s Error %s' % (plugin.name, r.status_code), msg, xbmcgui.NOTIFICATION_WARNING)
            log.warning("Playing silence for unplayable track %s to avoid kodi crash" % track_id)
        return TrackUrlItem.unplayableItem()

    def get_broadcast_url(self, broadcast_id, quality=None):
        try:
            soundQuality = quality if quality else self._config.quality
            media = Session.get_broadcast_url(self, broadcast_id, quality=soundQuality)
            if isinstance(media, BroadcastUrlItem):
                media.selectStream()
            return media
        except HTTPError as e:
            r = e.response
            if r.status_code in [401, 403]:
                msg = _T(Msg.i30210)
            else:
                msg = r.reason
            try:
                msg = r.json().get('userMessage')
            except:
                pass
            xbmcgui.Dialog().notification('%s Error %s' % (plugin.name, r.status_code), msg, xbmcgui.NOTIFICATION_WARNING)
            log.warning("Playing silence for unplayable live stream %s to avoid kodi crash" % broadcast_id)
        return TrackUrlItem.unplayableItem()

    def get_video_url(self, video_id, maxHeight=-1):
        try:
            maxVideoHeight = maxHeight if maxHeight >= 0 else self._config.maxVideoHeight
            media = Session.get_video_url(self, video_id, audioOnly=True if maxVideoHeight == 0 else False, preview=True if self._config.isFreeSubscription() and self._config.maxVideoHeight > 0 else False )
            if isinstance(media, VideoUrlItem):
                media.selectStream(maxVideoHeight)
            return media
        except HTTPError as e:
            r = e.response
            if r.status_code in [401, 403]:
                msg = _T(Msg.i30210)
            else:
                msg = r.reason
            try:
                msg = r.json().get('userMessage')
            except:
                pass
            xbmcgui.Dialog().notification('%s Error %s' % (plugin.name, r.status_code), msg, xbmcgui.NOTIFICATION_WARNING)
            log.warning("Playing silence for unplayable video %s to avoid kodi crash" % video_id)
        return VideoUrlItem.unplayableItem()

    def add_list_items(self, items, content=None, end=True, withNextPage=False, withSortModes=False):
        if content:
            xbmcplugin.setContent(plugin.handle, content)
            if settings.add_sort_methods and withSortModes and content in ['albums', 'songs', 'musicvideos', 'videos'] and KODI_VERSION >= (19, 0):
                # Label formats, see here: https://github.com/xbmc/xbmc/blob/master/xbmc/utils/LabelFormatter.cpp
                xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_NONE, labelMask='%L')
                xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS, labelMask='%L')
                xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE, labelMask='%L')
                xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_DATE, labelMask='%L')
        list_items = []
        for item in items:
            if isinstance(item, tidal.Category):
                category_items = item.getListItems()
                for url, li, isFolder in category_items:
                    if url and li:
                        list_items.append(('%s' % url if isFolder else url, li, isFolder))
            elif isinstance(item, tidal.BrowsableMedia):
                url, li, isFolder = item.getListItem()
                if url and li:
                    list_items.append(('%s' % url if isFolder else url, li, isFolder))
        if withNextPage and len(items) > 0:
            # Add folder for next page
            try:
                totalNumberOfItems = items[0]._totalNumberOfItems
                nextOffset = items[0]._offset + items[0]._pageSize
                if nextOffset < totalNumberOfItems and len(items) >= items[0]._pageSize:
                    self.add_directory_item(_T(Msg.i30244).format(pos1=nextOffset + 1, pos2=min(nextOffset+items[0]._pageSize, totalNumberOfItems), len=totalNumberOfItems),
                                            plugin.url_with_qs(plugin.path, offset=nextOffset))
            except:
                log.error('Next Page for URL %s not set' % sys.argv[0])
        if len(list_items) > 0:
            xbmcplugin.addDirectoryItems(plugin.handle, list_items)
        if end:
            xbmcplugin.endOfDirectory(plugin.handle)
            try:
                skinTheme = xbmc.getSkinDir().lower()
                if 'onfluence' in skinTheme:
                    if KODI_VERSION < (17, 0):
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
        item = DirectoryItem(title, endpoint, thumb, fanart, isFolder, label)
        self.add_list_items([item], end=end)

    def master_albums(self, offset=0, limit=999):
        items = self.get_category_content('master', 'recommended', 'albums', offset=offset, limit=limit)
        return items

    def master_playlists(self, offset=0, limit=999):
        items = self.get_category_content('master', 'recommended', 'playlists', offset=offset, limit=limit)
        return items

    def show_busydialog(self, headline='', textline=''):
        self.progressWindow = xbmcgui.DialogProgressBG()
        self.progressWindow.create(headline, textline)
        self.progressWindow.update(percent=50)

    def hide_busydialog(self):
        try:
            if self.progressWindow:
                self.progressWindow.close()
        except:
            pass
        self.progressWindow = None

    def check_updated_playlists(self, items, reloadPlaylist=False):
        if self.is_logged_in:
            for item in items:
                self.user.check_updated_playlist(playlist=item, reloadPlaylist=reloadPlaylist)
            self.user.save_cache()

    def get_userprofile(self, user_id):
        item = Session.get_userprofile(self, user_id)
        if self.is_logged_in:
            self.user.save_cache()
        return item

    def get_followers(self, user_id, offset=0, limit=500):
        items = Session.get_followers(self, user_id, offset=offset, limit=limit)
        if self.is_logged_in:
            self.user.save_cache()
        return items

    def get_following_users(self, user_id, offset=0, limit=500):
        items = Session.get_following_users(self, user_id, offset=offset, limit=limit)
        if self.is_logged_in:
            self.user.save_cache()
        return items



class TidalFavorites(Favorites):

    def __init__(self, session):
        Favorites.__init__(self, session)

    def reset(self):
        Favorites.reset(self)
        self.ids_on_disk = {}
        self.locked_artists_loaded = False
        self.locked_artists_updated = False
        self.locked_artists = []

    def load_locked_artists(self):
        try:
            if not self.locked_artists_loaded:
                self.locked_artists_loaded = False
                self.locked_artists_updated = False
                fd = xbmcvfs.File(settings.locked_artist_file, 'r')
                data = fd.read()
                fd.close()
                self.locked_artists = eval(data)
                log.debug('Loaded %s Favorites from disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
        except:
            log.warning('Locked Artists file not found: %s' % settings.locked_artist_file)
            self.locked_artists = [tidal.VARIOUS_ARTIST_ID]
            self.locked_artists_updated = True
            self.save_locked_artists()
        self.locked_artists_loaded = True
        return self.locked_artists_loaded

    def save_locked_artists(self):
        try:
            if self.locked_artists_updated:
                self.locked_artists_updated = False
                fd = xbmcvfs.File(settings.locked_artist_file, 'w')
                fd.write(repr(self.locked_artists))
                fd.close()
        except:
            log.error('Failed to save Locked Artists to cache file !')
            return False
        return True

    def load_cache(self):
        try:
            fd = xbmcvfs.File(settings.favorites_file, 'r')
            data = fd.read()
            fd.close()
            self.ids_on_disk = eval(data)
            self.ids.update(self.ids_on_disk)
            self.ids_loaded = isinstance(self.ids.get('tracks', None), list)
            self.ids_modified = False
            if self.ids_loaded:
                log.debug('Loaded %s Favorites from disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
        except:
            self.reset()
        return self.ids_loaded

    def save_cache(self):
        try:
            if self.ids_loaded:
                for k in self.ids.keys():
                    self.ids[k] = sorted(self.ids[k])
                if self.ids != self.ids_on_disk:
                    fd = xbmcvfs.File(settings.favorites_file, 'w')
                    fd.write(repr(self.ids))
                    fd.close()
                    self.ids_on_disk.update(self.ids)
                    self.ids_modified = False
                    log.info('Saved %s Favorites to disk.' % sum(len(self.ids[content]) for content in ['artists', 'albums', 'playlists', 'tracks', 'videos']))
        except:
            log.error('Error writing Favorite Cache file')
            return False
        return True

    def delete_cache(self):
        try:
            if xbmcvfs.exists(settings.favorites_file):
                xbmcvfs.delete(settings.favorites_file)
                log.debug('Deleted Favorites file.')
        except:
            return False
        return True

    def load_all(self, force_reload=False):
        if not force_reload and self.ids_loaded:
            return self.ids_loaded
        if not self.ids_loaded:
            self.load_cache()
        if force_reload or not self.ids_loaded:
            Favorites.load_all(self, force_reload=force_reload)
            self.save_cache()
        return self.ids_loaded

    def get(self, content_type, offset=0, limit=9999):
        self.load_all()
        if content_type == 'playlists':
            self._session.user.load_cache()
        items = Favorites.get(self, content_type, offset=offset, limit=limit)
        if items and self.ids_modified:
            self.save_cache()
        if content_type == 'playlists':
            self._session.check_updated_playlists(items)
        return items

    def add(self, content_type, item_ids):
        ok = Favorites.add(self, content_type, item_ids)
        if ok:
            self.load_all(force_reload=True)
        return ok

    def remove(self, content_type, item_id):
        if 'playlist' in content_type:
            self._session.user.load_cache()
        ok = Favorites.remove(self, content_type, item_id)
        if ok:
            self.load_all(force_reload=True)
            if 'playlist' in content_type:
                if self._session.user.folders_cache.pop(item_id, None):
                    self._session.user.folders_updated = True
                    self._session.user.save_cache()
        return ok

    def isLockedArtist(self, artist_id):
        self.load_locked_artists()
        return '%s' % artist_id in self.locked_artists

    def setLockedArtist(self, artist_id, lock=True):
        actually_locked = self.isLockedArtist(artist_id)
        ok = True
        if lock != actually_locked:
            try:
                if lock:
                    self.locked_artists.append('%s' % artist_id)
                    self.locked_artists = sorted(self.locked_artists)
                else:
                    self.locked_artists.remove('%s' % artist_id)
                self.locked_artists_updated = True
                self.save_locked_artists()
            except:
                ok = False
        return ok


class TidalUser(User):

    def __init__(self, session, favorites=None):
        User.__init__(self, session, favorites=favorites if favorites else TidalFavorites(session))
        self.playlists_loaded = False
        self.playlists_updated = False
        self.playlists_cache = {}
        self.folders_loaded = False
        self.folders_updated = False
        self.folders_cache = {}
        self.profiles_loaded = False
        self.profiles_updated = False
        self.profiles_cache = {}

    def update_caches(self, withProgress=False):
        log.info('Updating caches %s' % ('with progress dialog' if withProgress else 'in background'))
        progress = xbmcgui.DialogProgressBG() if withProgress else None
        if progress:
            progress.create(heading=plugin.name)
        try:
            if progress:
                progress.update(percent=1, message=_T(Msg.i30306))
            self.favorites.load_all(force_reload=True)
            self.playlists(flattened=True, allPlaylists=True, progress=progress)
            self.get_followers()
            self.get_following_users()
            self.get_blocked_users()
            self.save_cache()
        except:
            pass
        finally:
            if progress:
                xbmc.sleep(500)
                progress.close()

    def load_cache(self, force_reload=False):
        try:
            if not self.playlists_loaded or force_reload:
                fd = xbmcvfs.File(settings.playlist_file, 'r')
                self.playlists_cache = eval(fd.read())
                fd.close()
                self.playlists_loaded = True
                self.playlists_updated = False
                log.debug('Loaded %s Playlists from disk.' % len(list(self.playlists_cache.keys())))
        except:
            log.warning('Playlist Cache file not found. Creating a new one ...')
            self.playlists_loaded = True
            self.playlists_updated = True
            self.playlists_cache = {}
            self.save_cache()
        try:
            if not self.folders_loaded or force_reload:
                fd = xbmcvfs.File(settings.folders_file, 'r')
                self.folders_cache = eval(fd.read())
                fd.close()
                self.folders_loaded = True
                self.folders_updated = False
                log.debug('Loaded %s Playlist Folder entries from disk.' % len(list(self.folders_cache.keys())))
        except:
            log.warning('Folders Cache file not found. Creating a new one ...')
            self.folders_loaded = True
            self.folders_updated = True
            self.folders_cache = {}
            self.save_cache()
        try:
            if not self.profiles_loaded or force_reload:
                fd = xbmcvfs.File(settings.profiles_file, 'r')
                self.profiles_cache = eval(fd.read())
                fd.close()
                self.profiles_loaded = True
                self.profiles_updated = False
                log.debug('Loaded %s Userprofile entries from disk.' % len(list(self.profiles_cache.keys())))
        except:
            log.warning('Userprofile Cache file not found. Creating a new one ...')
            self.profiles_loaded = True
            self.profiles_updated = True
            self.profiles_cache = {}
            self.save_cache()
        return self.playlists_loaded and self.folders_loaded and self.profiles_loaded

    def save_cache(self):
        ok = self.favorites.save_cache()
        try:
            if self.playlists_loaded and self.playlists_updated:
                self.playlists_updated = False
                fd = xbmcvfs.File(settings.playlist_file, 'w')
                fd.write(repr(self.playlists_cache))
                fd.close()
                log.info('Saved %s Playlists to disk.' % len(list(self.playlists_cache.keys())))
        except:
            log.error('Error writing Playlist Cache file')
            ok = False
        try:
            if self.folders_loaded and self.folders_updated:
                self.folders_updated = False
                fd = xbmcvfs.File(settings.folders_file, 'w')
                fd.write(repr(self.folders_cache))
                fd.close()
                log.info('Saved %s Folders to disk.' % len(list(self.folders_cache.keys())))
        except:
            log.error('Error writing Folders Cache file')
            ok = False
        try:
            if self.profiles_loaded and self.profiles_updated:
                self.profiles_updated = False
                fd = xbmcvfs.File(settings.profiles_file, 'w')
                fd.write(repr(self.profiles_cache))
                fd.close()
                log.info('Saved %s Userprofiles to disk.' % len(list(self.profiles_cache.keys())))
        except:
            log.error('Error writing Userprofile Cache file')
            ok = False
        return ok

    def check_cached_userprofile(self, userprofile):
        if not isinstance(userprofile, tidal.UserProfile):
            return False
        item = self.profiles_cache.get('%s' % userprofile.id, {})
        if userprofile.name and not item.get('name', ''):
            self.profiles_cache.update({'%s' % userprofile.id: {'name': userprofile.name}})
            self.profiles_updated = True
        elif not userprofile.name:
            userprofile.name = item.get('name', userprofile.name)
        return True if self.profiles_updated else False

    def get_blocked_users(self, offset=0, limit=50):
        items = User.get_blocked_users(self, offset=offset, limit=limit)
        self.save_cache()
        return items

    def check_updated_playlist(self, playlist, reloadPlaylist=False):
        if not isinstance(playlist, tidal.Playlist):
            return False
        if reloadPlaylist:
            playlist = self._session.get_playlist(playlist.id)
        if playlist.isUserPlaylist and self.playlists_cache.get(playlist.id, {}).get('lastUpdated', datetime.datetime.fromordinal(1)) != playlist.lastUpdated:
            # User Playlist is new or modified
            items = self._session.get_playlist_items(playlist)
            album_ids = []
            if settings.album_playlist_tag in playlist.description and playlist.isUserPlaylist:
                album_ids = ['%s' % item.album.id for item in items if (isinstance(item, TrackItem) or (isinstance(item, VideoItem) and item.album))]
            # Save Playlist and Track-IDs into the Cache
            self.playlists_cache.update({playlist.id: {'title': playlist.title,
                                                       'description': playlist.description,
                                                       'lastUpdated': playlist.lastUpdated,
                                                       'ids': ['%s' % item.id for item in items],
                                                       'album_ids': album_ids}})
            self.playlists_updated = True
        if playlist.isUserPlaylist or playlist._isFavorite:
            # Check if Folder Cache entry changed (for all Playlists)
            cached_playlist = self.folders_cache.get(playlist.id, {})
            if cached_playlist.get('parentFolderId', None) != playlist.parentFolderId or cached_playlist.get('parentFolderName', '') != playlist.parentFolderName:
                self.folders_cache.update({playlist.id: {'parentFolderId': playlist.parentFolderId,
                                                         'parentFolderName': playlist.parentFolderName}})
                self.folders_updated = True
        return True if self.playlists_updated or self.folders_updated else False

    def check_deleted_playlists(self, items, checkFolders=False):
        # Check which playlist has to be removed from the cache
        cached_ids = list(self.playlists_cache.keys())
        act_ids = [item.id for item in items if item.isUserPlaylist]
        # Remove Deleted Playlists from Cache
        for plid in cached_ids:
            if plid not in act_ids:
                playlist = self.playlists_cache.pop(plid)
                if playlist:
                    self.playlists_updated = True
                    log.info('Removed playlist "%s" from playlist cache' % playlist['title'])
        if checkFolders:
            # And also from the folders cache
            cached_ids = list(self.folders_cache.keys())
            act_ids = [item.id for item in items if item.parentFolderId != None and not item._parentFolderIdFromCache]
            # Remove removed Playlists from the Folder Cache
            for plid in cached_ids:
                if plid not in act_ids:
                    playlist = self.folders_cache.pop(plid)
                    if playlist:
                        self.folders_updated = True
                        log.info('Removed %s from cached folder "%s"' % (plid, playlist['parentFolderName']))
        return True if self.playlists_updated or self.folders_updated else False

    def delete_cache(self):
        ok = True
        try:
            if xbmcvfs.exists(settings.playlist_file):
                xbmcvfs.delete(settings.playlist_file)
                log.debug('Deleted Playlists file.')
                self.playlists_loaded = False
                self.playlists_cache = {}
        except:
            ok = False
        try:
            if xbmcvfs.exists(settings.profiles_file):
                xbmcvfs.delete(settings.profiles_file)
                log.debug('Deleted Userprofiles file.')
                self.profiles_loaded = False
                self.profiles_cache = {}
        except:
            ok = False
        return ok

    def playlists_of_id(self, item_id, album_id=None):
        userpl = {}
        self.load_cache()
        if not self.playlists_loaded:
            self.playlists()
        plids = list(self.playlists_cache.keys())
        for plid in plids:
            if item_id and '%s' % item_id in self.playlists_cache.get(plid).get('ids', []):
                userpl.update({plid: self.playlists_cache.get(plid)})
            if album_id and '%s' % album_id in self.playlists_cache.get(plid).get('album_ids', []):
                userpl.update({plid: self.playlists_cache.get(plid)})
        return userpl

    def detect_default_playlists(self):
        # Find Default Playlists via title if ID is not available anymore
        try:
            all_ids = list(self.playlists_cache.keys())
            for what in ['track', 'album', 'video']:
                playlist_id = settings.getSetting('default_%splaylist_id' % what)
                playlist_title = settings.getSetting('default_%splaylist_title' % what)
                if playlist_id and playlist_title and playlist_id not in all_ids:
                    for playlist_id in all_ids:
                        if self.playlists_cache.get(playlist_id).get('title', '') == playlist_title:
                            settings.setSetting('default_%splaylist_id' % what, playlist_id)
                            settings.setSetting('default_%splaylist_title' % what, playlist_title)
                            break
        except:
            pass

    def playlists(self, flattened=True, allPlaylists=False, progress=None):
        if progress:
            progress.update(percent=2, message=_T(Msg.i30307))
        items = User.playlists(self, flattened=flattened, allPlaylists=allPlaylists)
        # Refresh the Playlist Cache
        self.load_cache()
        # Update modified Playlists in Cache
        item_no = 0
        for item in items:
            item_no += 1
            if progress:
                progress.update(percent=int((item_no * 100) / len(items)),
                                            message=_T(Msg.i30308).format(item=item_no, max=len(items), name=item.name))
            self.check_updated_playlist(item)
        if flattened:
            # in flattened mode all user playlists are loaded
            self.check_deleted_playlists(items, checkFolders=allPlaylists)
        if progress:
            progress.update(percent=100, message=_T(Msg.i30309))
        self.save_cache()
        if flattened and not allPlaylists:
            self.detect_default_playlists()
        return items

    def add_playlist_entries(self, playlist, item_ids=[]):
        self.load_cache()
        item = User.add_playlist_entries(self, playlist=playlist, item_ids=item_ids)
        if item:
            self.check_updated_playlist(item, reloadPlaylist=True)
            self.save_cache()
        return item

    def remove_playlist_entry(self, playlist, entry_no=None, item_id=None):
        self.load_cache()
        item = User.remove_playlist_entry(self, playlist, entry_no=entry_no, item_id=item_id)
        if item:
            self.check_updated_playlist(item, reloadPlaylist=True)
            self.save_cache()
        return item

    def create_playlist(self, title, description='', folder_id='root'):
        self.load_cache()
        item = User.create_playlist(self, title, description=description, folder_id=folder_id)
        if item:
            self.check_updated_playlist(item, reloadPlaylist=False)
            self.save_cache()
        return item

    def delete_playlist(self, playlist_id):
        self.load_cache()
        ok = User.delete_playlist(self, playlist_id)
        if ok:
            self.playlists_cache.pop(playlist_id)
            self.playlists_updated = True
            self.save_cache()
        return ok

    def renamePlaylistDialog(self, playlist):
        dialog = xbmcgui.Dialog()
        title = dialog.input(_T(Msg.i30233), playlist.title, type=xbmcgui.INPUT_ALPHANUM)
        ok = False
        if title:
            description = dialog.input(_T(Msg.i30234), playlist.description, type=xbmcgui.INPUT_ALPHANUM)
            ok = self.rename_playlist(playlist, title, description)
        return ok

    def newPlaylistDialog(self):
        dialog = xbmcgui.Dialog()
        title = dialog.input(_T(Msg.i30233), type=xbmcgui.INPUT_ALPHANUM)
        item = None
        if title:
            description = dialog.input(_T(Msg.i30234), type=xbmcgui.INPUT_ALPHANUM)
            item = self.create_playlist(title, description)
        return item

    def selectPlaylistDialog(self, headline=None, allowNew=False):
        if not self._session.is_logged_in:
            return None
        try:
            if not headline:
                headline = _T(Msg.i30238).format(what=_T('playlist'))
            items = self.playlists(flattened=True, allPlaylists=False)
            dialog = xbmcgui.Dialog()
            item_list = [item.name for item in items if item.isUserPlaylist]
            if allowNew:
                item_list.append(_T(Msg.i30237).format(what=_T('playlist')))
        except Exception as e:
            log.error(str(e))
            return None
        selected = dialog.select(headline, item_list)
        if selected >= len(items):
            item = self.newPlaylistDialog()
            xbmc.sleep(500)
            return item
        elif selected >= 0:
            return items[selected]
        return None

    def folders(self):
        items = User.folders(self)
        for item in items:
            if item.id == settings.default_folder_id and item.name != settings.default_folder_name:
                settings.setSetting('default_folder_name', item.name)
        return items

    def create_folder(self, name, parent_id='root'):
        folder = User.create_folder(self, name=name, parent_id=parent_id)
        return folder

    def remove_folder(self, trns):
        # trns can be a folder or playlist trn or a comma separated list of trns
        # Attention: A User Playlist will be deletet
        self.load_cache()
        ok = User.remove_folder(self, trns=trns)
        if ok:
            self.update_caches()
        return ok

    def rename_folder(self, folder_trn, name):
        self.load_cache()
        ok = User.rename_folder(self, folder_trn=folder_trn, name=name)
        if ok:
            self.update_caches()
        return ok

    def add_folder_entry(self, folder, playlist):
        self.load_cache()
        item = User.add_folder_entry(self, folder=folder, playlist=playlist)
        if item:
            self.update_caches()
        return item

    def move_folder_entries(self, trns, folder='root'):
        self.load_cache()
        ok = User.move_folder_entries(self, trns, folder=folder)
        if ok:
            self.update_caches()
        return ok

    def addToFolderDialog(self, playlist_id):
        playlist = self._session.get_playlist(playlist_id)
        folder = self.selectFolderDialog(headline=_T(Msg.i30239).format(what=_T('folder')), allowNew=True)
        ok = False
        if playlist and folder:
            self._session.show_busydialog(_T(Msg.i30263).format(what=_T('folder')), folder.name)
            try:
                if playlist.isUserPlaylist or playlist._isFavorite:
                    ok = self.move_folder_entries(trns=playlist.trn, folder=folder)
                else:
                    ok = self.add_folder_entry(folder, playlist)
            except Exception as e:
                log.logException(e, txt='Couldn''t add item to folder %s' % folder.name)
                traceback.print_exc()
            self._session.hide_busydialog()
        return ok

    def moveToFolderDialog(self, playlist_id):
        playlist = self._session.get_playlist(playlist_id)
        folder = self.selectFolderDialog(headline=_T(Msg.i30248).format(what=_T('folder')), allowNew=True)
        ok = False
        if playlist and folder:
            self._session.show_busydialog(_T(Msg.i30263).format(what=_T('folder')), folder.name)
            try:
                if playlist.isUserPlaylist or playlist._isFavorite:
                    ok = self.move_folder_entries(trns=playlist.trn, folder=folder)
                else:
                    ok = self.add_folder_entry(folder, playlist)
            except Exception as e:
                log.logException(e, txt='Couldn''t add item to folder %s' % folder.name)
                traceback.print_exc()
            self._session.hide_busydialog()
        return ok

    def removeFromFolderDialog(self, folder_id, playlist_id):
        playlist = self._session.get_playlist(playlist_id)
        folder = self.folder(folder_id)
        ok = False
        if playlist and folder:
            ok = xbmcgui.Dialog().yesno(_T(Msg.i30240).format(what=_T('folder')), _T(Msg.i30278).format(name="'%s'" % playlist.name, what=_T('folder'))+' ?')
            if ok:
                self._session.show_busydialog(_T(Msg.i30264).format(what=_T('folder')), folder.name)
                try:
                    self._session.user.move_folder_entries(trns=playlist.trn, folder='root')
                except Exception as e:
                    log.logException(e, txt='Couldn''t remove item from folder %s' % folder.name)
                    traceback.print_exc()
                self._session.hide_busydialog()
        return ok

    def newFolderDialog(self):
        dialog = xbmcgui.Dialog()
        name = dialog.input(_T(Msg.i30237).format(what=_T('folder')), type=xbmcgui.INPUT_ALPHANUM)
        item = None
        if name:
            item = self.create_folder(name)
            if item:
                item_id = item.id
                for poll in [1, 2, 3]:
                    xbmc.sleep(500)
                    # Re-read the Folder to check if created successfully
                    item = self.folder(item_id)
                    if item: break
        return item

    def renameFolderDialog(self, folder_id):
        folder = self.folder(folder_id)
        dialog = xbmcgui.Dialog()
        name = dialog.input(_T(Msg.i30251).format(what=_T('folder')), folder.name, type=xbmcgui.INPUT_ALPHANUM)
        ok = False
        if name:
            ok = self.rename_folder(folder.trn, name)
        return ok

    def deleteFolderDialog(self, folder_id):
        dialog = xbmcgui.Dialog()
        folder = self.folder(folder_id)
        msg = _T(Msg.i30277).format(folder=folder.name)
        if folder.totalNumberOfItems > 0:
            msg = _T(Msg.i30276).format(folder=folder.name, count=folder.totalNumberOfItems) + '\n' + msg
        ok = dialog.yesno(_T(Msg.i30235).format(what=_T('folder')), msg)
        if ok:
            self._session.show_busydialog(_T(Msg.i30235).format(what=_T('folder')), folder.name)
            try:
                self._session.user.remove_folder(folder.trn)
            except Exception as e:
                log.logException(e, txt='Couldn''t delete folder "%s"' % folder.name)
                traceback.print_exc()
                ok = False
            self._session.hide_busydialog()
        return ok

    def selectFolderDialog(self, headline=None, allowNew=False):
        if not self._session.is_logged_in:
            return None
        try:
            if not headline:
                headline = _T(Msg.i30238).format(what=_T('folder'))
            items = self.folders()
            dialog = xbmcgui.Dialog()
            item_list = [item.name for item in items]
            if allowNew:
                item_list.append(_T(Msg.i30237).format(what=_T('folder')))
        except Exception as e:
            log.error(str(e))
            return None
        selected = dialog.select(headline, item_list)
        if selected >= len(items):
            item = self.newFolderDialog()
            return item
        elif selected >= 0:
            return items[selected]
        return None

# End of File