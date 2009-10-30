# -*- coding: utf-8 -*-
# Copyright (C) 2008-2009  Warp Networks, S.L.
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
"""
View for the log window
"""

from os.path import join

from gtkmvc import View
import gtk.gdk

from wader.gtk.consts import GLADE_DIR


class LogView(View):

    GLADE_FILE = join(GLADE_DIR, "misc.glade")

    def __init__(self, ctrl):
        super(LogView, self).__init__(ctrl, self.GLADE_FILE, 'log_window')
        window = self.get_top_widget()

        icon = gtk.Button().render_icon(gtk.STOCK_FILE, gtk.ICON_SIZE_DIALOG)
        window.set_icon(icon)
        window.maximize()

        # Add ctrl + Q to quit log window
        agroup = gtk.AccelGroup()
        agroup.connect_group(ord('Q'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED,
                             lambda w, x, y, z: x.destroy()) # window
        window.add_accel_group(agroup)
