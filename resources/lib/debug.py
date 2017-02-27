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

from __future__ import unicode_literals

import sys, os, logging
import xbmc
import xbmcaddon

try:
    from unidecode import unidecode
except:
    def unidecode(txt): 
        return txt.decode('utf-8', 'ignore') 

#------------------------------------------------------------------------------
# Global Definitions
#------------------------------------------------------------------------------

DEBUG_ENABLED = True
DEBUG_SERVER = 'localhost'
ADDON_NAME = 'DEBUG'
LOG_DETAILS = 2
    
#------------------------------------------------------------------------------
# Functions
#------------------------------------------------------------------------------

def log(txt = '', level=xbmc.LOGDEBUG):
    ''' Log a text into the Kodi-Logfile '''
    try:
        if LOG_DETAILS > 0:
            if LOG_DETAILS == 2 and level == xbmc.LOGDEBUG:
                # More Logging
                level = xbmc.LOGNOTICE
            if LOG_DETAILS == 3 and (level == xbmc.LOGDEBUG or level == xbmc.LOGSEVERE):
                # Complex Logging
                level = xbmc.LOGNOTICE
            if level != xbmc.LOGSEVERE:
                if isinstance(txt, unicode):
                    txt = unidecode(txt)
                xbmc.log(b"[%s] %s" % (ADDON_NAME, txt), level) 
    except:
        xbmc.log(b"[%s] Unicode Error in message text" % ADDON_NAME, xbmc.LOGERROR)

def logException(e, txt='', level=xbmc.LOGERROR):
    if txt:
        log(txt + '\n' + str(e), level)
    logging.exception(str(e))

def updatePath():
    ''' Update the path to find pydevd Package '''
    if DEBUG_ENABLED:
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

def halt():
    ''' This is the Break-Point-Function '''
    host=None
    if DEBUG_ENABLED:
        if not host:
            if DEBUG_SERVER:
                host = DEBUG_SERVER
            else:
                host = 'localhost'
        updatePath()
        import pydevd
        pydevd.settrace(host, stdoutToServer=True, stderrToServer=True)
        pass


def killDebugThreads():
    ''' This kills all PyDevd Remote Debugger Threads '''
    if DEBUG_ENABLED:
        try:
            updatePath()
            import pydevd
            pydevd.stoptrace()
        except:
            pass
        pass


class KodiLogHandler(logging.StreamHandler):

    def __init__(self):
        logging.StreamHandler.__init__(self)
        addon_id = xbmcaddon.Addon().getAddonInfo('id')
        prefix = b"[%s] " % addon_id
        formatter = logging.Formatter(prefix + b'%(name)s: %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        levels = {
            logging.CRITICAL: xbmc.LOGFATAL,
            logging.ERROR: xbmc.LOGERROR,
            logging.WARNING: xbmc.LOGWARNING,
            logging.INFO: xbmc.LOGINFO,
            logging.DEBUG: xbmc.LOGDEBUG,
            logging.NOTSET: xbmc.LOGNONE,
        }
        if DEBUG_ENABLED:
            try:
                xbmc.log(self.format(record), levels[record.levelno])
            except UnicodeEncodeError:
                xbmc.log(self.format(record).encode('utf-8', 'ignore'), levels[record.levelno])

    def flush(self):
        pass

def setKodiLogHandler():
    logger = logging.getLogger()
    logger.addHandler(KodiLogHandler())
    logger.setLevel(logging.DEBUG)

# End of File