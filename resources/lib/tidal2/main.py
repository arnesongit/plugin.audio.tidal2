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
import json

from kodi_six import xbmc, xbmcgui, xbmcplugin, py2_decode
from requests import HTTPError

from .common import Const, plugin
from .textids import Msg, _T, _P
from .debug import log
from .tidalapi.models import Category, TrackUrl, VideoUrl, DeviceCode
from .config import settings
from .koditidal import TidalSession, DirectoryItem

try:
    # Python 3
    from urllib.parse import quote_plus, unquote_plus
except:
    # Python 2.7
    from urllib import quote_plus, unquote_plus

CONTENT_FOR_TYPE = {'artists': 'artists', 'albums': 'albums', 'playlists': 'albums', 'tracks': 'songs', 'videos': 'musicvideos', 'files': 'files'}
HOMEPAGE_ITEM_TYPES = {'PLAYLIST_LIST': 'playlists', 'ALBUM_LIST': 'albums', 'ARTIST_LIST': 'artists', 'TRACK_LIST': 'tracks', 'VIDEO_LIST': 'videos', 'MIX_LIST': 'mix'}

#------------------------------------------------------------------------------
# Initialization
#------------------------------------------------------------------------------

session = TidalSession(config=settings)

add_items = session.add_list_items
add_directory = session.add_directory_item


#------------------------------------------------------------------------------
# Plugin Functions
#------------------------------------------------------------------------------

@plugin.route('/')
def root():
    if session.is_logged_in:
        add_directory(_T(Msg.i30201), my_music)
        add_directory(_T(Msg.i30212), plugin.url_for(homepage_items))
    add_directory(_T(Msg.i30202), featured_playlists)
    categories = Category.groups()
    for item in categories:
        add_directory(_T(item), plugin.url_for(category, group=item))
    add_directory(_T(Msg.i30206), search)
    add_directory(_T(Msg.i30027), settings_dialog, isFolder=False)
    if session.is_logged_in:
        add_directory(_T(Msg.i30207), logout, end=True, isFolder=False)
    else:
        add_directory(_T(Msg.i30208), login, end=True, isFolder=False)


@plugin.route('/settings')
def settings_dialog():
    xbmc.executebuiltin('Addon.OpenSettings("%s")' % Const.addon_id)


@plugin.route('/homepage_items')
def homepage_items():
    params = { 'locale': settings.locale, 'deviceType': 'BROWSER' }
    apiPaths = []
    items = []
    for page_type in ['explore', 'home', 'videos']:
        r = session.request('GET', path='pages/%s' % page_type, params=params)
        if r.ok:
            json_obj = r.json()
            for row in json_obj['rows']:
                for module in row['modules']:
                    try:
                        item_type = module['type']
                        if item_type in HOMEPAGE_ITEM_TYPES:
                            apiPath = module['pagedList']['dataApiPath']
                            item = DirectoryItem(module['title'], plugin.url_for(homepage_item, item_type, quote_plus(apiPath)))
                            if not apiPath in apiPaths:
                                if item_type == 'MIX_LIST' and page_type == 'videos':
                                    item.name = item.name + ' (' + _P('videos') + ')'
                                items.append(item)
                                apiPaths.append(apiPath)
                        else:
                            log.info('Unknown Homepage Item "%s": %s' % (item_type, module.get('title', 'Unknown')))
                    except:
                        pass
    session.add_list_items(items, end=True)


@plugin.route('/homepage_item/<item_type>/<path>')
def homepage_item(item_type, path):
    path = py2_decode(unquote_plus(path)).strip()
    rettype = HOMEPAGE_ITEM_TYPES.get(item_type, 'NONE')
    if rettype != 'NONE':
        params = { 'locale': settings.locale, 'deviceType': 'BROWSER', 'offset': plugin.qs_offset, 'limit': min(50, settings.pageSize) }
        items = session._map_request(path=path, method='GET', params=params, ret=rettype)
        session.add_list_items(items, content=CONTENT_FOR_TYPE.get(rettype, 'files'), end=True, withNextPage=True)


@plugin.route('/category')
def category_list():
    categories = Category.groups()
    for item in categories:
        add_directory(_T(item), plugin.url_for(category, group=item), end=True if item == categories[-1] else False)


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
                category_content(group, item.path, content_type)
                return
    xbmcplugin.setContent(plugin.handle, CONTENT_FOR_TYPE.get('files'))
    if promoGroup and totalCount > 10:
        # Add Promotions as Folder on the Top if more than 10 Promotions available
        add_directory(_T(Msg.i30120), plugin.url_for(featured, group=promoGroup))
        add_directory('Master %s (MQA)' % _T(Msg.i30107), plugin.url_for(master_albums, offset=0))
        add_directory('Master %s (MQA)' % _T(Msg.i30108), plugin.url_for(master_playlists, offset=0))
    # Add Category Items as Folders
    add_items(items, content=None, end=not(promoGroup and totalCount <= 10))
    if promoGroup and totalCount <= 10:
        # Show up to 10 Promotions as single Items
        promoItems = session.get_featured(promoGroup, types=['ALBUM', 'PLAYLIST', 'VIDEO'], limit=min(settings.pageSize, 999))
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


