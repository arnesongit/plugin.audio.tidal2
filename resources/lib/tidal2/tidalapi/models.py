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
import locale
import re
import datetime
import json
import base64

PY2 = sys.version_info[0] == 2

if PY2:
    string_types = basestring
    from collections import Iterable
else:
    string_types = str
    from collections.abc import Iterable

IMG_URL = 'http://resources.tidal.com/images/{picture}/{size}.jpg'

DEFAULT_ARTIST_IMG = '1e01cdb6-f15d-4d8b-8440-a047976c1cac'
DEFAULT_ALBUM_IMG = '0dfd3368-3aa1-49a3-935f-10ffb39803c0'
DEFAULT_PLAYLIST_IMG = '443331e2-0421-490c-8918-5a4867949589' 
DEFAULT_VIDEO_IMB = 'fa6f0650-76ac-41d1-a4a3-7fe4c89fca90'

VARIOUS_ARTIST_ID = '2935'
TIDAL_ARTIST_ID = '6712922'

CATEGORY_IMAGE_SIZES = {'genres': '460x306', 'moods': '342x342'}

RE_ISO8601 = re.compile(r'^(?P<full>((?P<year>\d{4})([/-]?(?P<month>(0[1-9])|(1[012]))([/-]?(?P<day>(0[1-9])|([12]\d)|(3[01])))?)?(?:[\sT](?P<hour>([01][0-9])|(?:2[0123]))(\:?(?P<minute>[0-5][0-9])(\:?(?P<second>[0-5][0-9])(?P<ms>([\,\.]\d{1,10})?))?)?(?:Z|([\-+](?:([01][0-9])|(?:2[0123]))(\:?(?:[0-5][0-9]))?))?)?))$')


class Quality(object):
    hi_res = 'HI_RES'
    lossless = 'LOSSLESS'
    high = 'HIGH'
    low = 'LOW'
    trial = 'TRIAL' # 30 Seconds MP3 Stream


class SubscriptionType(object):
    premium = 'PREMIUM'
    hifi = 'HIFI'
    free = 'FREE'


class AudioMode(object):
    stereo = 'STEREO'
    sony_360 = 'SONY_360RA'
    dolby_atmos = 'DOLBY_ATMOS'


class Codec(object):
    MP3 = 'MP3'
    AAC = 'AAC'
    M4A = 'MP4A'
    FLAC = 'FLAC'
    MQA = 'MQA'
    Atmos = 'EAC3'


class ManifestMimeType(object):
    tidal_bts = 'vnd.tidal.bts'
    tidal_emu = 'vnd.tidal.emu'
    apple_mpegurl = 'vnd.apple.mpegurl'
    dash_xml = 'dash+xml'


class MimeType(object):
    audio_mpeg = 'audio/mpeg'
    audio_mp3 = 'audio/mp3'
    audio_m4a = 'audio/m4a'
    audio_flac = 'audio/x-flac'
    audio_eac3 = 'audio/eac3'
    video_mp4 = 'video/mp4'
    video_m3u8 = 'video/mpegurl'
    audio_map = {Codec.MP3: audio_mp3, Codec.AAC: audio_m4a, Codec.M4A: audio_m4a,
                 Codec.FLAC: audio_flac, Codec.MQA: audio_m4a, Codec.Atmos: audio_eac3}
    @staticmethod
    def fromAudioCodec(codec): return MimeType.audio_map.get(codec, MimeType.audio_m4a)


class Config(object):
    def __init__(self, **kwargs):
        self.quality = Quality.lossless
        self.country_code = 'WW'
        self.locale = 'en_US'
        self.preview_token = None
        self.debug_json = False
        self.init(**kwargs)

    def init(self, **kwargs):
        self.user_agent = kwargs.get('user_agent', "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.128 Safari/537.36")
        self.country_code = kwargs.get('country_code', self.country_code)
        self.user_id = kwargs.get('user_id', None)
        self.client_id = kwargs.get('client_id', None)
        self.client_secret = kwargs.get('client_secret', None)
        self.client_unique_key = kwargs.get('client_unique_key', None)
        self.session_id = kwargs.get('session_id', None)
        self.preview_token = kwargs.get('preview_token', self.preview_token)
        self.token_type = kwargs.get('token_type', None)
        self.access_token = kwargs.get('access_token', None)
        self.refresh_token = kwargs.get('refresh_token', None)
        self.login_time = kwargs.get('login_time', datetime.datetime.now())
        self.refresh_time = kwargs.get('refresh_time', datetime.datetime.now())
        self.expires_in = kwargs.get('expires_in', 0)
        self.expire_time = kwargs.get('expire_time', self.refresh_time)
        if not self.expire_time:
            self.expire_time = self.refresh_time + datetime.timedelta(seconds=self.expires_in)
        self.quality = kwargs.get('quality', self.quality)
        self.debug_json = kwargs.get('debug_json', self.debug_json)
        try:
            self.locale = locale.locale_alias.get(self.country_code.lower()).split('.')[0]
        except:
            pass


