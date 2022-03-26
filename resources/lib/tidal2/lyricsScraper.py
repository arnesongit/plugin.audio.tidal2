# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 arneson
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

import re
import requests
import xbmcaddon, xbmcvfs

try:
    from lib.utils import Lyrics, log
except:
    # For older Lyrics addon versions
    from utilities import Lyrics, log as simpleLog
    def log(txt, debug=True): simpleLog(txt)

__title__ = "TIDAL2"
__priority__ = '005'
__lrc__ = True

TIDAL2_PLUGIN = 'plugin.audio.tidal2'
TIDAL2_ADDON = xbmcaddon.Addon(TIDAL2_PLUGIN)


class LyricsFetcher:
    """
    This is a lyrics scraper for the addon plugin.audio.tidal2
    """

    def __init__(self, *args, **kwargs):
        self.DEBUG = kwargs.get('debug', True)
        self.settings = kwargs.get('settings', {})
        self.URL = 'http://localhost:%s/lyrics' % TIDAL2_ADDON.getSetting('fanart_server_port')

    def get_lyrics(self, song):
        log("%s: searching lyrics for %s - %s" % (__title__, song.artist, song.title), debug=self.DEBUG)
        if not TIDAL2_PLUGIN in song.filepath:
            lrcaddon = xbmcaddon.Addon('script.cu.lrclyrics')
            if lrcaddon.getSetting('search_lrc_file') == 'true' or lrcaddon.getSetting('search_file') == 'true':
                # Try to use lrc file in sub folder (for use without the write/delete lyrics option in the CU LRC Lyrics addon)
                filename = song.path2(True)
                if not xbmcvfs.exists(filename):
                    return None
                fd = xbmcvfs.File(filename, 'r')
                subtitles = fd.read()
                fd.close()
                if len(subtitles) > 0:
                    try:
                        lyrics = Lyrics(settings=self.settings)
                    except:
                        lyrics = Lyrics()
                    lyrics.song = song
                    lyrics.source = __title__ + ' (file)'
                    lyrics.lrc = True if re.search(r'(\[\d{2}\:\d{2}\.\d{2}\])', subtitles) else False
                    lyrics.lyrics = subtitles
                    return lyrics
            return None
        lyrics = None
        try:
            track_id = song.filepath.split('play_track/')[1].split('/')[0]
            log("Searching lyrics for Tidal-Track: %s" % track_id, debug=self.DEBUG)
            r = requests.request(method='GET', url=self.URL, params={'id': track_id})
            if not r.ok:
                log("No lyrics for Tidal-Track: %s" % track_id, debug=self.DEBUG)
                return None
            json_data = r.json()
            try:
                lyrics = Lyrics(settings=self.settings)
            except:
                lyrics = Lyrics()
            lyrics_text = json_data.get('subtitles', None)
            if not lyrics_text:
                lyrics_text = json_data.get('lyrics', None)
            if not lyrics_text:
                log("No text in lyrics for Tidal-Track: %s" % track_id, debug=self.DEBUG)
                return None
            lyrics.song = song
            if re.search(r'(\[\d{2}\:\d{2}\.\d{2}\])', lyrics_text):
                log("Found lrc lyrics for Tidal-Track: %s" % track_id, debug=self.DEBUG)
                lyrics.source = __title__ + ' (lrc)'
                lyrics.lrc = True
            else:
                log("Found text lyrics for Tidal-Track: %s" % track_id, debug=self.DEBUG)
                lyrics.source = __title__  + ' (text)'
                lyrics.lrc = False
            lyrics.lyrics = lyrics_text
            return lyrics
        except:
            log("No lyrics found", debug=self.DEBUG)
        return None

# End of FIle