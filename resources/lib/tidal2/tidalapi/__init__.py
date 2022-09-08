# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 arneson
# Copyright (C) 2014 Thomas Amland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import os
import re
import datetime
import random
import json
import logging
import requests
import base64
import hashlib
import pyaes
import uuid
from requests.structures import CaseInsensitiveDict

from .models import *

try:
    from urlparse import parse_qs, urljoin, urlsplit
    from urllib import urlencode, unquote
except ImportError:
    from urllib.parse import parse_qs, urljoin, urlsplit, urlencode, unquote


# log = logging.getLogger(__name__.split('.')[-1])
from ..debug import log

try:
    from requests.packages import urllib3
    urllib3.disable_warnings() # Disable OpenSSL Warnings in URLLIB3
except:
    pass

TIDAL_HOMEPAGE = 'https://listen.tidal.com'
URL_API_V1 = 'https://api.tidal.com/v1/'
URL_API_V2 = 'https://api.tidal.com/v2/'
URL_LOGIN = 'https://login.tidal.com/'
OAUTH_BASE_URL = 'https://auth.tidal.com/v1/oauth2/'
DEFAULT_SCOPE = 'r_usr+w_usr+w_sub' # w_usr=WRITE_USR, r_usr=READ_USR_DATA, w_sub=WRITE_SUBSCRIPTION
REFRESH_SCOPE = 'r_usr+w_usr'

ALL_SAERCH_FIELDS = ['ARTISTS', 'ALBUMS', 'PLAYLISTS', 'TRACKS', 'VIDEOS']