class AlbumType(object):
    album = 'ALBUM'
    ep = 'EP'
    single = 'SINGLE'


class Model(object):
    id = None
    name = 'Unknown'

    def parse_date(self, datestring, default=None):
        try:
            if isinstance(datestring, datetime.datetime):
                return datestring
            if isinstance(datestring, string_types):
                d = RE_ISO8601.match(datestring).groupdict()
                if d['hour'] and d['minute'] and d['second']:
                    return datetime.datetime(year=int(d['year']), month=int(d['month']), day=int(d['day']), hour=int(d['hour']), minute=int(d['minute']), second=int(d['second']))
                else:
                    return datetime.datetime(year=int(d['year']), month=int(d['month']), day=int(d['day']))
        except:
            pass
        return default


class BrowsableMedia(Model):

    # Internal Properties
    _isFavorite = False
    _itemPosition = -1
    _offset = 0
    _totalNumberOfItems = 0

    @property
    def image(self):
        return None

    @property
    def fanart(self):
        return None


class Album(BrowsableMedia):
    title = 'Unknown'
    artist = None
    artists = []
    duration = -1
    numberOfTracks = 1
    numberOfVideos = 0
    numberOfVolumes = 1
    allowStreaming = True
    streamReady = True
    premiumStreamingOnly = False
    streamStartDate = None
    releaseDate = None
    cover = None
    type = AlbumType.album
    audioQuality = Quality.lossless
    explicit = False
    version = None
    popularity = 0
    audioModes = [AudioMode.stereo]

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Album, self).__init__()
        self.releaseDate = self.parse_date(self.releaseDate)
        self.streamStartDate = self.parse_date(self.streamStartDate)
        self.num_tracks = self.numberOfTracks # For Backward Compatibility
        self.release_date = self.releaseDate  # For Backward Compatibility
        self.name = self.title                # For Backward Compatibility

    @property
    def year(self):
        if self.releaseDate:
            return self.releaseDate.year
        if self.streamStartDate:
            return self.streamStartDate.year
        return None

    @property
    def image(self):
        if self.cover:
            return IMG_URL.format(picture=self.cover.replace('-', '/'), size='640x640')
        return IMG_URL.format(picture=DEFAULT_ALBUM_IMG.replace('-', '/'), size='640x640')

    @property
    def fanart(self):
        if self.artist and isinstance(self.artist, Artist):
            return self.artist.fanart
        if self.cover:
            return IMG_URL.format(picture=self.cover.replace('-', '/'), size='1280x1280')
        return None

    @property
    def isMasterAlbum(self):
        return True if self.audioQuality == Quality.hi_res else False

    @property
    def isDolbyAtmos(self):
        try:
            return True if AudioMode.dolby_atmos in self.audioModes else False
        except:
            return False


class Artist(BrowsableMedia):
    picture = None
    url = None
    popularity = 0
    mix_ids = {}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Artist, self).__init__()
        try:
            self.mix_ids = kwargs['mixes']
        except:
            self.mix_ids = {}

    @property
    def image(self):
        if self.picture:
            return IMG_URL.format(picture=self.picture.replace('-', '/'), size='320x320')
        return IMG_URL.format(picture=DEFAULT_ARTIST_IMG.replace('-', '/'), size='320x320')

    @property
    def fanart(self):
        if self.picture:
            return IMG_URL.format(picture=self.picture.replace('-', '/'), size='1080x720')
        return None


