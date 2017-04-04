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

import sys, os
import logging
import xbmc

try:
    from unidecode import unidecode
except:
    def unidecode(txt): 
        return txt.decode('utf-8', 'ignore') 

#------------------------------------------------------------------------------
# Debug class
#------------------------------------------------------------------------------

class DebugHelper(object):

    logHandler = None

    def __init__(self, pluginName, detailLevel=0, enableTidalApiLog=False):
        ''' Initialize Error Logging with a given Log Level
            detailLevel = 0 : xbmc.LOGERROR and xbmc.LOGNOTICE
            detailLevel = 1 : as level 0 plus xbmc.LOGWARNING
            detailLevel = 2 : as level 1 plus xbmc.LOGDEBUG
            detailLevel = 3 : as level 2 plus xbmc.LOGSEVERE
        '''
        self.pluginName = pluginName
        self.detailLevel = detailLevel
        self.debugServer = 'localhost'
        # Set Log Handler for tidalapi
        self.addTidalapiLogger(pluginName, enableDebug=enableTidalApiLog)

    def log(self, txt = '', level=xbmc.LOGDEBUG):
        ''' Log a text into the Kodi-Logfile '''
        try:
            if self.detailLevel > 0 or level == xbmc.LOGERROR:
                if self.detailLevel == 2 and level == xbmc.LOGDEBUG:
                    # More Logging
                    level = xbmc.LOGNOTICE
                elif self.detailLevel == 3 and (level == xbmc.LOGDEBUG or level == xbmc.LOGSEVERE):
                    # Complex Logging
                    level = xbmc.LOGNOTICE
                if level != xbmc.LOGSEVERE:
                    if isinstance(txt, unicode):
                        txt = unidecode(txt)
                    xbmc.log(b"[%s] %s" % (self.pluginName, txt), level) 
        except:
            xbmc.log(b"[%s] Unicode Error in message text" % self.pluginName, xbmc.LOGERROR)

    def logException(self, e, txt=''):
        ''' Logs an Exception as Error Message '''
        try:
            if txt:
                if isinstance(txt, unicode):
                    txt = unidecode(txt)
                xbmc.log(b"[%s] %s\n%s" % (self.pluginName, txt, str(e)), level=xbmc.LOGERROR) 
            logging.exception(str(e))
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
            self.updatePath()
            import pydevd
            pydevd.stoptrace()
        except:
            pass
        pass

    def addTidalapiLogger(self, pluginName, enableDebug):
        if not DebugHelper.logHandler:
            DebugHelper.logHandler = KodiLogHandler(name=pluginName, modules=['resources.lib.tidalapi', 'tidalapi'])
            logger = logging.getLogger()
            logger.addHandler(DebugHelper.logHandler)
            logger.setLevel(logging.DEBUG if enableDebug else logging.WARNING)
        elif enableDebug:
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)


class KodiLogHandler(logging.StreamHandler):

    def __init__(self, name, modules):
        logging.StreamHandler.__init__(self)
        self._modules = modules
        self.pluginName = name
        prefix = b"[%s] " % name
        formatter = logging.Formatter(prefix + b'%(name)s: %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        if record.levelno < logging.WARNING and self._modules and not record.name in self._modules:
            # Log INFO and DEBUG only with enabled modules
            return
        levels = {
            logging.CRITICAL: xbmc.LOGFATAL,
            logging.ERROR: xbmc.LOGERROR,
            logging.WARNING: xbmc.LOGWARNING,
            logging.INFO: xbmc.LOGNOTICE,
            logging.DEBUG: xbmc.LOGSEVERE,
            logging.NOTSET: xbmc.LOGNONE,
        }
        try:
            xbmc.log(self.format(record), levels[record.levelno])
        except:
            try:
                xbmc.log(self.format(record).encode('utf-8', 'ignore'), levels[record.levelno])
            except:
                xbmc.log(b"[%s] Unicode Error in message text" % self.pluginName, levels[record.levelno])

    def flush(self):
        pass

# End of File