# -*- coding: utf-8 -*-
# Copyright (C) 2008 Warp Networks S.L.
# Author:  Pablo Martí
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import gobject
from gtkmvc import Model

from wader.common.consts import LOG_PATH
from wader.contrib.tail import Tail

INTERVAL = 15 * 100 # 1.5s


class LogModel(Model):

    def __init__(self):
        super(LogModel, self).__init__()

        self.source_id = None
        self.tail = None

    def start_logging(self, callback):
        self.tail = Tail(LOG_PATH, callback, tailbytes=4096)
        self.source_id = gobject.timeout_add(INTERVAL, self.tail.process)

    def stop_logging(self):
        gobject.source_remove(self.source_id)
        self.tail.close()
        self.tail = None
