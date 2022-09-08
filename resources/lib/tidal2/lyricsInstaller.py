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

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import traceback
from kodi_six import xbmcaddon, xbmcvfs, xbmcgui

from .common import KODI_VERSION, addon as TIDAL2_ADDON, isAddonInstalled
from .debug import log

if KODI_VERSION >= (19, 0):
    from xbmcvfs import translatePath
else:
    from xbmc import translatePath


TIDAL2_PLUGIN = 'plugin.audio.tidal2'
TIDAL2_CWD = translatePath(TIDAL2_ADDON.getAddonInfo('path'))

SUBDIR = "tidal2"

LYRICS_PLUGIN = 'script.cu.lrclyrics'
SCRAPER_PY = 'lyricsScraper.py'
try:
    if isAddonInstalled(LYRICS_PLUGIN):
        LYRICS_ADDON = xbmcaddon.Addon(LYRICS_PLUGIN)
        LYRICS_CWD = translatePath(LYRICS_ADDON.getAddonInfo('path'))
except:
    LYRICS_ADDON = None
    LYRICS_CWD = TIDAL2_CWD.replace(TIDAL2_PLUGIN, LYRICS_PLUGIN)

NEW_SETTING = '\t\t\t\t<setting help="" id="tidal2" label="33333" type="boolean">\n'\
              '\t\t\t\t\t<level>0</level>\n'\
              '\t\t\t\t\t<default>true</default>\n'\
              '\t\t\t\t\t<control type="toggle"/>\n'\
              '\t\t\t\t</setting>\n'

NEW_SETTING_OLD_STYLE = '\t\t<setting id="tidal2" type="bool" label="TIDAL2" default="true"/>\n'

NEW_MESSAGE = 'msgctxt "#33333"\nmsgid "TIDAL2"\nmsgstr "TIDAL2"\n'