class Mix(BrowsableMedia):
    title = 'Unknown'
    subTitle = ''
    mixType = ''
    dateAdded = None
    updated = None
    _image = None
    _fanart = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Mix, self).__init__()
        self.name = self.title
        self.dateAdded = self.parse_date(self.dateAdded)
        self.updated = self.parse_date(self.updated, default=self.dateAdded)
        try:
            self._image = kwargs['images']['MEDIUM']['url']
        except:
            self._image = IMG_URL.format(picture=DEFAULT_PLAYLIST_IMG.replace('-', '/'), size='320x214')
        try:
            try:
                self._fanart = kwargs['detailImages']['LARGE']['url']
            except:
                self._fanart = kwargs['images']['LARGE']['url']
        except:
            self._image = IMG_URL.format(picture=DEFAULT_PLAYLIST_IMG.replace('-', '/'), size='1080x720')

    @property
    def image(self):
        return self._image

    @property
    def fanart(self):
        return self._fanart


class Folder(BrowsableMedia):
    createdAt = None
    lastModifiedAt = None
    trn = None
    totalNumberOfItems = 0
    parentFolderId = None
    parentFolderName = ''

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Folder, self).__init__()
        self.createdAt = self.parse_date(self.createdAt)
        self.lastModifiedAt = self.parse_date(self.lastModifiedAt, default=self.lastModifiedAt)
        if not self.trn:
            self.trn = 'trn:folder:' + self.id
        try:
            self.parentFolderId = kwargs['parent']['id']
            self.parentFolderName = kwargs['parent']['name']
        except:
            pass

    @property
    def numberOfItems(self):
        return self.totalNumberOfItems

    @property
    def year(self):
        if self.lastModifiedAt:
            return self.lastModifiedAt.year
        elif self.createdAt:
            return self.createdAt.year
        return datetime.datetime.now().year

    @property
    def image(self):
        return IMG_URL.format(picture=DEFAULT_PLAYLIST_IMG.replace('-', '/'), size='320x214')

    @property
    def fanart(self):
        return None


class Playlist(BrowsableMedia):
    description = None
    creator = None
    type = None
    uuid = None
    trn = None
    title = 'Unknown'
    created = None
    creationDate = None
    creatorId = None
    publicPlaylist = None
    lastUpdated = None
    lastItemAddedAt = None
    squareImage = None
    numberOfTracks = 0
    numberOfVideos = 0
    duration = -1
    popularity = 0
    parentFolderId = None
    parentFolderName = ''
    parent = {}

    # Internal Properties
    _image = None  # For Backward Compatibility because "image" is a property method
    _etag = None   # ETag from HTTP Response Header for Playlist Operations

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Playlist, self).__init__()
        self.id = self.uuid
        self.is_public = self.publicPlaylist # For Backward Compatibility
        self.last_updated = self.lastUpdated # For Backward Compatibility
        self.num_tracks = self.numberOfItems # For Backward Compatibility
        self.name = self.title               # For Backward Compatibility
        if self.description == None:
            self.description = ''
        self._image = kwargs.get('image', None) # Because "image" is a property method
        self.created= self.parse_date(self.created)
        # New Property for Backward Compatibility
        self.creationDate = self.created
        self.lastUpdated = self.parse_date(self.lastUpdated, default=self.created)
        self.lastItemAddedAt = self.parse_date(self.lastItemAddedAt, default=self.lastUpdated)
        if not self.trn:
            self.trn = 'trn:playlist:' + self.uuid
        try:
            self.parentFolderId = kwargs['parent']['id']
            self.parentFolderName = kwargs['parent']['name']
        except:
            pass
        try:
            self.creatorId = kwargs['creator']['id']
        except:
            pass

    @property
    def isUserPlaylist(self):
        return True if self.type == 'USER' else False

    @property
    def numberOfItems(self):
        return self.numberOfTracks + self.numberOfVideos

    @property
    def year(self):
        if self.lastUpdated:
            return self.lastUpdated.year
        elif self.creationDate:
            return self.creationDate.year
        return datetime.datetime.now().year

    @property
    def image(self):
        if self.squareImage:
            return IMG_URL.format(picture=self.squareImage.replace('-', '/'), size='640x640')
        elif self._image:
            return IMG_URL.format(picture=self._image.replace('-', '/'), size='320x214')
        return IMG_URL.format(picture=DEFAULT_PLAYLIST_IMG.replace('-', '/'), size='320x214')

    @property
    def fanart(self):
        if self._image:
            return IMG_URL.format(picture=self._image.replace('-', '/'), size='1080x720')
        return None


