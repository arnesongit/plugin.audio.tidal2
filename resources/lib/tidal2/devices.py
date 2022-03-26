# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 arneson
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

import zipfile
import traceback
import base64
import pyaes
from io import BytesIO
from kodi_six import xbmcgui

from .apktools import AXMLPrinter, ARSCParser, ARSCResTableConfig
from .textids import Msg, _T, _P
from .debug import log


class ClientDevice(object):

    def __init__(self, name, client_id='', client_secret=''):
        self.name = name.replace('_', ' ').title()
        self.id = client_id
        self.secret = client_secret

    def __eq__(self, d):
        return True if type(self) == type(d) and self.name == d.name else False

    @property
    def complete(self):
        return True if self.id != '' and self.secret != '' else False


class DeviceSelectorDialog(object):

    @staticmethod
    def select_device(config):
        client = None
        try:
            fname = xbmcgui.Dialog().browseSingle(type=1, heading=_T(Msg.i30283), shares='', mask='.apk|.APK|.apkm|.APKM')
            if fname:
                selector = DeviceSelectorDialog(fname)
                client = selector.select_one_device(config)
                if client:
                    log.info('Selected device: %s' % client.name)
        except:
            pass
        return client

    def __init__(self, apk_filename):
        log.info('Loading APK file: %s' % apk_filename)
        try:
            self.apk = APK(apk_filename)
            self.package_name = self.apk.get_package()
            self.app_name = self.apk.get_app_name()
            self.app_version = self.apk.get_androidversion_name()
            log.info('Package: %s' % self.package_name)
            log.info('App: %s' % self.app_name)
            log.info('Version: %s' % self.app_version)
        except:
            self.apk = None
            self.package_name = '?'
            self.app_name = '?'
            self.app_version = '?'

    def select_one_device(self, config):
        if not isinstance(self.apk, APK):
            xbmcgui.Dialog().ok('Error', _T(Msg.i30284))
            return None
        if self.package_name != 'com.aspiro.tidal':
            xbmcgui.Dialog().ok('Error', _T(Msg.i30285))
            return None
        clients = {}
        res = self.apk.get_android_resources()
        for s in res.values[self.package_name]['\x00\x00']["string"]:
            if s[0].find('_client_id') > 0:
                c = ClientDevice(s[0].split('_client_id')[0].split('default_')[-1])
                if c.name != 'Stage':
                    if not c.name in clients:
                        clients[c.name] = c
                    clients[c.name].id = base64.b64encode(pyaes.AESModeOfOperationCTR(config.token_secret).encrypt(s[1])).decode('utf-8')
            elif s[0].find('_client_secret') > 0:
                c = ClientDevice(s[0].split('_client_secret')[0].split('default_')[-1])
                if c.name != 'Stage':
                    if not c.name in clients:
                        clients[c.name] = c
                    clients[c.name].secret = base64.b64encode(pyaes.AESModeOfOperationCTR(config.token_secret).encrypt(s[1])).decode('utf-8')
        clients = sorted([c for c in clients.values() if c.complete], key=lambda line: line.name)
        if len(clients) == 0:
            xbmcgui.Dialog().ok('%s v%s' % (self.app_name, self.app_version), _T(Msg.i30286))
            return None
        i = xbmcgui.Dialog().select('%s v%s' % (self.app_name, self.app_version), [c.name for c in clients])
        return None if i < 0 else clients[i]


class APK:
    """
    Minimalistic APK class to read app infos and resources
    """
    def __init__(self, filename):

        self.NS_ANDROID_URI = 'http://schemas.android.com/apk/res/android'
        self.appLabel = 'Unknown'
        self.package = 'unknown'
        self.versionNumber = '0.0'
        self.validZip = False
        self.validApk = False
        try:
            _bundle = None
            _zip = zipfile.ZipFile(filename, mode="r")
            self.validZip = True if _zip.testzip() == None else False
            if not self.validZip:
                log.warning('Unzip failed for APK %s' % filename)
                _zip.close()
                return
            namelist = _zip.namelist()
            if "base.apk" in namelist:
                # This is a bundle APK. Only use base.apk
                _bundle = _zip
                _zip = zipfile.ZipFile(BytesIO(_bundle.read('base.apk')))
                _bundle.close()
                namelist = _zip.namelist()
            for i in namelist:
                if i == "AndroidManifest.xml":
                    try:
                        log.info('Found AndroidManifest.xml')
                        parser = AXMLPrinter(_zip.read(i))
                        obj = parser.get_xml_obj()
                        self.package = obj.get('package', default='unknown')
                        log.info('Package is: %s' % repr(self.package))
                        self.versionNumber = obj.get('{%s}versionName' % self.NS_ANDROID_URI, default='0.0')
                        log.info('Version is: %s' % repr(self.versionNumber))
                        self.appLabel = obj.find('application').get('{%s}label' % self.NS_ANDROID_URI, default='Unknown')
                        log.info('appLabel is: %s' % repr(self.appLabel))
                        self.validApk = True
                    except Exception as e:
                        log.logException(e, 'Error reading manifest of APK file %s' % filename)
                        traceback.print_exc()

                elif i == "resources.arsc":
                    log.info('Found resources.arsc')
                    self.arsc = ARSCParser(_zip.read("resources.arsc"))

            _zip.close()
            self.get_app_name()
        except Exception as e:
            log.logException(e, 'Error parsing APK file %s' % filename)
            traceback.print_exc()

    def get_package(self):
        return self.package

    def get_androidversion_name(self):
        return self.versionNumber

    def get_app_name(self):
        try:
            if self.appLabel.startswith("@"):
                res_id, pack = self.parse_id(self.appLabel)
                if pack and pack != self.package:
                    self.appLabel = pack
                else:
                    self.appLabel = self.arsc.get_resolved_res_configs(res_id, ARSCResTableConfig.default_config())[0][1]
        except Exception as e:
            log.logException(e, 'Failed to get Application name')
            self.appLabel = 'Unknown'
        return self.appLabel

    def get_android_resources(self):
        return self.arsc

    def parse_id(self, name):
        if not name.startswith('@'):
            raise ValueError("Not a valid resource ID, must start with @: '{}'".format(name))
        # remove @
        name = name[1:]
        package = None
        if ':' in name:
            package, res_id = name.split(':', 1)
        else:
            res_id = name
        if len(res_id) != 8:
            raise ValueError("Numerical ID is not 8 characters long: '{}'".format(res_id))
        try:
            return int(res_id, 16), package
        except ValueError:
            raise ValueError("ID is not a hex ID: '{}'".format(res_id))

# End of File