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

# from __future__ import unicode_literals

import os
import xbmc
import xbmcaddon
import threading

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database

from koditidal import addon
import debug


METACACHE_DIR = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
METACACHE_FILE = 'metaCache.db'  # SQlite DB for cach data
CACHE_ALBUMS = True
CACHE_PLAYLISTS = True


class MetaCache(object):

    dbcon = None
    currentThreadId = None

    def __init__(self):
        self.currentThreadId = threading.currentThread()

    def connect(self):
        self.path = os.path.join(METACACHE_DIR, METACACHE_FILE)
        try:
            self.dbcon = database.connect(self.path)
            dbcur = self.dbcon.cursor()
            dbcur.execute("CREATE TABLE IF NOT EXISTS meta (""type TEXT, ""id TEXT, ""data TEXT, ""created DATE, ""UNIQUE(type, id)"");")
            self.dbcon.commit()
        except Exception, e:
            debug.logException(e)

    def close(self):
        if self.dbcon:
            try:
                self.dbcon.close()
                self.dbcon = None
            except:
                pass

    def fetch(self, item_type, item_id, default=None):
        item = default
        try:
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            dbcur.execute("SELECT * FROM meta WHERE (type = '%s' and id = '%s')" % (item_type, item_id))
            match = dbcur.fetchone()
            if match:
                item = eval(match[2])
        except Exception, e:
            debug.logException(e, txt='Error in fetch(%s,%s)' % (item_type, item_id))
        return item

    def fetchAllData(self, item_type):
        items = []
        try:
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            dbcur.execute("SELECT * FROM meta WHERE type = '%s'" % item_type)
            matchall = dbcur.fetchall()
            for match in matchall:
                items.append(eval(match[2]))
        except Exception, e:
            debug.logException(e, txt='Error in fetchAllData(%s)' % item_type)
        return items

    def fetchAllIds(self, item_type):
        items = []
        try:
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            dbcur.execute("SELECT id FROM meta WHERE type = '%s'" % item_type)
            matchall = dbcur.fetchall()
            for match in matchall:
                items.append(match[0])
        except Exception, e:
            debug.logException(e, txt='Error in fetchAllIds(%s)' % item_type)
        return items

    def insert(self, item_type, item_id, data, overwrite=False):
        ok = False
        try:
            if item_type == 'favorites':
                debug.log('MetaCache: Inserting %s Favorite %s' % (len(data), item_id))
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            i = repr(data)
            try: 
                if overwrite:
                    dbcur.execute("INSERT OR REPLACE INTO meta Values (?, ?, ?, DATE('now'))", (item_type, item_id, i))
                else:
                    dbcur.execute("INSERT INTO meta Values (?, ?, ?, DATE('now'))", (item_type, item_id, i))
                ok = True
            except database.IntegrityError:
                ok = False
            except:
                debug.log('Failed: INSERT INTO meta Values type="%s", id="%s", data="%s"' % (item_type, item_id, i), level=xbmc.LOGERROR)
                ok = False    
            self.dbcon.commit()
        except Exception, e:
            debug.logException(e, txt='Error in insert(%s,%s)' % (item_type, item_id))
        return ok

    def insertAlbumJson(self, json_obj):
        if CACHE_ALBUMS and json_obj.get('id') and json_obj.get('releaseDate'):
            self.insert('album', '%s' % json_obj.get('id'), json_obj, overwrite=True)

    def insertUserPlaylist(self, playlist_id, title='Unknown', items=[], overwrite=True):
        if CACHE_PLAYLISTS:
            if not title:
                title = playlist_id
            if items == None:
                if overwrite:
                    debug.log('MetaCache: Resetting UserPlaylist "%s"' % title)
            else:
                if overwrite:
                    debug.log('MetaCache: Updating UserPlaylist "%s" with %s items' % (title, len(items)))
                else:
                    debug.log('MetaCache: Inserting UserPlaylist "%s" with %s items' % (title, len(items)))
            if items == None:
                upd_playlist = { 'id': playlist_id,
                                 'title': title }
            else:
                upd_playlist = { 'id': playlist_id,
                                 'title': title,
                                 'items': items }
            self.insert('userpl', playlist_id, data=upd_playlist, overwrite=overwrite)

    def delete(self, item_type, item_id):
        ok = False
        try:
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            dbcur.execute("DELETE FROM meta WHERE (type = '%s' and id = '%s')" % (item_type, item_id))
            self.dbcon.commit()
            ok = True
        except:
            pass
        return ok

    def deleteAll(self, item_type):
        ok = False
        try:
            if not self.dbcon:
                self.connect()
            dbcur = self.dbcon.cursor()
            dbcur.execute("DELETE FROM meta WHERE (type = '%s')" % item_type)
            self.dbcon.commit()
            ok = True
        except:
            pass
        return ok

# End of File