class PlayableMedia(BrowsableMedia):
    # Common Properties for Tacks and Videos
    title = 'Unknown'
    artist = None
    artists = []
    album = None
    version = None
    explicit = False
    duration = 30
    audioQuality = Quality.lossless
    allowStreaming = True
    streamReady = True
    streamStartDate = None

    # Internal Properties
    _playlist_id = None        # ID of the Playlist
    _playlist_pos = -1         # Item position in playlist
    _etag = None               # ETag for User Playlists
    _playlist_name = None      # Name of Playlist
    _playlist_type = ''        # Playlist Type

    def __init__(self):
        super(PlayableMedia, self).__init__()
        self.streamStartDate = self.parse_date(self.streamStartDate)
        self.name = self.title  # For Backward Compatibility

    @property
    def year(self):
        if self.streamStartDate:
            return self.streamStartDate.year
        return datetime.datetime.now().year

    @property
    def available(self):
        return self.streamReady and self.allowStreaming


class Track(PlayableMedia):
    trackNumber = 1
    volumeNumber = 1
    popularity = 0
    isrc = None
    premiumStreamingOnly = False
    replayGain = 0.0
    peak = 1.0
    editable = False
    audioModes = [AudioMode.stereo]
    mix_ids = {}

    # Internal Properties
    _ftArtists = []  # All artists except main (Filled by parser)
    _cut = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Track, self).__init__()
        self.track_num = self.trackNumber # For Backward Compatibility
        self.disc_num =self.volumeNumber  # For Backward Compatibility
        self.popularity = int("0%s" % self.popularity)
        try:
            self.mix_ids = kwargs['mixes']
        except:
            self.mix_ids = {}

    @property
    def year(self):
        if self.album and isinstance(self.album, Album) and getattr(self.album, 'year', None):
            return self.album.year
        return super(Track, self).year

    @property
    def image(self):
        if self.album and isinstance(self.album, Album):
            return self.album.image
        return IMG_URL.format(picture=DEFAULT_ALBUM_IMG.cover.replace('-', '/'), size='640x640')

    @property
    def fanart(self):
        if self.artist and isinstance(self.artist, Artist):
            return self.artist.fanart
        return None

    @property
    def isMqa(self):
        return True if self.audioQuality == Quality.hi_res else False

    @property
    def isDolbyAtmos(self):
        try:
            return True if AudioMode.dolby_atmos in self.audioModes else False
        except:
            return False


class Video(PlayableMedia):
    releaseDate = None
    quality = None
    imageId = None
    squareImage = None
    popularity = 0
    quality = 'MP4_1080P'

    # Internal Properties
    _ftArtists = []  # All artists except main (Filled by parser)

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Video, self).__init__()
        self.releaseDate = self.parse_date(self.releaseDate)

    @property
    def year(self):
        if self.releaseDate:
            return self.releaseDate.year
        return super(Video, self).year

    @property
    def image(self):
        if self.squareImage:
            return IMG_URL.format(picture=self.squareImage.replace('-', '/'), size='320x320')
        elif self.imageId:
            return IMG_URL.format(picture=self.imageId.replace('-', '/'), size='320x214')
        return IMG_URL.format(picture=DEFAULT_VIDEO_IMB.replace('-', '/'), size='320x214')

    @property
    def fanart(self):
        if self.artist and isinstance(self.artist, Artist):
            return self.artist.fanart
        return None

    def getFtArtistsText(self):
        text = ''
        for item in self._ftArtists:
            if len(text) > 0:
                text = text + ', '
            text = text + item.name
        if len(text) > 0:
            text = 'ft. by ' + text
        return text


