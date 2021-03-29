# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Arne Svenson
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
import os
import json
import locale

from kodi_six import xbmc, xbmcaddon, xbmcvfs
from routing import Plugin

#------------------------------------------------------------------------------
# Global Definitions
#------------------------------------------------------------------------------

PY2 = sys.version_info[0] == 2

__addon_id__ = 'plugin.audio.tidal2'
addon = xbmcaddon.Addon(__addon_id__)

try:
    version = json.loads(xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["version", "name"]}, "id": 1 }'))['result']['version']
    KODI_VERSION = (version['major'], version['minor'])
except:
    KODI_VERSION = (16, 1)

if PY2:
    xbmc_translatePath = xbmc.translatePath
else:
    xbmc_translatePath = xbmcvfs.translatePath

# Py3 compat - alias unicode to str, and xrange to range
try:
    unicode  # noqa
except NameError:
    unicode = str
try:
    xrange  # noqa
except NameError:
    xrange = range

def getLocale():
    lo = None
    try:
        lo = locale.getdefaultlocale()[0]
    except:
        pass
    if not lo:
        try:
            lo = locale.getlocale()[0]
        except:
            pass
    if not lo:
        try:
            langval = json.loads(xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Settings.GetSettingValue", "params": {"setting": "locale.language"}, "id": 1 }'))['result']['value'].split('.')[-1]
            lo = locale.locale_alias.get(langval).split('.')[0]
        except:
            pass
    if not lo:
        # If no locale is found take the US locale
        lo = 'en_US'
    return lo

class Const(object):
    addon_id = addon.getAddonInfo('id')
    addon_name = addon.getAddonInfo('name')
    addon_path = addon.getAddonInfo('path')
    addon_profile_path = xbmc_translatePath(addon.getAddonInfo('profile'))
    addon_base_url = 'plugin://' + __addon_id__
    addon_fanart = os.path.join(addon_path, 'fanart.jpg')
    addon_icon = os.path.join(addon_path, 'icon.png')
    basestring_types = str if PY2 else bytes
    string_types = (str, unicode) if PY2 else (str, bytes)
    bytes = str if PY2 else bytes
    int_types = (int, long) if PY2 else (int,)
    locale = getLocale()

class KodiPlugin(Plugin):

    def __init__(self):
        try:
            # Creates a Dump is sys.argv[] is empty !
            Plugin.__init__(self, base_url=Const.addon_base_url)
        except:
            pass
        self.base_url = Const.addon_base_url
        self.name = Const.addon_name

def toUnicode(txt):
    if isinstance(txt, Const.basestring_types):
        return txt.decode('utf-8', 'ignore')
    else:
        return txt

def toBasestring(txt):
    if isinstance(txt, Const.basestring_types):
        return txt
    else:
        return txt.encode('utf-8')

plugin = KodiPlugin()

# End of File