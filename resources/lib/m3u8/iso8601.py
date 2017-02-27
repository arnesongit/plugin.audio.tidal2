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

import datetime
import re

re_iso8601 = re.compile(r'^(?P<full>((?P<year>\d{4})([/-]?(?P<month>(0[1-9])|(1[012]))([/-]?(?P<day>(0[1-9])|([12]\d)|(3[01])))?)?(?:[\sT](?P<hour>([01][0-9])|(?:2[0123]))(\:?(?P<minute>[0-5][0-9])(\:?(?P<second>[0-5][0-9])(?P<ms>([\,\.]\d{1,10})?))?)?(?:Z|([\-+](?:([01][0-9])|(?:2[0123]))(\:?(?:[0-5][0-9]))?))?)?))$')

class iso8601(object):

    @staticmethod
    def parse_date(datestring):

        try:
            m = re_iso8601.match(datestring)
            d = m.groupdict()
            if d['hour'] and d['minute'] and d['second']:
                dat = datetime.datetime(year=int(d['year']), month=int(d['month']), day=int(d['day']), hour=int(d['hour']), minute=int(d['minute']), second=int(d['second']))
            else:
                dat = datetime.datetime(year=int(d['year']), month=int(d['month']), day=int(d['day']))
            return dat
        except:
            dat = datetime.datetime.now()
        return dat