class Promotion(BrowsableMedia):
    header = None
    subHeader = None
    shortHeader = None
    shortSubHeader = None
    standaloneHeader = None
    group = None        # NEWS|DISCOVERY|RISING
    created = None
    text = None
    imageId = None
    imageURL = None
    type = None         # PLAYLIST|ALBUM|VIDEO|EXTURL
    artifactId = None
    duration= 0
    popularity = 0
    trn = None
    parentFolderId = None
    parentFolderName = ''
    parent = {}

    # Internal Properties
    _artist = None       # filled by parser

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Promotion, self).__init__()
        self.created = self.parse_date(self.created)
        self.id = '%s' % self.artifactId
        self.id = self.id.strip()
        self.name = self.shortHeader
        if self.type == 'ALBUM' and 'http' in self.id and 'album/' in self.id:
            # Correct malformed ID
            self.id = self.id.split('album/')[1]
        if self.type == 'VIDEO' and 'http' in self.id and 'video/' in self.id:
            # Correct malformed ID
            self.id = self.id.split('video/')[1]
        if not self.trn and self.type == 'PLAYLIST':
            self.trn = 'trn:playlist:' + self.id
        try:
            self.parentFolderId = kwargs['parent']['id']
            self.parentFolderName = kwargs['parent']['name']
        except:
            pass

    @property
    def image(self):
        if self.imageId:
            return IMG_URL.format(picture=self.imageId.replace('-', '/'), size='550x400')
        return self.imageURL

    @property
    def fanart(self):
        if self.imageId:
            return IMG_URL.format(picture=self.imageId.replace('-', '/'), size='550x400')
        return self.imageURL


class Category(BrowsableMedia):
    path = None
    hasAlbums = False
    hasArtists = False
    hasPlaylists = False
    hasTracks = False
    hasVideos = False

    # Internal Properties
    _image = None   # "image" is also a property
    _group = ''

    @staticmethod
    def groups():
        return ['featured', 'rising', 'genres', 'moods', 'movies', 'shows']

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Category, self).__init__()
        self.id = self.path
        self._image = kwargs.get('image', None) # Because "image" is a property

    @property
    def image(self):
        if self._image:
            return IMG_URL.format(picture=self._image.replace('-', '/'), size=CATEGORY_IMAGE_SIZES.get(self._group, '512x512'))
        return None

    @property
    def fanart(self):
        if self._image:
            return IMG_URL.format(picture=self._image.replace('-', '/'), size=CATEGORY_IMAGE_SIZES.get(self._group, '512x512'))
        return None

    @property
    def content_types(self):
        types = []
        if self.hasArtists:   types.append('artists')
        if self.hasAlbums:    types.append('albums')
        if self.hasPlaylists: types.append('playlists')
        if self.hasTracks:    types.append('tracks')
        if self.hasVideos:    types.append('videos')
        return types


class Role(object):
    main = 'MAIN'
    featured = 'FEATURED'


class SearchResult(Model):
    ''' List of Search Result Items '''

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(SearchResult, self).__init__()
        self.artists = []
        self.albums = []
        self.tracks = []
        self.playlists = []
        self.videos = []


class DeviceCode(Model):
    deviceCode = ''
    userCode = ''
    verificationUri = ''
    verificationUriComplete = ''
    expiresIn = 0
    interval = 2
    _client_id = None
    _client_secret = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        if isinstance(self.verificationUriComplete, string_types) and not self.verificationUriComplete.lower().startswith('http'):
            self.verificationUriComplete = 'https://' + self.verificationUriComplete
        self._start_time = datetime.datetime.now()
        self._expire_time = self._start_time + datetime.timedelta(seconds=self.expiresIn)

    @property
    def isExpired(self):
        return True if datetime.datetime.now() > self._expire_time else False


class AuthToken(Model):
    status = 200
    error = ''
    sub_status = 0
    error = ''
    error_description = ''
    access_token = ''
    refresh_token = ''
    token_type = ''
    expires_in = 0
    user_id = 0
    username = ''
    country_code = 'WW'

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        user = kwargs.get('user', {})
        self.user_id = user.get('userId', 0)
        self.username = user.get('username', '')
        self.country_code = user.get('countryCode', 'WW')
        self.id = self.user_id
        self.name = self.username
        self.login_time = datetime.datetime.now()
        self.expire_time = self.login_time + datetime.timedelta(seconds=self.expires_in)

    @property
    def success(self):
        return True if self.access_token and self.user_id != 0 else False

    @property
    def authorizationPending(self):
        return True if self.status == 400 and self.sub_status == 1002 else False


class UserInfo(Model):
    username = ''
    firstName = ''
    lastName = ''
    email = ''
    created = None
    picture = None
    newsletter = False
    gender = 'm'
    dateOfBirth = None
    facebookUid = '0'
    subscription = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(UserInfo, self).__init__()
        self.created = self.parse_date(self.created)
        self.dateOfBirth = self.parse_date(self.dateOfBirth)
        self.facebookUid = '%s' % self.facebookUid
        self.name = self.username


