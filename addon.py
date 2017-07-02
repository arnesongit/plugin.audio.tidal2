# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Thomas Amland, Arne Svenson
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
import xbmc
import xbmcgui
import xbmcplugin
from xbmcgui import ListItem
from requests import HTTPError
from resources.lib.tidalapi.models import Quality, Category, SubscriptionType
from resources.lib.koditidal import plugin, addon, _addon_id, _T, log, ALBUM_PLAYLIST_TAG, KODI_VERSION
from resources.lib.koditidal2 import TidalSession2 as TidalSession

# This is the Tidal Session
session = TidalSession()
session.load_session()

add_items = session.add_list_items
add_directory = session.add_directory_item
CONTENT_FOR_TYPE = {'artists': 'artists', 'albums': 'albums', 'playlists': 'albums', 'tracks': 'songs', 'videos': 'musicvideos', 'files': 'files'}


@plugin.route('/')
def root():
    if session.is_logged_in:
        add_directory(_T(30201), my_music)
    add_directory(_T(30202), featured_playlists)
    if getattr(session._config, 'cache_albums', False):
        add_directory(_T(30509), plugin.url_for(albums_with_videos))
    categories = Category.groups()
    for item in categories:
        add_directory(_T(item), plugin.url_for(category, group=item))
    add_directory(_T(30206), search)
    add_directory(_T(30027), settings, isFolder=False)
    if session.is_logged_in:
        add_directory(_T(30207), logout, end=True, isFolder=False)
    else:
        add_directory(_T(30208), login, end=True, isFolder=False)


@plugin.route('/settings')
def settings():
    xbmc.executebuiltin('Addon.OpenSettings("%s")' % _addon_id)