@plugin.route('/category/<group>/<path>/<content_type>')
def category_content(group, path, content_type):
    items = session.get_category_content(group, path, content_type, offset=int('%s' % plugin.qs_offset), limit=settings.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get(content_type, 'songs'), withNextPage=True)


@plugin.route('/master_albums')
def master_albums():
    items = session.master_albums(offset=int('%s' % plugin.qs_offset), limit=settings.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/master_playlists')
def master_playlists():
    items = session.master_playlists(offset=int('%s' % plugin.qs_offset), limit=settings.pageSize)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/track_radio/<track_id>')
def track_radio(track_id):
    add_items(session.get_track_radio(track_id, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/recommended/tracks/<track_id>')
def recommended_tracks(track_id):
    add_items(session.get_recommended_items('tracks', track_id, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/recommended/videos/<video_id>')
def recommended_videos(video_id):
    add_items(session.get_recommended_items('videos', video_id, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('videos'))


@plugin.route('/featured/<group>')
def featured(group):
    items = session.get_featured(group, types=['ALBUM', 'PLAYLIST', 'VIDEO'], limit=min(settings.pageSize, 999))
    add_items(items, content=CONTENT_FOR_TYPE.get('files'))


@plugin.route('/featured_playlists')
def featured_playlists():
    items = session.get_featured(limit=min(settings.pageSize, 999))
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/my_music')
def my_music():
    session.user.update_caches()
    add_directory(_T(Msg.i30273), user_folders)
    add_directory(_T(Msg.i30213), user_playlists)
    add_directory(_T(Msg.i30214), plugin.url_for(favorites, content_type='artists'))
    add_directory(_T(Msg.i30215), plugin.url_for(favorites, content_type='albums'))
    add_directory(_T(Msg.i30216), plugin.url_for(favorites, content_type='playlists'))
    add_directory(_T(Msg.i30217), plugin.url_for(favorites, content_type='tracks'))
    add_directory(_T(Msg.i30218), plugin.url_for(favorites, content_type='videos'))
    add_directory(_T(Msg.i30275), plugin.url_for(favorites, content_type='mixes'))
    add_directory(_T(Msg.i30271), plugin.url_for(session_info))
    add_directory(_T(Msg.i30272), plugin.url_for(refresh_token), end=True)


@plugin.route('/album/<album_id>')
def album_view(album_id):
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_TRACKNUM)
    album = session.get_album(album_id)
    if album and album.numberOfVideos > 0:
        add_directory(_T(Msg.i30110), plugin.url_for(album_videos, album_id=album_id))
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
    add_directory(_T(Msg.i30225), plugin.url_for(artist_bio, artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
    add_directory(_T(Msg.i30226), plugin.url_for(top_tracks, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_P('albums'), plugin.url_for(artist_albums, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30267), plugin.url_for(artist_singles, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30270), plugin.url_for(artist_compilations, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30110), plugin.url_for(artist_videos, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30227), plugin.url_for(artist_radio, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30228), plugin.url_for(artist_playlists, artist_id), thumb=artist.image, fanart=artist.fanart)
    add_directory(_T(Msg.i30229), plugin.url_for(similar_artists, artist_id), thumb=artist.image, fanart=artist.fanart)
    if session.is_logged_in:
        if session.user.favorites.isFavoriteArtist(artist_id):
            add_directory(_T(Msg.i30220), plugin.url_for(favorites_remove, content_type='artists', item_id=artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
        else:
            add_directory(_T(Msg.i30219), plugin.url_for(favorites_add, content_type='artists', item_id=artist_id), thumb=artist.image, fanart=artist.fanart, isFolder=False)
    albums = session.get_artist_albums(artist_id, limit=min(settings.pageSize, 50)) + \
             session.get_artist_albums_ep_singles(artist_id, limit=min(settings.pageSize, 50))
    add_items(albums, content=None)


@plugin.route('/artist/<artist_id>/bio')
def artist_bio(artist_id):
    artist = session.get_artist(artist_id)
    info = session.get_artist_info(artist_id)
    text = ''
    if info.get('summary', None):
        text += '%s:\n\n' % _T(Msg.i30230) + info.get('summary') + '\n\n'
    if info.get('text', None):
        text += '%s:\n\n' % _T(Msg.i30225) + info.get('text')
    if text:
        xbmcgui.Dialog().textviewer(artist.name, text)


@plugin.route('/artist/<artist_id>/top')
def top_tracks(artist_id):
    add_items(session.get_artist_top_tracks(artist_id, offset=plugin.qs_offset, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'), withNextPage=True)


@plugin.route('/artist/<artist_id>/radio')
def artist_radio(artist_id):
    add_items(session.get_artist_radio(artist_id, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'))


@plugin.route('/artist/<artist_id>/albums')
def artist_albums(artist_id):
    add_items(session.get_artist_albums(artist_id, offset=plugin.qs_offset, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/artist/<artist_id>/singles')
def artist_singles(artist_id):
    add_items(session.get_artist_albums_ep_singles(artist_id, offset=plugin.qs_offset, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/artist/<artist_id>/compilations')
def artist_compilations(artist_id):
    add_items(session.get_artist_albums_other(artist_id, offset=plugin.qs_offset, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/artist/<artist_id>/videos')
def artist_videos(artist_id):
    add_items(session.get_artist_videos(artist_id, offset=plugin.qs_offset, limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('videos'), withNextPage=True)


@plugin.route('/artist/<artist_id>/playlists')
def artist_playlists(artist_id):
    add_items(session.get_artist_playlists(artist_id), content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/artist/<artist_id>/similar')
def similar_artists(artist_id):
    add_items(session.get_artist_similar(artist_id), content=CONTENT_FOR_TYPE.get('artists'))


@plugin.route('/mix/<mix_id>')
def mix_view(mix_id):
    params = { 'locale': settings.locale, 'deviceType': 'BROWSER', 'mixId': mix_id }
    r = session.request('GET', path='pages/mix', params=params)
    if r.ok:
        json_obj = r.json()
        for row in json_obj['rows']:
            for module in row['modules']:
                try:
                    item_type = module['type']
                    if item_type in HOMEPAGE_ITEM_TYPES:
                        api_path = module['pagedList']['dataApiPath']
                        homepage_item(item_type, api_path)
                        break
                except:
                    pass


@plugin.route('/playlist/<playlist_id>/items')
def playlist_view(playlist_id):
    add_items(session.get_playlist_items(playlist_id, offset=int('0%s' % plugin.qs_offset), limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'), withNextPage=True)


@plugin.route('/playlist/<playlist_id>/tracks')
def playlist_tracks(playlist_id):
    add_items(session.get_playlist_tracks(playlist_id, offset=int('0%s' % plugin.qs_offset), limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('tracks'), withNextPage=True)


@plugin.route('/playlist/<playlist_id>/albums')
def playlist_albums(playlist_id):
    add_items(session.get_playlist_albums(playlist_id, offset=int('0%s' % plugin.qs_offset), limit=settings.pageSize), content=CONTENT_FOR_TYPE.get('albums'), withNextPage=True)


@plugin.route('/user_playlists')
def user_playlists():
    items = session.user.playlists(flattened=True, allPlaylists=False)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'), withNextPage=False)


@plugin.route('/user_playlist/rename/<playlist_id>')
def user_playlist_rename(playlist_id):
    playlist = session.get_playlist(playlist_id)
    ok = session.user.renamePlaylistDialog(playlist)
    if ok:
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/clear/<playlist_id>')
def user_playlist_clear(playlist_id):
    dialog = xbmcgui.Dialog()
    playlist = session.get_playlist(playlist_id)
    ok = dialog.yesno(_T(Msg.i30258).format(what=_T('playlist')), _T(Msg.i30259).format(name=playlist.title, count=playlist.numberOfItems))
    if ok:
        session.show_busydialog(_T(Msg.i30258).format(what=_T('playlist')), playlist.name)
        try:
            session.user.remove_all_playlist_entries(playlist_id)
        except Exception as e:
            log.logException(e, txt='Couldn''t clear playlist %s' % playlist_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/delete/<playlist_id>')
def user_playlist_delete(playlist_id):
    dialog = xbmcgui.Dialog()
    playlist = session.get_playlist(playlist_id)
    ok = dialog.yesno(_T(Msg.i30235).format(what=_T('playlist')), _T(Msg.i30236).format(name=playlist.title, count=playlist.numberOfItems))
    if ok:
        session.show_busydialog(_T(Msg.i30235).format(what=_T('playlist')), playlist.name)
        try:
            session.user.delete_playlist(playlist_id)
        except Exception as e:
            log.logException(e, txt='Couldn''t delete playlist %s' % playlist_id)
            traceback.print_exc()
        xbmc.sleep(1000)
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/add/<item_type>/<item_id>')
def user_playlist_add_item(item_type, item_id):
    if item_type == 'playlist':
        srcPlaylist = session.get_playlist(item_id)
        if not srcPlaylist:
            return
        items = session.get_playlist_items(playlist=srcPlaylist)
        # Sort Items by Artist, Title
        sortMode = 'ALBUM' if settings.album_playlist_tag in srcPlaylist.description else 'LABEL'
        items.sort(key=lambda line: line.getSortText(mode=sortMode).upper(), reverse=False)
        items = ['%s' % item.id for item in items if item.available]
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
        session.show_busydialog(_T(Msg.i30263).format(what=_T('playlist')), playlist.name)
        try:
            session.user.add_playlist_entries(playlist=playlist, item_ids=items)
        except Exception as e:
            log.logException(e, txt='Couldn''t add item to playlist %s' % item_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove/<playlist_id>/<entry_no>')
def user_playlist_remove_item(playlist_id, entry_no):
    item_no = int('0%s' % entry_no) + 1
    playlist = session.get_playlist(playlist_id)
    ok = xbmcgui.Dialog().yesno(_T(Msg.i30247).format(name=playlist.name), _T(Msg.i30241).format(entry=item_no))
    if ok:
        session.show_busydialog(_T(Msg.i30264).format(what=_T('playlist')), playlist.name)
        try:
            session.user.remove_playlist_entry(playlist, entry_no=entry_no)
        except Exception as e:
            log.logException(e, txt='Couldn''t remove item from playlist %s' % playlist_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove_id/<playlist_id>/<item_id>')
def user_playlist_remove_id(playlist_id, item_id):
    playlist = session.get_playlist(playlist_id)
    ok = xbmcgui.Dialog().yesno(_T(Msg.i30247).format(name=playlist.name), _T(Msg.i30246))
    if ok:
        session.show_busydialog(_T(Msg.i30264).format(what=_T('playlist')), playlist.name)
        try:
            session.user.remove_playlist_entry(playlist, item_id=item_id)
        except Exception as e:
            log.logException(e, txt='Couldn''t remove item from playlist %s' % playlist_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/remove_album/<playlist_id>/<item_id>')
def user_playlist_remove_album(playlist_id, item_id, dialog=True):
    playlist = session.get_playlist(playlist_id)
    ok = True
    if dialog:
        ok = xbmcgui.Dialog().yesno(_T(Msg.i30247).format(name=playlist.name), _T(Msg.i30246))
    if ok:
        session.show_busydialog(_T(Msg.i30264).format(what=_T('playlist')), playlist.name)
        try:
            items = session.get_playlist_tracks(playlist)
            for item in items:
                if '%s' % item.album.id == '%s' % item_id:
                    session.user.remove_playlist_entry(playlist, entry_no=item._playlist_pos)
                    break # Remove only one Item
        except Exception as e:
            log.logException(e, txt='Couldn''t remove album from playlist %s' % playlist_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist/move/<playlist_id>/<entry_no>/<item_id>')
def user_playlist_move_entry(playlist_id, entry_no, item_id):
    dialog = xbmcgui.Dialog()
    playlist = session.user.selectPlaylistDialog(headline=_T(Msg.i30248).format(what=_T('playlist')), allowNew=True)
    if playlist and playlist.id != playlist_id:
        session.show_busydialog(_T(Msg.i30265).format(what=_T('playlist')), playlist.name)
        try:
            ok = session.user.add_playlist_entries(playlist=playlist, item_ids=[item_id])
            if ok:
                ok = session.user.remove_playlist_entry(playlist_id, entry_no=entry_no)
            else:
                dialog.notification(plugin.name, _T(Msg.i30269), xbmcgui.NOTIFICATION_ERROR)
        except Exception as e:
            log.logException(e, txt='Couldn''t move item from playlist %s' % playlist_id)
            traceback.print_exc()
        session.hide_busydialog()
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_set_default/<item_type>/<playlist_id>')
def user_playlist_set_default(item_type, playlist_id):
    if item_type == 'folder':
        item = session.user.folder(playlist_id)
        if item:
            settings.setSetting('default_folder_id', item.id)
            settings.setSetting('default_folder_name', item.name)
    else:
        item = session.get_playlist(playlist_id)
        if item:
            if item_type.lower().find('track') >= 0:
                settings.setSetting('default_trackplaylist_id', item.id)
                settings.setSetting('default_trackplaylist_title', item.title)
            elif item_type.lower().find('video') >= 0:
                settings.setSetting('default_videoplaylist_id', item.id)
                settings.setSetting('default_videoplaylist_title', item.title)
            elif item_type.lower().find('album') >= 0:
                settings.setSetting('default_albumplaylist_id', item.id)
                settings.setSetting('default_albumplaylist_title', item.title)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_reset_default/<item_type>')
def user_playlist_reset_default(item_type):
    if item_type.lower().find('track') >= 0:
        settings.setSetting('default_trackplaylist_id', '')
        settings.setSetting('default_trackplaylist_title', '')
    elif item_type.lower().find('video') >= 0:
        settings.setSetting('default_videoplaylist_id', '')
        settings.setSetting('default_videoplaylist_title', '')
    elif item_type.lower().find('album') >= 0:
        settings.setSetting('default_albumplaylist_id', '')
        settings.setSetting('default_albumplaylist_title', '')
    elif item_type.lower().find('folder') >= 0:
        settings.setSetting('default_folder_id', '')
        settings.setSetting('default_folder_name', '')
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_cm/<playlist_id>')
def user_playlist_cm(playlist_id):
    item = session.get_playlist(playlist_id)
    if item.isUserPlaylist:
        cm = []
        cmd = []
        cm.append(_T(Msg.i30251).format(what=_T('playlist')))
        cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist/rename/%s' % playlist_id))
        if item.numberOfItems > 0:
            cm.append(_T(Msg.i30258).format(what=_T('playlist')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist/clear/%s' % playlist_id))
        cm.append(_T(Msg.i30235).format(what=_T('playlist')))
        cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist/delete/%s' % playlist_id))
        if str(playlist_id) == settings.default_trackplaylist_id:
            cm.append(_T(Msg.i30250).format(what=_P('Track')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/tracks'))
        else:
            cm.append(_T(Msg.i30249).format(what=_P('Track')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/tracks/%s' % playlist_id))
        if str(playlist_id) == settings.default_videoplaylist_id:
            cm.append(_T(Msg.i30250).format(what=_P('Video')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/videos'))
        else:
            cm.append(_T(Msg.i30249).format(what=_P('Video')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/videos/%s' % playlist_id))
        if str(playlist_id) == settings.default_albumplaylist_id:
            cm.append(_T(Msg.i30250).format(what=_P('Album')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_reset_default/albums'))
        else:
            cm.append(_T(Msg.i30249).format(what=_P('Album')))
            cmd.append('RunPlugin(%s)' % plugin.url_for_path('/user_playlist_set_default/albums/%s' % playlist_id))
        i = xbmcgui.Dialog().contextmenu(cm)
        if i >= 0 and i < len(cmd):
            xbmc.executebuiltin(cmd[i])


@plugin.route('/user_folder_toggle')
def user_folder_toggle():
    if not session.is_logged_in:
        return
    url = xbmc.getInfoLabel( "ListItem.FilenameandPath" )
    if not Const.addon_id in url:
        return
    if not 'playlist/' in url:
        user_playlist_toggle()
        return
    item_id = url.split('playlist/')[1].split('/')[0]
    playlist = session.get_playlist(item_id)
    if not playlist:
        return
    folder = session.user.folder(settings.default_folder_id)
    if not folder:
        user_folder_add(playlist.id)
        return
    try:
        if playlist.parentFolderId:
            session.show_busydialog(_T(Msg.i30264).format(what=_T('folder')), folder.name)
            session.user.move_folder_entries(trns=playlist.trn, folder='root')
        else:
            session.show_busydialog(_T(Msg.i30263).format(what=_T('folder')), folder.name)
            session.user.add_folder_entry(folder, playlist)
    except Exception as e:
        log.logException(e, txt='Couldn''t toggle folder for playlist %s' % playlist.id)
        traceback.print_exc()
    session.hide_busydialog()
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_playlist_toggle')
def user_playlist_toggle():
    if not session.is_logged_in:
        return
    url = xbmc.getInfoLabel( "ListItem.FilenameandPath" )
    if not Const.addon_id in url:
        return
    if 'playlist/' in url:
        user_folder_toggle()
        return
    item_type = 'unknown'
    if 'play_track/' in url:
        item_type = 'track'
        userpl_id = settings.default_trackplaylist_id
        userpl_name = settings.default_trackplaylist_title
        item_id = url.split('play_track/')[1]
        item_id = item_id.split('/')[0]
        item = session.get_track(item_id)
    elif 'play_video/' in url:
        item_type = 'video'
        userpl_id = settings.default_videoplaylist_id
        userpl_name = settings.default_videoplaylist_title
        item_id = url.split('play_video/')[1]
        item_id = item_id.split('/')[0]
        item = session.get_video(item_id)
    elif 'album/' in url:
        item_type = 'album'
        userpl_id = settings.default_albumplaylist_id
        userpl_name = settings.default_albumplaylist_title
        item_id = url.split('album/')[1]
        item_id = int('0%s' % item_id.split('/')[0])
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
        if item._userplaylists and userpl_id in item._userplaylists:
            session.show_busydialog(_T(Msg.i30264).format(what=_T('playlist')), userpl_name)
            session.user.remove_playlist_entry(playlist=userpl_id, item_id=item.id)
        else:
            session.show_busydialog(_T(Msg.i30263).format(what=_T('playlist')), userpl_name)
            session.user.add_playlist_entries(playlist=userpl_id, item_ids=['%s' % item.id])
    except Exception as e:
        log.logException(e, txt='Couldn''t toggle playlist for %s' % item_type)
        traceback.print_exc()
    session.hide_busydialog()
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folders')
def user_folders():
    folders = session.user.folders()
    folder_ids = [f.id for f in folders]
    items = session.user.playlists(flattened=False, allPlaylists=False)
    playlists = [p for p in items if p.parentFolderId not in folder_ids]
    add_items(folders + playlists, content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/user_folders/<folder_id>')
def user_folder_items(folder_id):
    items = session.user.folder_items(folder_id)
    add_items(items, content=CONTENT_FOR_TYPE.get('albums'))


@plugin.route('/user_folder/add/<playlist_id>')
def user_folder_add(playlist_id):
    if session.user.addToFolderDialog(playlist_id):
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folder/move/<playlist_id>')
def user_folder_move(playlist_id):
    if session.user.moveToFolderDialog(playlist_id):
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folder/create')
def user_folder_create():
    if session.user.newFolderDialog():
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folder/rename/<folder_id>')
def user_folder_rename(folder_id):
    if session.user.renameFolderDialog(folder_id):
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folder/remove/<folder_id>/<playlist_id>')
def user_folder_remove(folder_id, playlist_id):
    if session.user.removeFromFolderDialog(folder_id, playlist_id):
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/user_folder/delete/<folder_id>')
def user_folder_delete(folder_id):
    if session.user.deleteFolderDialog(folder_id):
        xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/favorites')
def favorites_menu():
    session.user.favorites.load_all(force_reload=True)
    add_directory(_T(Msg.i30214), plugin.url_for(favorites, content_type='artists'))
    add_directory(_T(Msg.i30215), plugin.url_for(favorites, content_type='albums'))
    add_directory(_T(Msg.i30216), plugin.url_for(favorites, content_type='playlists'))
    add_directory(_T(Msg.i30217), plugin.url_for(favorites, content_type='tracks'))
    add_directory(_T(Msg.i30218), plugin.url_for(favorites, content_type='videos'))
    add_directory(_T(Msg.i30218), plugin.url_for(favorites, content_type='mixes'), end=True)


@plugin.route('/favorites/<content_type>')
def favorites(content_type):
    limit = min(settings.pageSize, 100 if content_type == 'videos' else 9999)
    if content_type in ['playlists', 'mixes']:
        items = session.user.favorites.get(content_type, offset=0, limit=50)
    else:
        items = session.user.favorites.get(content_type, offset=plugin.qs_offset, limit=limit)
    if content_type in ['playlists', 'artists', 'mixes']:
        items.sort(key=lambda line: line.name, reverse=False)
        if content_type in ['playlists', 'mixes']:
            items = items[plugin.qs_offset:plugin.qs_offset+limit]
    else:
        items.sort(key=lambda line: '%s - %s' % (line.artist.name, line.title), reverse=False)
    add_items(items, content=CONTENT_FOR_TYPE.get(content_type, 'songs'), withNextPage=True)


@plugin.route('/favorites/add/<content_type>/<item_id>')
def favorites_add(content_type, item_id):
    if 'playlist' in content_type:
        playlist = session.get_playlist(item_id)
        if playlist and playlist.isUserPlaylist:
            log.error("User-Playlist '%s' can't be set as favorite" % playlist.name)
            return
    ok = session.user.favorites.add(content_type, item_id)
    if ok:
        xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30231).format(what=_T(content_type)), icon=xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/favorites/remove/<content_type>/<item_id>')
def favorites_remove(content_type, item_id):
    if 'playlist' in content_type:
        playlist = session.get_playlist(item_id)
        if playlist and playlist.isUserPlaylist:
            log.error("User-Playlist '%s' can't be set as favorite" % playlist.name)
            return
    ok = session.user.favorites.remove(content_type, item_id)
    if ok:
        xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30232).format(what=_T(content_type)), icon=xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/lock_artist/<artist_id>')
def lock_artist(artist_id):
    session.user.favorites.setLockedArtist(artist_id, True)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/unlock_artist/<artist_id>')
def unlock_artist(artist_id):
    session.user.favorites.setLockedArtist(artist_id, False)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/cache_reset')
def cache_reset():
    if not session.is_logged_in:
        return
    session.user.delete_cache()
    session.user.favorites.delete_cache()


@plugin.route('/cache_reset_confirmed')
def cache_reset_confirmed():
    if xbmcgui.Dialog().yesno(_T(Msg.i30507), _T(Msg.i30508)):
        cache_reset()


@plugin.route('/cache_reload')
def cache_reload():
    if not session.is_logged_in:
        return
    session.user.favorites.load_all(force_reload=True)
    session.user.load_cache()
    session.user.playlists(flattened=True, allPlaylists=True)


@plugin.route('/favorite_toggle')
def favorite_toggle():
    if not session.is_logged_in:
        return
    path = xbmc.getInfoLabel('Container.FolderPath')
    url = xbmc.getInfoLabel( "ListItem.FileNameAndPath" )
    if not Const.addon_id in url or '/favorites/' in path:
        return
    try:
        isFavorite = False
        content_type = None
        if 'artist/' in url:
            item_id = url.split('artist/')[1]
            item_id = int('0%s' % item_id.split('/')[0])
            if not '/' in item_id:
                content_type = 'artists'
                isFavorite = session.user.favorites.isFavoriteArtist(item_id)
        elif 'album/' in url:
            item_id = url.split('album/')[1]
            item_id = item_id.split('/')[0]
            if not '/' in item_id:
                content_type = 'albums'
                isFavorite = session.user.favorites.isFavoriteAlbum(item_id)
        elif 'play_track/' in url:
            item_id = url.split('play_track/')[1]
            item_id = item_id.split('/')[0] # Remove album_id behind the track_id
            if not '/' in item_id:
                content_type = 'tracks'
                isFavorite = session.user.favorites.isFavoriteTrack(item_id)
        elif 'playlist/' in url:
            item_id = url.split('playlist/')[1]
            item_id = item_id.split('/')[0] # Remove offset behind playlist_id
            if not '/' in item_id:
                content_type = 'playlists'
                isFavorite = session.user.favorites.isFavoritePlaylist(item_id)
        elif 'play_video/' in url:
            item_id = url.split('play_video/')[1]
            if not '/' in item_id:
                content_type = 'videos'
                isFavorite = session.user.favorites.isFavoriteVideo(item_id)
        elif 'mix/' in url:
            item_id = url.split('mix/')[1]
            if not '/' in item_id:
                content_type = 'mixes'
                isFavorite = session.user.favorites.isFavoriteMix(item_id)
        if content_type == None:
            return
        if isFavorite:
            favorites_remove(content_type, item_id)
        else:
            favorites_add(content_type, item_id)
    except:
        pass


@plugin.route('/search')
def search():
    settings.setSetting('last_search_field', '')
    settings.setSetting('last_search_text', '')
    add_directory(_T(Msg.i30106), plugin.url_for(search_type, field='artist'))
    add_directory(_T(Msg.i30107), plugin.url_for(search_type, field='album'))
    add_directory(_T(Msg.i30108), plugin.url_for(search_type, field='playlist'))
    add_directory(_T(Msg.i30109), plugin.url_for(search_type, field='track'))
    add_directory(_T(Msg.i30110), plugin.url_for(search_type, field='video'), end=True)


@plugin.route('/search_type/<field>')
def search_type(field):
    last_field = settings.getSetting('last_search_field')
    search_text = settings.getSetting('last_search_text')
    if last_field != field or not search_text:
        settings.setSetting('last_search_field', field)
        keyboard = xbmc.Keyboard('', _T(Msg.i30206))
        keyboard.doModal()
        if keyboard.isConfirmed():
            search_text = keyboard.getText()
        else:
            search_text = ''
    settings.setSetting('last_search_text', search_text)
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
    try:
        try:
            args = plugin.args
            code = None
            if 'deviceCode' in args and '_client_id' in args:
                # Got device code as query string from Web-GUI login page.
                code = DeviceCode(
                    deviceCode = args['deviceCode'][0],
                    userCode = args['userCode'][0],
                    verificationUri = args['verificationUri'][0],
                    verificationUriComplete = args['verificationUriComplete'][0],
                    expiresIn = int(args['expiresIn'][0]),
                    interval = int(args['interval'][0]),
                    _client_id = args['_client_id'][0],
                    _client_secret = args['_client_secret'][0] )
        except:
            code = None
        if not code and (settings.client_id == '' or settings.client_secret == ''):
            url = 'http://{ip}:{port}/client'.format(ip=xbmc.getInfoLabel('Network.IPAddress'), port=settings.fanart_server_port)
            xbmcgui.Dialog().ok(_T(Msg.i30281), _T(Msg.i30257).format(url=url))
            settings_dialog()
        else:
            session.login(device_code=code)
    except Exception as e:
        log.logException(e, 'Login failed !')
        xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30253), icon=xbmcgui.NOTIFICATION_ERROR)
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/logout')
def logout():
    if xbmcgui.Dialog().yesno(_T(Msg.i30207), _T(Msg.i30256)):
        session.logout()
    xbmc.executebuiltin('Container.Refresh()')


@plugin.route('/session_info')
def session_info():
    info = session._map_request(path='sessions', method='GET', ret='json')
    dialog = xbmcgui.Dialog()
    dialog.ok(_T(Msg.i30271), 
              '%s: %s\n' % (_T(Msg.i30008), info['userId']) +
              '%s: %s\n' % (_T(Msg.i30019), info['sessionId']) +
              '%s: %s\n' % (_T(Msg.i30020), info['client']['name']) +
              '%s: %s' % (_T(Msg.i30022), settings.expire_time))


@plugin.route('/refresh_token')
def refresh_token():
    log.info("Old Expire Time: %s" % settings.expire_time)
    ok = session.token_refresh()
    if ok:
        log.info("New Expire Time: %s" % settings.expire_time)
    else:
        log.error('Token Refresh failed.')
    pass


@plugin.route('/play_track/<track_id>/<album_id>')
def play_track(track_id, album_id):
    play_track_cut(track_id, None, album_id)


@plugin.route('/play_track_cut/<track_id>/<cut_id>/<album_id>')
def play_track_cut(track_id, cut_id, album_id):
    try:
        media = session.get_track_url(track_id, cut_id=cut_id)
        if cut_id:
            log.info("Playing Cut %s: %s with MimeType: %s" % (cut_id, media.url, media.get_mimeType()))
        else:
            log.info("Playing: %s with MimeType: %s" % (media.url, media.get_mimeType()))
        if settings.set_playback_info:
            track = session.get_track(track_id, withAlbum=False)
            url, li, isFolder = track.getListItem()
            li.setPath(media.url)
        else:
            li = xbmcgui.ListItem(path=media.url)
    except Exception as e:
        xbmcgui.Dialog().notification('%s Fatal Error' % plugin.name, repr(e), xbmcgui.NOTIFICATION_ERROR)
        traceback.print_exc()
        media = TrackUrl(url=settings.unplayable_m4a)
        li = xbmcgui.ListItem(path=media.url)
    li.setProperty('mimetype', media.get_mimeType())
    xbmcplugin.setResolvedUrl(plugin.handle, True, li)


@plugin.route('/play_video/<video_id>')
def play_video(video_id):
    try:
        media = session.get_video_url(video_id)
        if isinstance(media, VideoUrl) and media.url:
            log.info("Playing: %s with MimeType: %s" % (media.url, media.get_mimeType()))
            if settings.set_playback_info:
                video = session.get_video(video_id)
                url, li, isFolder = video.getListItem()
                li.setPath(media.url)
            else:
                li = xbmcgui.ListItem(path=media.url)
        else:
            log.warning("Got no video url. Playing silence for unplayable video %s to avoid kodi crash" % video_id)
            media = TrackUrl(url = settings.unplayable_m4a)
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
        media = TrackUrl(url = settings.unplayable_m4a)
    except Exception as e:
        xbmcgui.Dialog().notification('%s Fatal Error' % plugin.name, repr(e), xbmcgui.NOTIFICATION_ERROR)
        traceback.print_exc()
        media = TrackUrl(url=settings.unplayable_m4a)
    li = xbmcgui.ListItem(path=media.url)
    li.setProperty('mimetype', media.get_mimeType())
    xbmcplugin.setResolvedUrl(plugin.handle, True, li)


@plugin.route('/stream_locked')
def stream_locked():
    xbmcgui.Dialog().notification(plugin.name, _T(Msg.i30242), icon=xbmcgui.NOTIFICATION_INFO)


#------------------------------------------------------------------------------
# MAIN Program of the Plugin
#------------------------------------------------------------------------------

def run(argv=sys.argv):
    try:
        plugin.run(argv=argv)
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
        xbmcgui.Dialog().notification('%s Error %s' % (plugin.name, r.status_code), msg, xbmcgui.NOTIFICATION_ERROR)
        traceback.print_exc()
    except Exception as e:
        xbmcgui.Dialog().notification('%s Fatal Error' % plugin.name, repr(e), xbmcgui.NOTIFICATION_ERROR)
        traceback.print_exc()
    finally:
        session.cleanup()
        log.killDebugThreads()

# End of File