class Subscription(Model):
    subscription = {'type': SubscriptionType.hifi}
    status = 'ACTIVE'
    validUntil = None
    highestSoundQuality = None
    premiumAccess = True
    canGetTrial = False
    paymentType = ''

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(Subscription, self).__init__()
        if not self.highestSoundQuality:
            # Determine highest sound quality with subscription type 
            self.highestSoundQuality = {SubscriptionType.hifi: Quality.lossless, 
                                        SubscriptionType.premium: Quality.high,
                                        SubscriptionType.free: Quality.low}.get(self.type, Quality.high)
        self.validUntil = self.parse_date(self.validUntil if self.validUntil else '2099-12-31')

    @property
    def type(self):
        try:
            return self.subscription.get('type', SubscriptionType.hifi)
        except:
            return SubscriptionType.hifi

    @type.setter
    def type(self, value):
        self.subscription = {'type': value}

    @property
    def isValid(self):
        return self.validUntil >= datetime.datetime.now()


class StreamUrl(object):
    url = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TrackUrl(StreamUrl):
    codec = None            # MP3, AAC, FLAC, ALAC, MQA, EAC3
    cutId = None
    soundQuality = None     # LOW, HIGH, LOSSLESS
    audioQuality = None     # LOW, HIGH, LOSSLESS, HI_RES
    encryptionKey = None
    securityToken = None
    securityType = None
    trackId = None
    mimeType = MimeType.audio_mpeg
    urls = []
    # Fields for playbackinfopostpaywall results
    assetPresentation = 'FULL'
    audioMode = AudioMode.stereo
    streamingSessionId = None
    manifestMimeType  = ''
    manifest = None
    manifestJson = {}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(TrackUrl, self).__init__()
        if not self.url and len(self.urls) > 0:
            self.url = self.urls[0]
        if not self.soundQuality:
            self.soundQuality = self.audioQuality
        if ManifestMimeType.tidal_bts in self.manifestMimeType and self.manifest:
            self.manifestJson = json.loads(base64.b64decode(self.manifest).decode('utf-8'))
            self.codec = self.manifestJson['codecs'].upper().split('.')[0] if 'codecs' in self.manifestJson else Codec.M4A
            self.mimeType = self.manifestJson.get('mimeType', MimeType.fromAudioCodec(self.codec))
            self.encryptionKey = self.manifestJson.get('keyId', None)
            self.urls = self.manifestJson['urls']
            self.url = self.urls[0]

    def get_mimeType(self):
        if self.codec:
            return MimeType.fromAudioCodec(self.codec)
        if not isinstance(self.url, string_types):
            return MimeType.audio_m4a
        return MimeType.audio_flac if  '.flac' in self.url else MimeType.audio_mp3 if '.mp3' in self.url else MimeType.audio_m4a

    @property
    def isEncrypted(self):
        return True if self.encryptionKey or self.securityToken or ManifestMimeType.dash_xml in self.manifestMimeType else False


class VideoUrl(StreamUrl):
    videoId = None
    videoQuality = None     # HIGH
    urls = []
    format = 'HLS'
    mimeType = MimeType.video_mp4
    # Fields for playbackinfopostpaywall results
    streamType = None
    assetPresentation = 'FULL'
    audioMode = AudioMode.stereo
    streamingSessionId = None
    manifestMimeType  = ''
    manifest = None
    manifestJson = {}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(VideoUrl, self).__init__()
        if not self.url and len(self.urls) > 0:
            self.url = self.urls[0]
        if ManifestMimeType.apple_mpegurl in self.manifestMimeType and len(self.urls) > 0:
            self.url = self.urls[0]
        elif ManifestMimeType.tidal_emu in self.manifestMimeType and self.manifest:
            self.manifestJson = json.loads(base64.b64decode(self.manifest).decode('utf-8'))
            self.mimeType = self.manifestJson.get('mimeType', MimeType.video_mp4)
            self.urls = self.manifestJson['urls']
            self.url = self.urls[0]

    def get_mimeType(self):
        if isinstance(self.url, string_types) and '.m3u8' in self.url.lower():
            return MimeType.video_m3u8
        return MimeType.video_mp4

    @property
    def isEncrypted(self):
        return True if ManifestMimeType.dash_xml in self.manifestMimeType else False


class CutInfo(Model):
    duration = 0
    userId = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        super(CutInfo, self).__init__()