class LyricsInstaller:
    """
    This class installs the TIDAL2 lyrics scraper into the addon script.cu.lrclyrics
    """
    def __init__(self):
        self.success = True
        self.protocol = []
        if KODI_VERSION >= (19, 0):
            self.scrapers_dir = os.path.join(LYRICS_CWD, 'lib', 'culrcscrapers')
        else:
            self.scrapers_dir = os.path.join(LYRICS_CWD, 'resources', 'lib', 'culrcscrapers')

    @staticmethod
    def lyrics_settings():
        LYRICS_ADDON.openSettings()

    def log_info(self, txt):
        self.protocol.append(txt)
        log.info(txt)

    def log_error(self, txt):
        self.protocol.append(txt)
        log.error(txt)
        self.success = False

    def install_scraper(self, checkInstalled=False):
        """
        Copy the tidal2 scraper source file into the curlscrapers folder of the lyrics addon
        """
        try:
            if checkInstalled:
                self.log_info('Checking if scraper "%s" is installed ...' % SUBDIR)
            subdir = os.path.join(self.scrapers_dir, '')
            if not xbmcvfs.exists(subdir):
                self.log_error('Lyrics addon %s is not installed !' % LYRICS_PLUGIN)
                return False
            if checkInstalled:
                self.log_info('Found Lyrics addon %s' % LYRICS_PLUGIN)
            subdir = os.path.join(self.scrapers_dir, SUBDIR, '')
            if xbmcvfs.exists(subdir):
                self.log_info('Scraper folder "%s" already exists.' % SUBDIR)
            else:
                if checkInstalled:
                    self.log_error('Scraper folder missing: %s' % subdir)
                    return False
                # create tidal2 folder inside the culrcscrapers folder
                if not xbmcvfs.mkdir(subdir):
                    self.log_error('Failed to create scraper folder: %s' % subdir)
                    return False
                self.log_info('Scraper folder "%s" successfully created.' % SUBDIR)
            newfile = os.path.join(subdir, SCRAPER_PY)
            localfile = os.path.join(TIDAL2_CWD, 'resources', 'lib', 'tidal2', SCRAPER_PY)
            if not xbmcvfs.exists(localfile):
                self.log_error('Missing file: %s' % localfile)
                return False
            if checkInstalled and not xbmcvfs.exists(newfile):
                self.log_error('Missing file: %s' % newfile)
                return False
            # copy source of this file as a new scraper (overwrite old version)
            if checkInstalled:
                self.log_info('Scraper source file exists.')
            elif xbmcvfs.copy(localfile, newfile):
                fd = xbmcvfs.File(os.path.join(subdir, '__init__.py'), 'w')
                fd.write(b'\n')
                fd.close()
                self.log_info('Successfully installed scraper "%s" source file.' % SUBDIR)
            else:
                self.log_error('Failed to copy scraper source file: %s' % newfile)
                return False
        except:
            self.log_error("Failed to copy tidal2 lyrics scraper into the addon %s" % LYRICS_PLUGIN)
            traceback.print_exc()
            return False
        return True

    def install_settings(self, checkInstalled=False):
        """
        Create a setting for tidal2 in the settings.xml file of the lyrics addon
        """
        try:
            if checkInstalled:
                self.log_info('Checking if "%s" setting is present ...' % SUBDIR)
            settingsfile = os.path.join(LYRICS_CWD, 'resources', 'settings.xml')
            if not xbmcvfs.exists(settingsfile):
                self.log_error('Settings file is missing: %s' % settingsfile)
                return False
            fd = xbmcvfs.File(settingsfile, mode='r')
            xmldata = fd.read()
            fd.close()
            if SUBDIR in xmldata and ('33333' in xmldata or 'TIDAL2' in xmldata):
                self.log_info('Scraper setting "%s" already exists.' % SUBDIR)
            elif checkInstalled:
                self.log_error('%s setting is not in file %s' % (SUBDIR, settingsfile))
                return False
            elif KODI_VERSION >= (19, 0):
                # Insert tidal2 setting (new style)
                cut = xmldata.split('label="32154">\n')
                if len(cut) != 2:
                    self.log_error('Wrong format of the settings.xml file.')
                    return False
                xmldata = cut[0] + 'label="32154">\n' + NEW_SETTING + cut[1]
                fd = xbmcvfs.File(settingsfile, mode='w')
                if fd.write(xmldata):
                    fd.close()
                    self.log_info('Successfully updated the settings.xml')
                else:
                    fd.close()
                    self.log_error('Failed to update file %s' % settingsfile)
                    return False
            else:
                # Insert tidal2 setting (old style)
                cut = xmldata.split('label="32154" type="lsep"/>\n')
                if len(cut) != 2:
                    self.log_error('Wrong format of the settings.xml file.')
                    return False
                xmldata = cut[0] + 'label="32154" type="lsep"/>\n' + NEW_SETTING_OLD_STYLE + cut[1]
                fd = xbmcvfs.File(settingsfile, mode='w')
                if fd.write(xmldata):
                    fd.close()
                    self.log_info('Successfully updated the settings.xml')
                else:
                    fd.close()
                    self.log_error('Failed to update file %s' % settingsfile)
                    return False
        except:
            self.log_error("Failed to copy tidal2 lyrics scraper into the addon %s" % LYRICS_PLUGIN)
            traceback.print_exc()
            return False
        return True


    def install_label(self, checkInstalled=False):
        """
        Create the TIDAL2 label in the strings.po file of the lyrics addon
        """
        try:
            if KODI_VERSION < (19, 0):
                # not needed for Kodi versions older than Matrix
                return
            if checkInstalled:
                self.log_info('Checking if TIDAL2 label is in the language file ...')
            # Add TIDAL2 label for the new setting
            langfile = os.path.join(LYRICS_CWD, 'resources', 'language', 'resource.language.en_GB', 'strings.po')
            if not xbmcvfs.exists(langfile):
                langfile = os.path.join(LYRICS_CWD, 'resources', 'language', 'resource.language.en_gb', 'strings.po')
                if not xbmcvfs.exists(langfile):
                    self.log_error('Language file missing: %s' % langfile)
                    return False
            fd = xbmcvfs.File(langfile, mode='r')
            podata = fd.read()
            fd.close()
            if 'TIDAL2' in podata and '33333' in podata:
                self.log_info('TIDAL2 label already exists in language file.')
            else:
                if checkInstalled:
                    self.log_error('TIDAL2 label 33333 is missing in file %s' % langfile)
                    return False
                fd = xbmcvfs.File(langfile, mode='w')
                if fd.write(podata + NEW_MESSAGE):
                    fd.close()
                    self.log_info('Successfully inserted label TIDAL2 into the language file.')
                else:
                    fd.close()
                    self.log_error('Failed to update file %s' % langfile)
                    return False
        except:
            self.log_error("Failed to copy tidal2 lyrics scraper into the addon %s" % LYRICS_PLUGIN)
            traceback.print_exc()
            return False
        return True

    def install(self, checkInstalled=False):
        """
        Install this scraper into the lyrics addon directory
        """
        try:
            self.success = True
            self.protocol = []
            self.install_scraper(checkInstalled)
            if self.success or checkInstalled:
                self.install_settings(checkInstalled)
            if self.success or checkInstalled:
                self.install_label(checkInstalled)
            if LYRICS_ADDON and not checkInstalled:
                # Disable all other scrapers in settings
                scrapers = [d for d in os.listdir(self.scrapers_dir) if os.path.isdir(os.path.join(self.scrapers_dir, d)) and d != '__pycache__' and d != SUBDIR]
                for scraper in scrapers:
                    if LYRICS_ADDON.getSetting(scraper) == 'true':
                        LYRICS_ADDON.setSetting(scraper, 'false')
                LYRICS_ADDON.setSetting('silent', 'true')
                # Enable the tidal2 scraper
                LYRICS_ADDON.setSetting(SUBDIR, 'true')
                TIDAL2_ADDON.setSetting('enable_lyrics', 'true')
                try:
                    # For older addon version
                    LYRICS_ADDON.setSetting('save_lyrics1', 'false')
                    LYRICS_ADDON.setSetting('save_lyrics2', 'false')
                except:
                    pass
                try:
                    # for newer addon version
                    LYRICS_ADDON.setSetting('save_lyrics1_lrc', 'false')
                    LYRICS_ADDON.setSetting('save_lyrics1_txt', 'false')
                    LYRICS_ADDON.setSetting('save_lyrics2_lrc', 'false')
                    LYRICS_ADDON.setSetting('save_lyrics2_txt', 'false')
                except:
                    pass
                self.log_info('Successfully installed "%s" scraper. Please restart Kodi !' % SUBDIR)
        except:
            self.log_error("Failed to install tidal2 lyrics scraper")
            traceback.print_exc()
            return False
        return self.success

    def uninstall(self):
        """
        Remove the scraper from the lyrics addon directory
        """
        try:
            self.success = True
            self.protocol = []
            self.log_info('Deleting scraper "%s" folder from the lyrics addon ...' % SUBDIR)
            subdir = os.path.join(self.scrapers_dir, SUBDIR, '')
            if xbmcvfs.exists(subdir):
                if xbmcvfs.rmdir(subdir, force=True):
                    self.log_info('Successfully deleted the folder "%s"' % SUBDIR)
                else:
                    self.log_error('Failed to delete scraper folder "%s"' % SUBDIR)
            else:
                self.log_info('Scraper folder "%s" not exist or already deleted.' % SUBDIR)
            if LYRICS_ADDON:
                LYRICS_ADDON.setSetting(SUBDIR, 'false')
        except:
            self.log_error("Failed to uninstall tidal2 lyrics scraper")
            traceback.print_exc()
            return False
        TIDAL2_ADDON.setSetting('enable_lyrics', 'false')
        return True

    def show_protocol(self):
        """
        Display the protocol log as a Popup Dialog
        """
        txt = '\n'.join(self.protocol) if self.protocol else 'Nothing happened.'
        if len(self.protocol) > 5:
            xbmcgui.Dialog().textviewer('Scraper Installer Protocol', txt)
        else:
            xbmcgui.Dialog().ok('Scraper Installer Protocol', txt)
        return self.success

# End of FIle