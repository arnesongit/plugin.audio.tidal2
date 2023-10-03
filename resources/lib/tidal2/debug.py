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
import os
import threading
import traceback

from kodi_six import xbmc, xbmcaddon
from requests import HTTPError

from .common import addon, toUnicode, PY2

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

    def __init__(self, pluginName=None, enableInfoLog=False, enableDebugLog=True, enableDebugger=False):
        ''' Initialize Error Logging with a given Log Level
            enableDebugLog = True : enable debug messages  (normal logging)
            enableInfoLog = True :  enable info messages   (full logging)
        '''
        self.pluginName = pluginName if pluginName != None else addon.getAddonInfo('name')
        self.debugLogEnabled = enableDebugLog
        self.infoLogEnabled = enableInfoLog
        self.debuggerEnabled = enableDebugger
        self.debugServer = 'localhost'
        self.debugPort = 5678

    def log(self, txt = '', level=xbmc.LOGDEBUG):
        ''' Log a text into the Kodi-Logfile '''
        try:
            txt = toUnicode(txt)
            xbmc.log("[%s] %s" % (self.pluginName, txt), level) 
        except:
            xbmc.log("[%s] Logging Error" % self.pluginName, xbmc.LOGERROR)
            traceback.print_exc()

    def debug(self, txt):
        self.log(txt, level=LOGNOTICE if self.debugLogEnabled else xbmc.LOGDEBUG)

    def info(self, txt):
        if self.infoLogEnabled:
            self.log(txt, level=LOGNOTICE)

    def warning(self, txt):
        self.log(txt, level=xbmc.LOGWARNING)

    def error(self, txt):
        self.log(txt, level=xbmc.LOGERROR)

    def logException(self, e, txt=''):
        ''' Logs an Exception as Error Message '''
        try:
            errtab = []
            if txt:
                errtab.append(toUnicode(txt))
            errtab.append(str(e))
            try:
                if isinstance(e, HTTPError) and e.response != None:
                    msg = e.response.json()
                    if 'userMessage' in msg:
                        errtab.append(msg['userMessage'])
                    if 'error_description' in msg:
                        errtab.append(msg['error_description'])
            except:
                pass
            xbmc.log("[%s] %s" % (self.pluginName, '\n'.join(errtab)), level=xbmc.LOGERROR) 
        except:
            pass

    def updatePath(self):
        ''' Update the path to find pydevd Package '''
        # check is pydevd is in the search path
        pydevd_found = False
        for comp in sys.path:
            if comp.find('script.module.pydevd') != -1:
                pydevd_found = True
                break
        if pydevd_found:
            log.debug('Found pydevd in path: %s' % comp)
        else:
            pydevd_path = os.path.join(xbmcaddon.Addon('script.module.pydevd').getAddonInfo('path'), 'lib')
            log.debug('Adding pydev to path: %s' % pydevd_path)
            sys.path.append(pydevd_path)

    def halt(self):
        ''' This is the Break-Point-Function '''
        try:
            self.updatePath()
            log.debug('Starting Remote Debugger')
            import pydevd
            pydevd.settrace(host=self.debugServer, stdout_to_server=True, stderr_to_server=True, port=self.debugPort, suspend=True, trace_only_current_thread=True, wait_for_ready_to_run=True)
            #pydevd.settrace(host=self.debugServer, port=self.debugPort, stdoutToServer=True, stderrToServer=True, 
            #                suspend=True, wait_for_ready_to_run=True, trace_only_current_thread=True)
            log.debug('Remote Debugger started')
        except:
            self.error('pydevd library not found')

    def killDebugThreads(self):
        ''' This kills all PyDevd Remote Debugger Threads '''
        try:
            # self.updatePath()
            import pydevd
            pydevd.stoptrace()
            log.debug("pydevd Debugger Threads stopped")
        except:
            pass

    def runDebugged(self, funcName, *args, **kwargs):
        if PY2 or not self.debuggerEnabled:
            funcName(*args, **kwargs)
        else:
            log.info('Starting Debugging Thread')
            thread = threading.Thread(target=funcName, name='Debug.%s' % self.pluginName, *args, **kwargs)
            thread.start()
            cnt = 1
            while not xbmc.Monitor().waitForAbort(timeout=0.25) and thread.is_alive():
                cnt = cnt + 1
                log.info('Debugging Thread stopped')


log = DebugHelper(enableInfoLog = True if addon.getSetting('debug_log') == 'true' else False,
                  enableDebugLog = True if addon.getSetting('debug_json') == 'true' else False,
                  enableDebugger = True if addon.getSetting('debug_with_new_thread') == 'true' else False)

# End of File