class Session(object):

    def __init__(self, config):
        """:type _config: :class:`Config`"""
        self._config = config
        self.user = User(self)
        self._cursor = ''
        self._cursor_pos = 0
        self._streamingSessionId = None

    def cleanup(self):
        self._config = None
        if self.user:
            self.user._session = None
            if self.user.favorites:
                self.user.favorites._session = None
                self.user.favorites = None
            self.user = None

    def get_country_code(self, default='DE'):
        try:
            url = urljoin(URL_API_V1, 'country/context')
            headers = { 'X-Tidal-Token': self._config.preview_token}
            r = requests.get(url, params={'countryCode': 'WW'}, headers=headers)
            if not r.ok:
                return default
            return r.json().get('countryCode', default)
        except:
            return default

    def login_part1(self, client_id=None, client_secret=None):
        if not client_id or not client_secret:
            client_id = self._config.client_id
            client_secret = self._config.client_secret
        data = {
            'client_id': pyaes.AESModeOfOperationCTR(self._config.token_secret).decrypt(base64.b64decode(client_id)).decode('utf-8') if self._config.client_name else client_id,
            'scope': DEFAULT_SCOPE
        }
        r = requests.post(urljoin(OAUTH_BASE_URL, 'device_authorization'), data=data)
        r = self.check_response(r)
        device_code = self._parse_device_code(r.json())
        device_code._client_id = client_id
        device_code._client_secret = client_secret
        return device_code

    def login_part2(self, device_code):
        data = {
            'client_id': pyaes.AESModeOfOperationCTR(self._config.token_secret).decrypt(base64.b64decode(device_code._client_id)).decode('utf-8') if self._config.client_name else device_code._client_id,
            'client_secret': pyaes.AESModeOfOperationCTR(self._config.token_secret).decrypt(base64.b64decode(device_code._client_secret)).decode('utf-8') if self._config.client_name else device_code._client_secret,
            'device_code': device_code if isinstance(device_code, string_types) else device_code.deviceCode,
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            'scope': DEFAULT_SCOPE
        }
        r = requests.post(urljoin(OAUTH_BASE_URL, 'token'), data=data)
        if self._config.debug_json:
            r = self.check_response(r, raiseOnError=False)
        try:
            token = self._parse_auth_token(r.json())
            if token.success:
                self._config.user_id = token.user_id
                self._config.user_country_code = token.country_code
                self._config.token_type = token.token_type
                self._config.access_token = token.access_token
                if token.refresh_token:
                    self._config.refresh_token = token.refresh_token
                if self._config.client_name:
                    self._config.client_id = base64.b64encode(pyaes.AESModeOfOperationCTR(self._config.token_secret).encrypt(data['client_id'].encode('utf-8'))).decode('utf-8')
                    self._config.client_secret = base64.b64encode(pyaes.AESModeOfOperationCTR(self._config.token_secret).encrypt(data['client_secret'].encode('utf-8'))).decode('utf-8')
                else:
                    self._config.client_id = data['client_id']
                    self._config.client_secret = data['client_secret']
                self._config.expires_in = token.expires_in
                self._config.login_time = token.login_time
                self._config.refresh_time = token.login_time
                self._config.expire_time = token.expire_time
        except:
            token = AuthToken(status=500, error='Unknown error', error_description='No Json data in respose')
        return token


    @property
    def is_logged_in(self):
        return True if self._config.access_token and self._config.user_country_code and self.user else False

    def check_login(self):
        """ Returns true if current session is valid, false otherwise. """
        if not self.is_logged_in:
            return False
        self.user.subscription = self.get_user_subscription(self.user.id)
        return True if self.user.subscription != None else False

    def token_refresh(self):
        data = {
            'client_id': pyaes.AESModeOfOperationCTR(self._config.token_secret).decrypt(base64.b64decode(self._config.client_id)).decode('utf-8') if self._config.client_name else self._config.client_id,
            'refresh_token': self._config.refresh_token,
            'grant_type': 'refresh_token',
            'scope': REFRESH_SCOPE
        }
        if self._config.client_secret:
            data['client_secret'] = pyaes.AESModeOfOperationCTR(self._config.token_secret).decrypt(base64.b64decode(self._config.client_secret)).decode('utf-8') if self._config.client_name else self._config.client_secret
        log.debug('Requesting new Access Token...')
        r = requests.post(urljoin(OAUTH_BASE_URL, 'token'), data=data)
        if self._config.debug_json:
            r = self.check_response(r, raiseOnError=False)
        try:
            token = self._parse_auth_token(r.json())
            if token.success:
                self._config.user_id = token.user_id
                self._config.token_type = token.token_type
                self._config.access_token = token.access_token
                self._config.expires_in = token.expires_in
                self._config.refresh_time = token.login_time
                self._config.expire_time = token.expire_time
                log.info('New Access Token expires at %s' % token.expire_time)
        except:
            token = AuthToken(status=500, error='Unknown error', error_description='No Json data in respose')
        return token

    def token_expired(self, r=None):
        if isinstance(r, requests.Response):
            try:
                json_obj = r.json()
                if not r.ok and json_obj.get('status', 0) == 401 and json_obj.get('subStatus', 0) == 11003:
                    log.info('Access Token expired at %s. Getting new one ...' % self._config.expire_time)
                    return True
            except:
                pass
            return False
        if datetime.datetime.now() > self._config.expire_time:
            log.info('Access Token in addon settings expired at %s. Getting new one ...' % self._config.expire_time)
            return True
        return False

    def logout(self, signoff=False):
        if signoff:
            try:
                self.request(method='POST', path='logout')
            except:
                pass
        self._config.init()
        self.user = None

    def request(self, method, url=URL_API_V1, path=None, params=None, data=None, headers=None, authenticate=True):
        if self.is_logged_in and self.token_expired():
            self.token_refresh()
        request_headers = {}
        request_params = {}
        if (url.startswith(URL_API_V1) or url.startswith(URL_API_V2)) and not 'countryCode' in request_params:
            request_params['countryCode'] = self._config.country_code
        if headers:
            request_headers.update(headers)
        if params:
            request_params.update(params)
        if request_params.get('offset', 1) == 0:
            request_params.pop('offset', 1) # Remove Zero Offset from Params
        url = urljoin(url, path)
        if self.is_logged_in and not 'token' in request_params:
            if authenticate:
                request_headers.update({'Authorization': '{} {}'.format(self._config.token_type, self._config.access_token)})
        else:
            # Request with Preview-Token. Remove SessionId if given via headers parameter
            # request_headers.pop('X-Tidal-SessionId', None)
            request_params.update({'token': self._config.preview_token})
        r = requests.request(method, url, params=request_params, data=data, headers=request_headers)
        if self.token_expired(r):
            self.token_refresh()
            request_headers.update({'Authorization': '{} {}'.format(self._config.token_type, self._config.access_token)})
            r = requests.request(method, url, params=request_params, data=data, headers=request_headers)
        return self.check_response(r)

    def check_response(self, r, raiseOnError=True, debugJson=True):
        log.info('%s %s' % (r.request.method, r.request.url))
        if not r.ok:
            try:
                msg = r.json()
                errtab = [repr(r)]
                if 'userMessage' in msg:
                    errtab.append(msg['userMessage'])
                if 'error_description' in msg:
                    errtab.append(msg['error_description'])
                log.error('\n'.join(errtab))
            except:
                log.error(repr(r))
        if raiseOnError:
            r.raise_for_status()
        if self._config.debug_json and debugJson:
            try:
                log.info(repr(r))
                log.info('response: %s' % json.dumps(r.json(), indent=4))
            except:
                try:
                    log.info('response: %s' % r.content)
                except:
                    pass
        return r

    def get_playlist(self, playlist_id):
        return self._map_request('playlists/%s' % playlist_id, ret='playlist')

    def get_playlist_tracks(self, playlist_id, offset=0, limit=9999):
        # keeping 1st parameter as playlist_id for backward compatibility 
        if isinstance(playlist_id, Playlist):
            playlist_id = playlist_id.id
        items = self._map_request('playlists/%s/tracks' % playlist_id, params={'offset': offset, 'limit': limit}, ret='tracks')
        track_no = offset
        for item in items:
            item._playlist_id = playlist_id
            item._playlist_pos = track_no
            track_no += 1
        return items

    def get_playlist_items(self, playlist, offset=0, limit=9999, ret='playlistitems'):
        if not isinstance(playlist, Playlist):
            playlist = self.get_playlist(playlist)
        # Don't read empty playlists
        if not playlist or playlist.numberOfItems == 0:
            return []
        itemCount = playlist.numberOfItems - offset
        remaining = min(itemCount, limit)
        result = []
        # Number of Items is limited to 100, so read multiple times if more than 100 entries are requested
        while remaining > 0:
            nextLimit = min(100, remaining)
            items = self._map_request('playlists/%s/items' % playlist.id, params={'offset': offset, 'limit': nextLimit}, ret='playlistitems')
            if items:
                track_no = offset
                for item in items:
                    item._playlist_id = playlist.id
                    item._playlist_pos = track_no
                    item._etag = playlist._etag
                    item._playlist_name = playlist.title
                    item._playlist_type = playlist.type
                    item._pageSize = limit
                    track_no += 1
                remaining -= len(items)
                result += items
            else:
                remaining = 0
            offset += 100
        if ret.startswith('track'):
            # Return tracks only
            result = [item for item in result if isinstance(item, Track)]
        elif ret.startswith('video'):
            # Return videos only
            result = [item for item in result if isinstance(item, Video)]
        return result

    def get_album(self, album_id):
        return self._map_request('albums/%s' % album_id, ret='album')

    def get_album_tracks(self, album_id):
        return self._map_request('albums/%s/tracks' % album_id, ret='tracks')

    def get_album_items(self, album_id, ret='playlistitems'):
        offset = 0
        remaining = 9999
        result = []
        # Number of Items is limited to 100, so read multiple times if more than 100 entries are requested
        while remaining > 0:
            items = self._map_request('albums/%s/items' % album_id, params={'offset': offset, 'limit': 100}, ret='playlistitems')
            if items:
                if remaining == 9999:
                    remaining = items[0]._totalNumberOfItems
                remaining -= len(items)
                result += items
            else:
                remaining = 0
            offset += 100
        if ret.startswith('track'):
            # Return tracks only
            result = [item for item in result if isinstance(item, Track)]
        elif ret.startswith('video'):
            # Return videos only
            result = [item for item in result if isinstance(item, Video)]
        return result

    def get_artist(self, artist_id):
        return self._map_request('artists/%s' % artist_id, ret='artist')

    def get_artist_albums(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/albums' % artist_id, params={'offset': offset, 'limit': limit}, ret='albums')

    def get_artist_albums_ep_singles(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/albums' % artist_id, params={'filter': 'EPSANDSINGLES', 'offset': offset, 'limit': limit}, ret='albums')

    def get_artist_albums_other(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/albums' % artist_id, params={'filter': 'COMPILATIONS', 'offset': offset, 'limit': limit}, ret='albums')

    def get_artist_top_tracks(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/toptracks' % artist_id, params={'offset': offset, 'limit': limit}, ret='tracks')

    def get_artist_videos(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/videos' % artist_id, params={'offset': offset, 'limit': limit}, ret='videos')

    def _cleanup_text(self, text):
        clean_text = re.sub("\[.*?\]", '', text)            # Remove Tags: [wimpLink ...] [/wimpLink]
        clean_text = re.sub(r"<br.>", '\n\n', clean_text)   # Replace Tags: <br/> with NewLine
        return clean_text

    def get_artist_bio(self, artist_id):
        bio = self.request('GET', path='artists/%s/bio' % artist_id, params={'includeImageLinks': 'false'}).json()
        return self._cleanup_text(bio.get('text', ''))

    def get_artist_info(self, artist_id):
        bio = self.request('GET', path='artists/%s/bio' % artist_id, params={'includeImageLinks': 'false'}).json()
        if bio.get('summary', None):
            bio.update({'summary': self._cleanup_text(bio.get('summary', ''))})
        if bio.get('text', None):
            bio.update({'text': self._cleanup_text(bio.get('text', ''))})
        return bio

    def get_artist_similar(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/similar' % artist_id, params={'offset': offset, 'limit': limit}, ret='artists')

    def get_artist_radio(self, artist_id, offset=0, limit=999):
        return self._map_request('artists/%s/radio' % artist_id, params={'offset': offset, 'limit': limit}, ret='tracks')

    def get_artist_playlists(self, artist_id):
        return self._map_request('artists/%s/playlistscreatedby' % artist_id, ret='playlists')

    def get_featured(self, group=None, types=['PLAYLIST'], limit=999):
        params = {'limit': limit,
                  'clientType': 'BROWSER',
                  'subscriptionType': SubscriptionType.premium_mid}
        if group:
            params.update({'group': group})      # RISING | DISCOVERY | NEWS
        items = self.request('GET', path='promotions', params=params).json()['items']
        return [self._parse_promotion(item) for item in items if item['type'] in types]

    def get_category_items(self, group):
        items = list(map(self._parse_category, self.request('GET', path=group).json()))
        for item in items:
            item._group = group
        return items

    def get_category_content(self, group, path, content_type, offset=0, limit=999):
        return self._map_request('/'.join([group, path, content_type]), params={'offset': offset, 'limit': limit}, ret=content_type)

    def get_featured_items(self, content_type, group, path='featured', offset=0, limit=999):
        return self.get_category_content(path, group, content_type, offset, limit)

    def get_moods(self):
        return self.get_category_items('moods')

    def get_mood_playlists(self, mood_id):
        return self.get_category_content('moods', mood_id, 'playlists')

    def get_genres(self):
        return self.get_category_items('genres')

    def get_genre_items(self, genre_id, content_type):
        return self.get_category_content('genres', genre_id, content_type)

    def get_movies(self):
        items = self.get_category_items('movies')
        movies = []
        for item in items:
            movies += self.get_category_content('movies', item.path, 'videos')
        return movies

    def get_shows(self):
        items = self.get_category_items('shows')
        shows = []
        for item in items:
            shows += self.get_category_content('shows', item.path, 'playlists')
        return shows

    def get_track_radio(self, track_id, offset=0, limit=999):
        return self._map_request('tracks/%s/radio' % track_id, params={'offset': offset, 'limit': limit}, ret='tracks')

    def get_track(self, track_id, withAlbum=False):
        item = self._map_request('tracks/%s' % track_id, ret='track')
        if item.album and withAlbum:
            album = self.get_album(item.album.id)
            if album:
                item.album = album
        return item

    def get_mix(self, mix_id):
        params = { 'mixId': mix_id, 'locale': self._config.locale, 'deviceType': 'BROWSER' }
        r = self.request('GET', path='pages/mix', params=params)
        if r.ok:
            json_obj = r.json()
            for row in json_obj['rows']:
                for module in row['modules']:
                    try:
                        item_type = module['type']
                        if item_type == 'MIX_HEADER' and 'mix' in module:
                            item = self._parse_mix(module['mix'])
                            return item
                    except:
                        pass
        return None

    def get_lyrics(self, track_id):
        try:
            return self._map_request('tracks/%s/lyrics' % track_id, params={'countryCode': self._config.user_country_code}, ret='lyrics')
        except:
            return None

    def get_video(self, video_id):
        return self._map_request('videos/%s' % video_id, ret='video')

    def get_recommended_items(self, content_type, item_id, offset=0, limit=999):
        return self._map_request('%s/%s/recommendations' % (content_type, item_id), params={'offset': offset, 'limit': limit}, ret=content_type)

    def get_feed_items(self):
        try:
            items = []
            json = self._map_request(path='feed/activities', url=URL_API_V2, params={'userId': self._config.user_id, 'locale': self._config.locale, 'deviceType': 'BROWSER'}, ret='json')
            for jitem in json['activities']:
                jalbum = jitem.get('followableActivity', {}).get('album', {})
                if jalbum:
                    items.append(self._parse_album(jalbum))
                jmix = jitem.get('followableActivity', {}).get('historyMix', {})
                if jmix:
                    items.append(self._parse_mix(jmix))
        except:
            pass
        return items

    def _map_request(self, path, url=URL_API_V1, method='GET', params=None, data=None, headers=None, authenticate=True, ret=None):
        r = self.request(method, url=url, path=path, params=params, data=data, headers=headers, authenticate=authenticate)
        if not r.ok:
            return [] if ret.endswith('s') else None
        json_obj = r.json()
        if ret == 'json':
            return json_obj
        if 'items' in json_obj:
            items = json_obj.get('items')
            result = []
            offset = 0
            if params and 'offset' in params:
                offset = params.get('offset')
            itemPosition = offset
            if self._cursor:
                itemPosition = itemPosition + self._cursor_pos
            else:
                self._cursor_pos = 0
            try:
                self._cursor = json_obj.get('cursor', '')
                numberOfItems = int('0%s' % json_obj.get('totalNumberOfItems')) if 'totalNumberOfItems' in json_obj else 9999
            except:
                numberOfItems = 9999
            log.info('NumberOfItems=%s, %s items in list' % (numberOfItems, len(items)))
            for item in items:
                retType = ret
                if 'type' in item and ret.startswith('playlistitem'):
                    retType = item['type']
                if 'data' in item and URL_API_V2 in url:
                    parent = item.get('parent', {})
                    item = item['data']
                    if not 'parent' in item:
                        item['parent'] = parent if isinstance(parent, dict) else {}
                    retType = item.get('itemType', retType).lower()
                elif 'item' in item:
                    item = item['item']
                elif 'track' in item and ret.startswith('track'):
                    item = item['track']
                elif 'video' in item and ret.startswith('video'):
                    item = item['video']
                nextItem = self._parse_one_item(item, retType)
                if isinstance(nextItem, BrowsableMedia):
                    nextItem._itemPosition = itemPosition
                    nextItem._offset = offset
                    if params and 'limit' in params:
                        nextItem._pageSize = params['limit']
                    nextItem._totalNumberOfItems = numberOfItems
                result.append(nextItem)
                itemPosition = itemPosition + 1
                self._cursor_pos = self._cursor_pos + 1
        else:
            if 'data' in json_obj and URL_API_V2 in url:
                parent = json_obj.get('parent', {})
                json_obj = json_obj['data']
                if not 'parent' in json_obj:
                    json_obj['parent'] = parent if isinstance(parent, dict) else {}
                retType = json_obj.get('itemType', ret).lower()
            result = self._parse_one_item(json_obj, ret)
            if isinstance(result, Playlist) and result.isUserPlaylist:
                # Get ETag of Playlist which must be used to add/remove entries of playlists
                try: 
                    result._etag = r.headers._store['etag'][1]
                except:
                    result._etag = None
                    if URL_API_V1 in url:
                        # ETag is only for API V1
                        log.error('No ETag in response header for playlist "%s" (%s)' % (json_obj.get('title'), json_obj.get('id')))
        return result

    def _map_request_v2(self, path, url=URL_API_V2, params=None, data=None, headers=None, authenticate=True, ret=None):
        self._cursor = ''
        self._cursor_pos = 0
        firstRun = True
        items = []
        while self._cursor or firstRun:
            firstRun = False
            items = items + self._map_request(path=path, url=url, params=params, data=data, headers=headers, authenticate=authenticate, ret=ret)
            params['cursor'] = self._cursor
        self._cursor = ''
        self._cursor_pos = 0
        # Build item numbers because all line are loaded everytime
        offset = 0
        for item in items:
            item._totalNumberOfItems = len(items)
            item._itemPosition = offset
            item._offset = offset
            offset = offset + 1
        return items

    def get_streaming_session_id(self, forceNew=False):
        if forceNew or not self.streamingSessionId:
            self._streamingSessionId = uuid.uuid4()
        return self._streamingSessionId

    def get_track_url(self, track_id, quality=None):
        params = {}
        if not self.is_logged_in:
            url = 'tracks/%s/previewurl' % track_id
        else:
            url = 'tracks/%s/playbackinfopostpaywall' % track_id
            params = { 'audioquality': quality if quality else self._config.quality,
                       'playbackmode': 'STREAM',
                       'assetpresentation': 'FULL',
                       'deviceType': 'TABLET',
                       'locale': self._config.locale,
                       'countryCode': self._config.user_country_code,
                       'streamingsessionid':  self.get_streaming_session_id(forceNew=True) }
        return self._map_request(url,  params=params, ret='track_url')

    def get_video_url(self, video_id, audioOnly=False, preview=False):
        params = {}
        ret_type = 'video_url'
        if not self.is_logged_in or preview:
            url = 'videos/%s/previewurl' % video_id
            params['token'] = self._config.preview_token
        else:
            url = 'videos/%s/playbackinfopostpaywall' % video_id
            params = { 'videoquality': 'AUDIO_ONLY' if audioOnly else 'HIGH',
                       'playbackmode': 'STREAM',
                       'assetpresentation': 'FULL',
                       'countryCode': self._config.user_country_code }
            if audioOnly:
                ret_type = 'track_url'
        return self._map_request(url,  params=params, ret=ret_type)

    def search(self, field, value, limit=50):
        search_field = field
        if isinstance(search_field, string_types) and search_field.upper() == 'ALL':
            search_field = ALL_SAERCH_FIELDS
        params = {
            'query': value,
            'limit': limit,
        }
        if isinstance(search_field, string_types):
            what = search_field.upper()
            params.update({'types': what if what == 'ALL' or what.endswith('S') else what + 'S'})
        elif isinstance(search_field, Iterable):
            params.update({'types': ','.join(search_field)})
        return self._map_request('search', params=params, ret='search')

#------------------------------------------------------------------------------
# Parse JSON Data into Media-Item-Objects
#------------------------------------------------------------------------------

    def _parse_one_item(self, json_obj, ret=None):
        parse = None
        ret = ret.lower()
        if ret.startswith('user'):
            parse = self._parse_user
        elif ret.startswith('refresh_token'):
            parse = self._parse_refresh_token
        elif ret.startswith('subscription'):
            parse = self._parse_subscription
        elif ret.startswith('artist'):
            parse = self._parse_artist
        elif ret.startswith('album'):
            parse = self._parse_album
        elif ret.startswith('track_url'):
            parse = self._parse_track_url
        elif ret.startswith('track'):
            parse = self._parse_track
        elif ret.startswith('video_url'):
            parse = self._parse_video_url
        elif ret.startswith('video'):
            parse = self._parse_video
        elif ret.startswith('folder'):
            parse = self._parse_folder
        elif ret.startswith('playlist'):
            parse = self._parse_playlist
        elif ret.startswith('category'):
            parse = self._parse_category
        elif ret.startswith('search'):
            parse = self._parse_search
        elif ret.startswith('mix'):
            parse = self._parse_mix
        elif ret.startswith('lyrics'):
            parse = self._parse_lyrics
        elif ret.startswith('device_code'):
            parse = self._parse_device_code
        elif ret.startswith('auth_token'):
            parse = self._parse_auth_token
        else:
            raise NotImplementedError()
        oneItem = parse(json_obj)
        return oneItem

    def _parse_user(self, json_obj):
        return UserInfo(**json_obj)

    def _parse_subscription(self, json_obj):
        return Subscription(**json_obj)

    def _parse_artist(self, json_obj):
        artist = Artist(**json_obj)
        if self.is_logged_in and self.user.favorites:
            artist._isFavorite = self.user.favorites.isFavoriteArtist(artist.id)
        return artist

    def _parse_all_artists(self, artist_id, json_obj):
        allArtists = []
        ftArtists = []
        for item in json_obj:
            nextArtist = self._parse_artist(item)
            allArtists.append(nextArtist)
            if nextArtist.id != artist_id:
                ftArtists.append(nextArtist)
        return (allArtists, ftArtists)

    def _parse_album(self, json_obj, artist=None):
        album = Album(**json_obj)
        if artist:
            album.artist = artist
        elif 'artist' in json_obj:
            album.artist = self._parse_artist(json_obj['artist'])
        elif 'artists' in json_obj:
            album.artist = self._parse_artist(json_obj['artists'][0])
        if 'artists' in json_obj:
            album.artists, album._ftArtists = self._parse_all_artists(album.artist.id, json_obj['artists'])
        else:
            album.artists = [album.artist]
            album._ftArtists = []
        if self.is_logged_in and self.user.favorites:
            album._isFavorite = self.user.favorites.isFavoriteAlbum(album.id)
        return album

    def _parse_folder(self, json_obj):
        return Folder(**json_obj)

    def _parse_playlist(self, json_obj):
        playlist = Playlist(**json_obj)
        if self.is_logged_in and self.user.favorites:
            playlist._isFavorite = self.user.favorites.isFavoritePlaylist(playlist.id)
        if self.is_logged_in and playlist.isUserPlaylist and playlist.creatorId != None and '%s' % playlist.creatorId != '%s' % self._config.user_id:
            playlist.type = 'OTHER_USER' # This is a User Playlist from a different user
        return playlist

    def _parse_promotion(self, json_obj):
        item = Promotion(**json_obj)
        if self.is_logged_in and self.user.favorites:
            if item.type == 'ALBUM':
                item._isFavorite = self.user.favorites.isFavoriteAlbum(item.id)
            elif item.type == 'PLAYLIST':
                item._isFavorite = self.user.favorites.isFavoritePlaylist(item.id)
            elif item.type == 'VIDEO':
                item._isFavorite = self.user.favorites.isFavoriteVideo(item.id)
        return item

    def _parse_track_url(self, json_obj):
        return TrackUrl(**json_obj)

    def _parse_track(self, json_obj):
        track = Track(**json_obj)
        if 'artist' in json_obj:
            track.artist = self._parse_artist(json_obj['artist'])
        elif 'artists' in json_obj:
            track.artist = self._parse_artist(json_obj['artists'][0])
        if 'artists' in json_obj:
            track.artists, track._ftArtists = self._parse_all_artists(track.artist.id, json_obj['artists'])
        else:
            track.artists = [track.artist]
            track._ftArtists = []
        track.album = self._parse_album(json_obj['album'], artist=track.artist)
        if self.is_logged_in and self.user.favorites:
            track._isFavorite = self.user.favorites.isFavoriteTrack(track.id)
        return track

    def _parse_video_url(self, json_obj):
        return VideoUrl(**json_obj)

    def _parse_video(self, json_obj):
        video = Video(**json_obj)
        if 'artist' in json_obj:
            video.artist = self._parse_artist(json_obj['artist'])
        elif 'artists' in json_obj:
            video.artist = self._parse_artist(json_obj['artists'][0])
        if 'artists' in json_obj:
            video.artists, video._ftArtists = self._parse_all_artists(video.artist.id, json_obj['artists'])
            if not 'artist' in json_obj and len(video.artists) > 0:
                video.artist = video.artists[0]
        else:
            video.artists = [video.artist]
            video._ftArtists = []
        if 'album' in json_obj and json_obj['album']:
            video.album = self._parse_album(json_obj['album'], artist=video.artist)
        if self.is_logged_in and self.user.favorites:
            video._isFavorite = self.user.favorites.isFavoriteVideo(video.id)
        return video

    def _parse_category(self, json_obj):
        return Category(**json_obj)

    def _parse_search(self, json_obj):
        result = SearchResult()
        if 'artists' in json_obj:
            result.artists = [self._parse_artist(json) for json in json_obj['artists']['items']]
        if 'albums' in json_obj:
            result.albums = [self._parse_album(json) for json in json_obj['albums']['items']]
        if 'tracks' in json_obj:
            result.tracks = [self._parse_track(json) for json in json_obj['tracks']['items']]
        if 'playlists' in json_obj:
            result.playlists = [self._parse_playlist(json) for json in json_obj['playlists']['items']]
        if 'videos' in json_obj:
            result.videos = [self._parse_video(json) for json in json_obj['videos']['items']]
        return result

    def _parse_mix(self, json_obj):
        item = Mix(**json_obj)
        if self.is_logged_in and self.user.favorites:
            item._isFavorite = self.user.favorites.isFavoriteMix(item.id)
        return item

    def _parse_lyrics(self, json_obj):
        return Lyrics(**json_obj)

    def _parse_device_code(self, json_obj):
        return DeviceCode(**json_obj)

    def _parse_auth_token(self, json_obj):
        return AuthToken(**json_obj)


#------------------------------------------------------------------------------
# Class to work with user favorites
#------------------------------------------------------------------------------

class Favorites(object):

    def __init__(self, session):
        self.ids = {}
        self._session = session
        self._base_url = 'users/%s/favorites' % session._config.user_id
        self.reset()

    def reset(self):
        self.ids_loaded = False
        self.ids_modified = False
        self.ids = {'artists': [], 'albums': [], 'playlists': [], 'tracks': [], 'videos': [], 'mixes': []}

    def add_buffered_ids(self, content_type, item_ids):
        ids = item_ids if isinstance(item_ids, list) else [item_ids]
        for _id in ids:
            _id = _id.id if isinstance(_id, BrowsableMedia) else _id
            try:
                if not '%s' % _id in self.ids[content_type]:
                    self.ids[content_type].append('%s' % _id)
                    self.ids_modified = True
            except:
                pass
        return self.ids_modified

    def remove_buffered_ids(self, content_type, item_ids):
        ids = item_ids if isinstance(item_ids, list) else [item_ids]
        for _id in ids:
            _id = _id.id if isinstance(_id, BrowsableMedia) else _id
            try:
                if '%s' % _id in self.ids[content_type]:
                    self.ids[content_type].remove('%s' % _id)
                    self.ids_modified = True
            except:
                pass
        return self.ids_modified

    def load_all(self, force_reload=False):
        if force_reload or not self.ids_loaded:
            # Reset all first
            self.reset()
            r = self._session.request('GET', path=self._base_url + '/ids')
            if r.ok:
                json_obj = r.json()
                if 'ARTIST' in json_obj:
                    self.ids['artists'] = json_obj.get('ARTIST')
                if 'ALBUM' in json_obj:
                    self.ids['albums'] = json_obj.get('ALBUM')
                if 'PLAYLIST' in json_obj:
                    self.ids['playlists'] = json_obj.get('PLAYLIST')
                if 'TRACK' in json_obj:
                    self.ids['tracks'] = json_obj.get('TRACK')
                if 'VIDEO' in json_obj:
                    self.ids['videos'] = json_obj.get('VIDEO')
                try:
                    mix_ids = self._session._map_request(path='favorites/mixes/ids', url=URL_API_V2, params={'limit': 500}, ret='json')
                    if mix_ids:
                        self.ids['mixes'] = mix_ids.get('content')
                except:
                    pass
                self.ids_loaded = True
        return self.ids_loaded

    def get(self, content_type, offset=0, limit=9999):
        content_type = content_type.lower()
        if content_type == 'playlists':
            params = {'folderId': 'root', 'offset': 0, 'limit': 50, 'order': 'NAME', 'includeOnly': 'FAVORITE_PLAYLIST'}
            path = 'my-collection/playlists/folders/flattened'
            items = self._session._map_request_v2(path=path, url=URL_API_V2, params=params, ret='folders')
        elif content_type == 'mixes':
            params = {'offset': 0, 'limit': 50, 'order': 'NAME', 'locale': self._session._config.locale, 'orderDirection': 'ASC', 'deviceType': 'BROWSER'}
            path = 'favorites/mixes'
            items = self._session._map_request_v2(path=path, url=URL_API_V2, params=params, ret='mix')
        else:
            items = self._session._map_request(self._base_url + '/' + content_type, 
                                               params={'offset': offset, 'limit': limit if content_type != 'videos' else min(limit, 100), 'order': 'NAME'}, 
                                               ret=content_type)
        self.add_buffered_ids(content_type, items)
        return items

    def add(self, content_type, item_ids):
        if isinstance(item_ids, string_types):
            ids = [item_ids]
        else:
            ids = item_ids
        param = {'artists': 'artistId', 'albums': 'albumId', 'playlists': 'uuid', 
                 'tracks': 'trackIds', 'videos': 'videoIds', 'mixes': 'mixIds'}.get(content_type)
        if content_type == 'mixes':
            ok = self._session.request('PUT', path='favorites/mixes/add', url=URL_API_V2, data={param: ','.join(ids), 'onArtifactNotFound': 'FAIL'}).ok
        else:
            ok = self._session.request('POST', path=self._base_url + '/%s' % content_type, data={param: ','.join(ids)}).ok
        if ok:
            self.add_buffered_ids(content_type, ids)
        return ok

    def remove(self, content_type, item_id):
        if content_type == 'mixes':
            ok = self._session.request('PUT', path='favorites/mixes/remove', url=URL_API_V2, data={'mixIds': item_id}).ok
        else:
            ok = self._session.request('DELETE', path=self._base_url + '/%s/%s' % (content_type, item_id)).ok
        if ok:
            self.remove_buffered_ids(content_type, item_id)
        return ok

    def add_artist(self, artist_id):
        return self.add('artists', artist_id)

    def remove_artist(self, artist_id):
        return self.remove('artists', artist_id)

    def add_album(self, album_id):
        return self.add('albums', album_id)

    def remove_album(self, album_id):
        return self.remove('albums', album_id)

    def add_playlist(self, playlist_id):
        return self.add('playlists', playlist_id)

    def remove_playlist(self, playlist_id):
        return self.remove('playlists', playlist_id)

    def add_track(self, track_id):
        return self.add('tracks', track_id)

    def remove_track(self, track_id):
        return self.remove('tracks', track_id)

    def add_video(self, video_id):
        return self.add('videos', video_id)

    def remove_video(self, video_id):
        return self.remove('videos', video_id)

    def add_mix(self, mix_id):
        return self.add('mixes', mix_id)

    def remove_mix(self, mix_id):
        return self.remove('mixes', mix_id)

    def artists(self):
        return self.get('artists')

    def isFavoriteArtist(self, artist_id):
        self.load_all()
        return '%s' % artist_id in self.ids.get('artists', [])

    def albums(self):
        return self.get('albums')

    def isFavoriteAlbum(self, album_id):
        self.load_all()
        return '%s' % album_id in self.ids.get('albums', [])

    def playlists(self):
        return self.get('playlists')

    def isFavoritePlaylist(self, playlist_id):
        self.load_all()
        return '%s' % playlist_id in self.ids.get('playlists', [])

    def tracks(self):
        return self.get('tracks')

    def isFavoriteTrack(self, track_id):
        self.load_all()
        return '%s' % track_id in self.ids.get('tracks', [])

    def videos(self):
        return self.get('videos', limit=100)

    def isFavoriteVideo(self, video_id):
        self.load_all()
        return '%s' % video_id in self.ids.get('videos', [])

    def mixes(self):
        return self.get('mixes')

    def isFavoriteMix(self, mix_id):
        self.load_all()
        return '%s' % mix_id in self.ids.get('mixes', [])

#------------------------------------------------------------------------------
# Class to work with users playlists
#------------------------------------------------------------------------------

class User(object):

    favorites = None

    def __init__(self, session, favorites=None):
        self._session = session
        self._base_url = 'users/%s' % session._config.user_id
        self._url_v2 = urljoin(URL_API_V2, 'my-collection/')
        self.favorites = favorites if favorites else Favorites(session)

    def info(self):
        return self._session._map_request(path=self._base_url, ret='user')

    def subscription(self):
        return self._session._map_request(path=self._base_url + '/subscription', ret='subscription')

    def playlists(self, flattened=True, allPlaylists=False):
        params = {'folderId': 'root', 'offset': 0, 'limit': 50, 'order': 'NAME', 'includeOnly': 'PLAYLIST' if allPlaylists else 'USER_PLAYLIST'}
        path = 'my-collection/playlists/folders'
        if flattened:
            path = path + '/flattened'
        return self._session._map_request_v2(path=path, url=URL_API_V2, params=params, ret='folders')

    def create_playlist(self, title, description='', folder_id='root'):
        return self._session._map_request(path='playlists/folders/create-playlist', url=self._url_v2, method='PUT', params={'name': title, 'description': description, 'folderId': folder_id}, ret='playlist')

    def delete_playlist(self, playlist_id):
        if isinstance(playlist_id, Playlist):
            playlist_id = playlist_id.id
        return self._session.request('DELETE', path='playlists/%s' % playlist_id).ok

    def rename_playlist(self, playlist, title, description=''):
        if not isinstance(playlist, Playlist):
            playlist = self._session.get_playlist(playlist)
        elif not playlist._etag:
            # Re-Read Playlist to get ETag
            playlist = self._session.get_playlist(playlist.id)
        ok = False
        if playlist and playlist._etag:
            headers = {'if-none-match': '%s' % playlist._etag}
            data = {'title': title, 'description': description}
            ok = self._session.request('POST', path='playlists/%s' % playlist.id, data=data, headers=headers).ok
        else:
            log.warning('Got no ETag for playlist %s' & playlist.title)
        return playlist if ok else None

    def add_playlist_entries(self, playlist, item_ids=[]):
        if not isinstance(playlist, Playlist):
            playlist = self._session.get_playlist(playlist)
        elif not playlist._etag:
            # Re-Read Playlist to get ETag
            playlist = self._session.get_playlist(playlist.id)
        trackIds = ','.join(item_ids)
        ok = False
        if playlist and playlist._etag:
            headers = {'if-none-match': '%s' % playlist._etag}
            data = {'trackIds': trackIds}  # , 'toIndex': playlist.numberOfItems}
            ok = self._session.request('POST', path='playlists/%s/items' % playlist.id, data=data, headers=headers).ok
        else:
            log.warning('Got no ETag for playlist %s' & playlist.title)
        return playlist if ok else None

    def remove_playlist_entry(self, playlist, entry_no=None, item_id=None):
        if not isinstance(playlist, Playlist):
            playlist = self._session.get_playlist(playlist)
        elif not playlist._etag:
            # Re-Read Playlist to get ETag
            playlist = self._session.get_playlist(playlist.id)
        if item_id:
            # Got Track/Video-ID to remove from Playlist
            entry_no = None
            items = self._session.get_playlist_items(playlist)
            for item in items:
                if str(item.id) == str(item_id):
                    entry_no = item._playlist_pos
            if entry_no == None:
                return False
        ok = False
        if playlist and playlist._etag:
            headers = {'if-none-match': '%s' % playlist._etag}
            ok = self._session.request('DELETE', path='playlists/%s/items/%s' % (playlist.id, entry_no), headers=headers).ok
        return playlist if ok else None

    def remove_all_playlist_entries(self, playlist):
        if not isinstance(playlist, Playlist):
            playlist = self._session.get_playlist(playlist)
        elif not playlist._etag:
            # Re-Read Playlist to get ETag
            playlist = self._session.get_playlist(playlist.id)
        if playlist.numberOfItems < 1:
            return True
        entries = []
        i = 0
        while i < playlist.numberOfItems:
            entries.append('%s' % i)
            i = i + 1
        return self.remove_playlist_entry(playlist, entry_no=','.join(entries))

    def folders(self):
        params = {'folderId': 'root', 'offset': 0, 'limit': 50, 'order': 'NAME', 'includeOnly': 'FOLDER'}
        items = self._session._map_request_v2(path='my-collection/playlists/folders', url=URL_API_V2, params=params, ret='folders')
        return items

    def folder(self, folder_id):
        items = self.folders()
        for item in items:
            if item.id == folder_id: return item
        return None

    def folder_items(self, folder_id):
        params = {'folderId': folder_id, 'offset': 0, 'limit': 50, 'order': 'NAME', 'includeOnly': 'PLAYLIST'}
        items = self._session._map_request_v2(path='my-collection/playlists/folders', url=URL_API_V2, params=params, ret='folders')
        return items

    def create_folder(self, name, parent_id='root'):
        return self._session._map_request(url=self._url_v2, path='playlists/folders/create-folder', method='PUT', params={'folderId': parent_id, 'name': name, 'trns': ''}, ret='folder')

    def remove_folder(self, trns):
        # trns can be a folder or playlist trn or a comma separated list of trns
        return self._session.request('PUT', url=self._url_v2, path='playlists/folders/remove', params={'trns': trns}).ok

    def rename_folder(self, folder_trn, name):
        return self._session.request('PUT', url=self._url_v2, path='playlists/folders/rename', params={'trn': folder_trn, 'name': name}).ok

    def add_folder_entry(self, folder, playlist):
        if not isinstance(playlist, Playlist):
            playlist = self._session.get_playlist(playlist)
        folderId = folder.id if isinstance(folder, Folder) else folder
        ok = False
        if playlist.isUserPlaylist or self.favorites.isFavoritePlaylist(playlist.id):
            params = {'folderId': folderId, 'trns': playlist.trn}
            ok = self._session.request('PUT', path='playlists/folders/move', url=self._url_v2, params=params).ok
        else:
            params = {"folderId": folderId, "uuids": playlist.uuid}
            ok = self._session.request('PUT', path='playlists/folders/add-favorites', url=self._url_v2, params=params).ok
        return ok

    def move_folder_entries(self, trns, folder='root'):
        folderId = folder.id if isinstance(folder, Folder) else folder
        params = {'folderId': folderId, 'trns': ','.join([trns] if not isinstance(trns, list) else trns)}
        return self._session.request('PUT', path='playlists/folders/move', url=self._url_v2, params=params).ok

# End of File