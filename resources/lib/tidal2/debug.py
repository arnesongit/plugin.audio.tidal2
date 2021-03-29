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

from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import os
import traceback

from kodi_six import xbmc

from .common import addon, toUnicode

try:
    # LOGNOTICE not available in Kodi 19
    LOGNOTICE = xbmc.LOGNOTICE
except:
    # Use LOGINFO in Kodi 19
    LOGNOTICE = xbmc.LOGINFO

#------------------------------------------------------------------------------
# Debug class
#------------------------------------------------------------------------------

class DebugHelper(object):

    def __init__(self, enableDebugLog=True, enableInfoLog=False ):
        ''' Initialize Error Logging with a given Log Level
            enableDebugLog = True : enable debug messages  (normal logging)
            enableInfoLog = True :  enable info messages   (full logging)
        '''
        self.pluginName = addon.getAddonInfo('name')
        self.debugEnabled = enableDebugLog
        self.infosEnabled = enableInfoLog
        self.debugServer = 'localhost'

    def log(self, txt = '', level=xbmc.LOGDEBUG):
        ''' Log a text into the Kodi-Logfile '''
        try:
            if (level == xbmc.LOGINFO and self.infosEnabled) or (level == xbmc.LOGDEBUG and self.debugEnabled):
                level = LOGNOTICE
            txt = toUnicode(txt)
            xbmc.log("[%s] %s" % (self.pluginName, txt), level) 
        except:
            xbmc.log("[%s] Logging Error" % self.pluginName, xbmc.LOGERROR)
            traceback.print_exc()

    def debug(self, txt):
        self.log(txt, level=xbmc.LOGDEBUG)

    def info(self, txt):
        self.log(txt, level=xbmc.LOGINFO)

    def warning(self, txt):
        self.log(txt, level=xbmc.LOGWARNING)

    def error(self, txt):
        self.log(txt, level=xbmc.LOGERROR)

    def logException(self, e, txt=''):
        ''' Logs an Exception as Error Message '''
        try:
            if txt:
                txt = toUnicode(txt)
                xbmc.log("[%s] %s\n%s" % (self.pluginName, txt, str(e)), level=xbmc.LOGERROR) 
            # logging.exception(str(e))
        except:
            pass

    def updatePath(self):
        ''' Update the path to find pydevd Package '''
        # For PyCharm:
        # sys.path.append("/Applications/PyCharm.app/Contents/helpers/pydev")
        # For LiClipse:
        # sys.path.append("/Applications/LiClipse.app/Contents/liclipse/plugins/org.python.pydev_4.4.0.201510052047/pysrc")
        for comp in sys.path:
            if comp.find('addons') != -1:
                pydevd_path = os.path.normpath(os.path.join(comp, os.pardir, 'script.module.pydevd', 'lib'))
                sys.path.append(pydevd_path)
                break
            pass

    def halt(self):
        ''' This is the Break-Point-Function '''
        try:
            self.updatePath()
            import pydevd
            pydevd.settrace(self.debugServer, stdoutToServer=True, stderrToServer=True)
        except:
            pass

    def killDebugThreads(self):
        ''' This kills all PyDevd Remote Debugger Threads '''
        try:
            # self.updatePath()
            import pydevd
            pydevd.stoptrace()
        except:
            pass


log = DebugHelper(enableDebugLog = True if addon.getSetting('debug_log') == 'true' else False,
                  enableInfoLog = True if addon.getSetting('debug_json') == 'true' else False)
# End of File