@plugin.route('/albums_with_videos')
def albums_with_videos():
    add_items(session.albums_with_videos(), content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/category/<group>')
def category(group):
    promoGroup = {'rising': 'RISING', 'discovery': 'DISCOVERY', 'featured': 'NEWS'}.get(group, None)
    items = session.get_category_items(group)
    totalCount = 0
    for item in items:
        totalCount += len(item.content_types)
    if totalCount == 1:
        # Show Single content directly (Movies and TV Shows)
        for item in items:
            content_types = item.content_types
            for content_type in content_types:
                category_content(group, item.path, content_type, offset=0)
                return
    xbmcplugin.setContent(plugin.handle, 'files')
    if promoGroup and totalCount > 10:
        # Add Promotions as Folder on the Top if more than 10 Promotions available
        add_directory(_T(30120), plugin.url_for(featured, group=promoGroup))
        add_directory('Master %s (MQA)' % _T(30107), plugin.url_for(master_albums, offset=0))
        add_directory('Master %s (MQA)' % _T(30108), plugin.url_for(master_playlists, offset=0))
    # Add Category Items as Folders
    add_items(items, content=None, end=not(promoGroup and totalCount <= 10))
    if promoGroup and totalCount <= 10:
        # Show up to 10 Promotions as single Items
        promoItems = session.get_featured(promoGroup, types=['ALBUM', 'PLAYLIST', 'VIDEO'])
        if promoItems:
            add_items(promoItems, end=True)


@plugin.route('/category/<group>/<path>')
def category_item(group, path):
    items = session.get_category_items(group)
    path_items = []
    for item in items:
        if item.path == path:
            item._force_subfolders = True
            path_items.append(item)
    add_items(path_items, content=CONTENT_FOR_TYPE.get('files'))


@plugin.route('/category/<group>/<path>/<content_type>/<offset>')
def category_content(group, path, content_type, offset):
    items = session.get_category_content(group, path, content_type, offset=int('0%s' % offset), limit=session._config.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get(content_type, 'songs'), withNextPage=True)


@plugin.route('/master_albums/<offset>')
def master_albums(offset):
    items = session.master_albums(offset=int('0%s' % offset), limit=session._config.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/master_playlists/<offset>')
def master_playlists(offset):
    items = session.master_playlists(offset=int('0%s' % offset), limit=session._config.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/track_radio/<track_id>')
def track_radio(track_id):
    add_items(session.get_track_radio(track_id, limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/recommended/tracks/<track_id>')
def recommended_tracks(track_id):
    add_items(session.get_recommended_items('tracks', track_id, limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/recommended/videos/<video_id>')
def recommended_videos(video_id):
    add_items(session.get_recommended_items('videos', video_id, limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('videos'))


@plugin.route('/featured/<group>')
def featured(group):
    items = session.get_featured(group, types=['ALBUM', 'PLAYLIST', 'VIDEO'])
    add_items(items, content=CONTENT_FOR_TYPE.get('files'))


@plugin.route('/featured_playlists')
def featured_playlists():
    items = session.get_featured()
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/my_music')
def my_music():
    add_directory(_T(30213), user_playlists)
    add_directory(_T(30214), plugin.url_for(favorites, content_type='artists'))
    add_directory(_T(30215), plugin.url_for(favorites, content_type='albums'))
    add_directory(_T(30216), plugin.url_for(favorites, content_type='playlists'))
    add_directory(_T(30217), plugin.url_for(favorites, content_type='tracks'))
    add_directory(_T(30218), plugin.url_for(favorites, content_type='videos'), end=True)


@plugin.route('/album/<album_id>')
def album_view(album_id):
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_TRACKNUM)
    album = session.get_album(album_id)
    if album and album.numberOfVideos > 0:
        add_directory(_T(30110), plugin.url_for(album_videos, album_id=album_id))
    add_items(session.get_album_tracks(album_id), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/album_videos/<album_id>')
def album_videos(album_id):
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_TRACKNUM)
    add_items(session.get_album_items(album_id, ret='videos'), content=CONTENT_FOR_TYPE.get('videos'))


@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    if session.is_logged_in:
        session.user.favorites.load_all()
    artist = session.get_artist(artist_id)
    xbmcplugin.setContent(plugin.handle, 'albums')
    add_directory(_T(30225), plugin.url_for(artist_bio, artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
    add_directory(_T(30226), plugin.url_for(top_tracks, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(30110), plugin.url_for(artist_videos, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(30227), plugin.url_for(artist_radio, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(30228), plugin.url_for(artist_playlists, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(30229), plugin.url_for(similar_artists, artist_id), thumb=artist.image, fanart=artist.fanart)
    if session.is_logged_in:
        if session.user.favorites.isFavoriteArtist(artist_id):
            add_directory(_T(30220), plugin.url_for(favorites_remove, content_type='artists', item_id=artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
        else:
            add_directory(_T(30219), plugin.url_for(favorites_add, content_type='artists', item_id=artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
    albums = session.get_artist_albums(artist_id) + \
             session.get_artist_albums_ep_singles(artist_id) + \
             session.get_artist_albums_other(artist_id)
    add_items(albums, content=None)


@plugin.route('/artist/<artist_id>/bio')
def artist_bio(artist_id):
    artist = session.get_artist(artist_id)
    info = session.get_artist_info(artist_id)
    text = ''
    if info.get('summary', None):
        text += '%s:\n\n' % _T(30230) + info.get('summary') + '\n\n'
    if info.get('text', None):
        text += '%s:\n\n' % _T(30225) + info.get('text')
    if text:
        xbmcgui.Dialog().textviewer(artist.name, text)


@plugin.route('/artist/<artist_id>/top')
def top_tracks(artist_id):
    add_items(session.get_artist_top_tracks(artist_id, limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/artist/<artist_id>/radio')
def artist_radio(artist_id):
    add_items(session.get_artist_radio(artist_id, limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/artist/<artist_id>/videos')
def artist_videos(artist_id):
    add_items(session.get_artist_videos(artist_id), content=CONTENT_FOR_TYPE.get('videos'))


@plugin.route('/artist/<artist_id>/playlists')
def artist_playlists(artist_id):
    add_items(session.get_artist_playlists(artist_id), content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/artist/<artist_id>/similar')
def similar_artists(artist_id):
    add_items(session.get_artist_similar(artist_id), content=CONTENT_FOR_TYPE.get('artists'))


@plugin.route('/playlist/<playlist_id>/items/<offset>')
def playlist_view(playlist_id, offset):
    add_items(session.get_playlist_items(playlist_id, offset=int('0%s' % offset), limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'), withNextPage=True)


@plugin.route('/playlist/<playlist_id>/tracks/<offset>')
def playlist_tracks(playlist_id, offset):
    add_items(session.get_playlist_tracks(playlist_id, offset=int('0%s' % offset), limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('tracks'), withNextPage=True)


@plugin.route('/playlist/<playlist_id>/albums/<offset>')
def playlist_albums(playlist_id, offset):
    add_items(session.get_playlist_albums(playlist_id, offset=int('0%s' % offset), limit=session._config.pageSize), content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/user_playlists')
def user_playlists():
    items = session.user.playlists()
    # Find Default Playlists via title if ID is not available anymore
    all_ids = session.user.playlists_cache.keys()
    for what in ['track', 'album', 'video']:
        playlist_id = addon.getSetting('default_%splaylist_id' % what).decode('utf-8')
        playlist_title = addon.getSetting('default_%splaylist_title' % what).decode('utf-8')
        if playlist_id and playlist_title and playlist_id not in all_ids:
            for playlist_id in all_ids:
                if session.user.playlists_cache.get(playlist_id).get('title', '') == playlist_title:
                    addon.setSetting('default_%splaylist_id' % what, playlist_id)
                    addon.setSetting('default_%splaylist_title' % what, playlist_title)
                    break
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/user_playlist/rename/<playlist_id>')
def user_playlist_rename(playlist_id):
    playlist = session.get_playlist(playlist_id)
    ok = session.user.renamePlaylistDialog(playlist)
    if ok:
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/delete/<playlist_id>')
def user_playlist_delete(playlist_id):
    dialog = xbmcgui.Dialog()
    playlist = session.get_playlist(playlist_id)
    ok = dialog.yesno(_T(30235), _T(30236).format(name=playlist.title, count=playlist.numberOfItems))
    if ok:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        try:
            session.user.delete_playlist(playlist_id)
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/add/<item_type>/<item_id>')
def user_playlist_add_item(item_type, item_id):
    if item_type == 'playlist':
        srcPlaylist = session.get_playlist(item_id)
        if not srcPlaylist:
            return
        items = session.get_playlist_items(playlist=srcPlaylist)
        # Sort Items by Artist, Title
        sortMode = 'ALBUM' if ALBUM_PLAYLIST_TAG in srcPlaylist.description else 'LABEL'
        items.sort(key=lambda line: line.getSortText(mode=sortMode).upper(), reverse=False)
        items = ['%s' % item.id for item in items]
    elif item_type.startswith('album'):
        # Add First Track of the Album
        tracks = session.get_album_items(item_id)
        for track in tracks:
            if track.available:
                item_id = track.id
                break
        items = ['%s' % item_id]
    else:
        items = [item_id]
    playlist = session.user.selectPlaylistDialog(allowNew=True)
    if playlist:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        try:
            session.user.add_playlist_entries(playlist=playlist, item_ids=items)
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove/<playlist_id>/<entry_no>')
def user_playlist_remove_item(playlist_id, entry_no):
    item_no = int('0%s' % entry_no) + 1
    playlist = session.get_playlist(playlist_id)
    ok = xbmcgui.Dialog().yesno(_T(30247) % playlist.title, _T(30241) % item_no)
    if ok:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        try:
            session.user.remove_playlist_entry(playlist, entry_no=entry_no)
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove_id/<playlist_id>/<item_id>')
def user_playlist_remove_id(playlist_id, item_id):
    playlist = session.get_playlist(playlist_id)
    ok = xbmcgui.Dialog().yesno(_T(30247) % playlist.title, _T(30246))
    if ok:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        try:
            session.user.remove_playlist_entry(playlist, item_id=item_id)
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove_album/<playlist_id>/<item_id>')
def user_playlist_remove_album(playlist_id, item_id, dialog=True):
    playlist = session.get_playlist(playlist_id)
    ok = True
    if dialog:
        ok = xbmcgui.Dialog().yesno(_T(30247) % playlist.title, _T(30246))
    if ok:
        xbmc.executebuiltin('ActivateWindow(busydialog)')
        try:
            items = session.get_playlist_tracks(playlist)
            for item in items:
                if '%s' % item.album.id == '%s' % item_id:
                    session.user.remove_playlist_entry(playlist, entry_no=item._playlist_pos)
                    break # Remove only one Item
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/move/<playlist_id>/<entry_no>/<item_id>')
def user_playlist_move_entry(playlist_id, entry_no, item_id):
    dialog = xbmcgui.Dialog()
    playlist = session.user.selectPlaylistDialog(headline=_T(30248), allowNew=True)
    if playlist and playlist.id <> playlist_id:
        xbmc.executebuiltin( "ActivateWindow(busydialog)" )
        try:
            ok = session.user.add_playlist_entries(playlist=playlist, item_ids=[item_id])
            if ok:
                ok = session.user.remove_playlist_entry(playlist_id, entry_no=entry_no)
            else:
                dialog.notification(plugin.name, _T('API Call Failed'), xbmcgui.NOTIFICATION_ERROR)
        except Exception, e:
            log(str(e), level=xbmc.LOGERROR)
            traceback.print_exc()
        xbmc.executebuiltin( "Dialog.Close(busydialog)" )
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_set_default/<item_type>/<playlist_id>')
def user_playlist_set_default(item_type, playlist_id):
    item = session.get_playlist(playlist_id)
    if item:
        if item_type.lower().find('track') >= 0:
            addon.setSetting('default_trackplaylist_id', item.id)
            addon.setSetting('default_trackplaylist_title', item.title)
        elif item_type.lower().find('video') >= 0:
            addon.setSetting('default_videoplaylist_id', item.id)
            addon.setSetting('default_videoplaylist_title', item.title)
        elif item_type.lower().find('album') >= 0:
            addon.setSetting('default_albumplaylist_id', item.id)
            addon.setSetting('default_albumplaylist_title', item.title)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_reset_default/<item_type>')
def user_playlist_reset_default(item_type):
    if item_type.lower().find('track') >= 0:
        addon.setSetting('default_trackplaylist_id', '')
        addon.setSetting('default_trackplaylist_title', '')
    elif item_type.lower().find('video') >= 0:
        addon.setSetting('default_videoplaylist_id', '')
        addon.setSetting('default_videoplaylist_title', '')
    elif item_type.lower().find('album') >= 0:
        addon.setSetting('default_albumplaylist_id', '')
        addon.setSetting('default_albumplaylist_title', '')
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_toggle')
def user_playlist_toggle():
    if not session.is_logged_in:
        return
    url = xbmc.getInfoLabel( "ListItem.FilenameandPath" )
    if not _addon_id in url:
        return
    if 'play_track/' in url:
        item_type = 'track'
        userpl_id = addon.getSetting('default_trackplaylist_id').decode('utf-8')
        item_id = url.split('play_track/')[1]
        item_id = item_id.split('/')[0]
        item = session.get_track(item_id)
    elif 'play_video/' in url:
        item_type = 'video'
        userpl_id = addon.getSetting('default_videoplaylist_id').decode('utf-8')
        item_id = url.split('play_video/')[1]
        item = session.get_video(item_id)
    elif 'album/' in url:
        item_type = 'album'
        userpl_id = addon.getSetting('default_albumplaylist_id').decode('utf-8')
        item_id = int('0%s' % url.split('album/')[1])
        item = session.get_album(item_id)
        if userpl_id:
            if item._userplaylists and userpl_id in item._userplaylists:
                user_playlist_remove_album(userpl_id, item.id, dialog=False)
                return
            tracks = session.get_album_items(item.id)
            for track in tracks:
                if track.available:
                    item.id = track.id  # Add First Track of Album
                    break
    else:
        return
    try:
        if not userpl_id:
            # Dialog Mode if default Playlist not set
            user_playlist_add_item(item_type, '%s' % item_id)
            return
        xbmc.executebuiltin( "ActivateWindow(busydialog)" )
        if item._userplaylists and userpl_id in item._userplaylists:
            session.user.remove_playlist_entry(playlist=userpl_id, item_id=item.id)
        else:
            session.user.add_playlist_entries(playlist=userpl_id, item_ids=['%s' % item.id])
    except Exception, e:
        log(str(e), level=xbmc.LOGERROR)
        traceback.print_exc()
    xbmc.executebuiltin( "Dialog.Close(busydialog)" ) # Avoid GUI Lock        
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/favorites/<content_type>')
def favorites(content_type):
    items = session.user.favorites.get(content_type, limit=100 if content_type == 'videos' else 9999)
    if content_type in ['playlists', 'artists']:
        items.sort(key=lambda line: line.name, reverse=False)
    else:
        items.sort(key=lambda line: '%s - %s' % (line.artist.name, line.title), reverse=False)
    add_items(items, content=CONTENT_FOR_TYPE.get(content_type, 'songs'))


@plugin.route('/favorites/add/<content_type>/<item_id>')
def favorites_add(content_type, item_id):
    ok = session.user.favorites.add(content_type, item_id)
    if ok:
        xbmcgui.Dialog().notification(heading=plugin.name, message=_T(30231).format(what=_T(content_type)), icon=xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/favorites/remove/<content_type>/<item_id>')
def favorites_remove(content_type, item_id):
    ok = session.user.favorites.remove(content_type, item_id)
    if ok:
        xbmcgui.Dialog().notification(heading=plugin.name, message=_T(30232).format(what=_T(content_type)), icon=xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/cache_reset')
def cache_reset():
    if not session.is_logged_in:
        return
    session.user.delete_cache()
    session.user.favorites.delete_cache()

@plugin.route('/cache_reset_confirmed')
def cache_reset_confirmed():
    if xbmcgui.Dialog().yesno(_T(30507), _T(30508)):
        cache_reset()

@plugin.route('/cache_reload')
def cache_reload():
    if not session.is_logged_in:
        return
    session.user.favorites.load_all(force_reload=True)
    session.user.load_cache()
    session.user.playlists()


@plugin.route('/favorite_toggle')
def favorite_toggle():
    if not session.is_logged_in:
        return
    path = xbmc.getInfoLabel('Container.FolderPath').decode('utf-8')
    url = xbmc.getInfoLabel( "ListItem.FileNameAndPath" ).decode('utf-8')
    if not _addon_id in url or '/favorites/' in path:
        return
    try:
        xbmc.executebuiltin( "ActivateWindow(busydialog)" )
        if 'artist/' in url:
            item_id = url.split('artist/')[1]
            if not '/' in item_id:
                if session.user.favorites.isFavoriteArtist(item_id):
                    session.user.favorites.remove_artist(item_id)
                else:
                    session.user.favorites.add_artist(item_id)
        elif 'album/' in url:
            item_id = url.split('album/')[1]
            if not '/' in item_id:
                if session.user.favorites.isFavoriteAlbum(item_id):
                    session.user.favorites.remove_album(item_id)
                else:
                    session.user.favorites.add_album(item_id)
        elif 'play_track/' in url:
            item_id = url.split('play_track/')[1]
            item_id = item_id.split('/')[0] # Remove album_id behind the track_id
            if not '/' in item_id:
                if session.user.favorites.isFavoriteTrack(item_id):
                    session.user.favorites.remove_track(item_id)
                else:
                    session.user.favorites.add_track(item_id)
        elif 'playlist/' in url:
            item_id = url.split('playlist/')[1]
            item_id = item_id.split('/')[0] # Remove offset behind playlist_id
            if not '/' in item_id:
                if session.user.favorites.isFavoritePlaylist(item_id):
                    session.user.favorites.remove_playlist(item_id)
                else:
                    session.user.favorites.add_playlist(item_id)
        elif 'play_video/' in url:
            item_id = url.split('play_video/')[1]
            if not '/' in item_id:
                if session.user.favorites.isFavoriteVideo(item_id):
                    session.user.favorites.remove_video(item_id)
                else:
                    session.user.favorites.add_video(item_id)
    except:
        pass
    xbmc.executebuiltin( "Dialog.Close(busydialog)" ) # Avoid GUI Lock        
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/search')
def search():
    addon.setSetting('last_search_field', '')
    addon.setSetting('last_search_text', '')
    add_directory(_T(30106), plugin.url_for(search_type, field='artist'))
    add_directory(_T(30107), plugin.url_for(search_type, field='album'))
    add_directory(_T(30108), plugin.url_for(search_type, field='playlist'))
    add_directory(_T(30109), plugin.url_for(search_type, field='track'))
    add_directory(_T(30110), plugin.url_for(search_type, field='video'), end=True)


@plugin.route('/search_type/<field>')
def search_type(field):
    last_field = addon.getSetting('last_search_field').decode('utf-8')
    search_text = addon.getSetting('last_search_text').decode('utf-8')
    if last_field <> field or not search_text:
        addon.setSetting('last_search_field', field)
        keyboard = xbmc.Keyboard('', _T(30206))
        keyboard.doModal()
        if keyboard.isConfirmed():
            search_text = keyboard.getText()
        else:
            search_text = ''
    addon.setSetting('last_search_text', search_text)
    if search_text:
        searchresults = session.search(field, search_text)
        add_items(searchresults.artists, content=CONTENT_FOR_TYPE.get('files'), end=False)
        add_items(searchresults.albums, end=False)
        add_items(searchresults.playlists, end=False)
        add_items(searchresults.tracks, end=False)
        add_items(searchresults.videos, end=True)
    else:
        #xbmcplugin.setContent(plugin.handle, content='files')
        xbmcplugin.endOfDirectory(plugin.handle, succeeded=False, updateListing=False)


@plugin.route('/login')
def login():
    username = addon.getSetting('username')
    password = addon.getSetting('password')
    subscription_type = [SubscriptionType.hifi, SubscriptionType.premium][int('0' + addon.getSetting('subscription_type'))]

    if not username or not password:
        # Ask for username/password
        dialog = xbmcgui.Dialog()
        username = dialog.input(_T(30008), username)
        if not username:
            return
        password = dialog.input(_T(30009), option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if not password:
            return
        selected = dialog.select(_T(30010), [SubscriptionType.hifi, SubscriptionType.premium])
        if selected < 0:
            return
        subscription_type = [SubscriptionType.hifi, SubscriptionType.premium][selected]

    ok = session.login(username, password, subscription_type)
    if ok and (not addon.getSetting('username') or not addon.getSetting('password')):
        # Ask about remembering username/password
        dialog = xbmcgui.Dialog()
        if dialog.yesno(plugin.name, _T(30209)):
            addon.setSetting('username', username)
            addon.setSetting('password', password)
        else:
            addon.setSetting('password', '')
    if not ok:
        xbmcgui.Dialog().notification(plugin.name, _T(30253) , icon=xbmcgui.NOTIFICATION_ERROR)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/logout')
def logout():
    session.logout()
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/play_track/<track_id>/<album_id>')
def play_track(track_id, album_id):
    media_url = session.get_media_url(track_id, album_id=album_id)
    log("Playing: %s" % media_url)
    disableInputstreamAddon = False
    if not media_url.startswith('http://') and not media_url.startswith('https://') and \
        not 'app=' in media_url.lower() and not 'playpath=' in media_url.lower():
        # Rebuild RTMP URL
        if KODI_VERSION >= (17, 0):
            media_url = 'rtmp://%s' % media_url
            disableInputstreamAddon = True
        else:
            host, tail = media_url.split('/', 1)
            app, playpath = tail.split('/mp4:', 1)
            media_url = 'rtmp://%s app=%s playpath=mp4:%s' % (host, app, playpath)
    li = ListItem(path=media_url)
    if disableInputstreamAddon:
        # Krypton can play RTMP Audio Streams without inputstream.rtmp Addon
        li.setProperty('inputstreamaddon', '')
    mimetype = 'audio/flac' if session._config.quality == Quality.lossless and session.is_logged_in else 'audio/mpeg'
    li.setProperty('mimetype', mimetype)
    xbmcplugin.setResolvedUrl(plugin.handle, True, li)


@plugin.route('/play_track_cut/<track_id>/<cut_id>/<album_id>')
def play_track_cut(track_id, cut_id, album_id):
    media_url = session.get_media_url(track_id, cut_id=cut_id, album_id=album_id)
    log("Playing Cut %s: %s" % (cut_id, media_url))
    disableInputstreamAddon = False
    if not media_url.startswith('http://') and not media_url.startswith('https://') and \
        not 'app=' in media_url.lower() and not 'playpath=' in media_url.lower():
        # Rebuild RTMP URL
        if KODI_VERSION >= (17, 0):
            media_url = 'rtmp://%s' % media_url
            disableInputstreamAddon = True
        else:
            host, tail = media_url.split('/', 1)
            app, playpath = tail.split('/mp4:', 1)
            media_url = 'rtmp://%s app=%s playpath=mp4:%s' % (host, app, playpath)
    li = ListItem(path=media_url)
    if disableInputstreamAddon:
        # Krypton can play RTMP Audio Streams without inputstream.rtmp Addon
        li.setProperty('inputstreamaddon', '')
    mimetype = 'audio/flac' if session._config.quality == Quality.lossless and session.is_logged_in else 'audio/mpeg'
    li.setProperty('mimetype', mimetype)
    xbmcplugin.setResolvedUrl(plugin.handle, True, li)


@plugin.route('/play_video/<video_id>')
def play_video(video_id):
    media = session.get_video_url(video_id)
    if media:
        log("Playing: %s" % media.url)
        li = ListItem(path=media.url)
        li.setProperty('mimetype', 'video/mp4')
        xbmcplugin.setResolvedUrl(plugin.handle, True, li)


@plugin.route('/stream_locked')
def stream_locked():
    xbmcgui.Dialog().notification(heading=plugin.name, message=_T(30242), icon=xbmcgui.NOTIFICATION_INFO)


if __name__ == '__main__':
    try:
        plugin.run()
    except HTTPError as e:
        r = e.response
        if r.status_code in [401, 403]:
            msg = _T(30210)
        else:
            msg = r.reason
        try:
            msg = r.json().get('userMessage')
        except:
            pass
        xbmcgui.Dialog().notification('%s Error %s' % (plugin.name, r.status_code), msg, xbmcgui.NOTIFICATION_ERROR)
        traceback.print_exc()
