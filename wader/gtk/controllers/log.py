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
"""Log controller"""

from wader.gtk.controllers import Controller


class LogController(Controller):
    """Controller for the log window"""

    def __init__(self, model):
        super(LogController, self).__init__(model)

    def register_view(self, view):
        super(LogController, self).register_view(view)
        view.get_top_widget().connect('delete_event', self.on_delete_event_cb)

        self.model.start_logging(self.on_data_in_cb)

    def on_delete_event_cb(self, *args):
        self.model.stop_logging()
        self.close_controller()

    def on_data_in_cb(self, line):
        textview = self.view['textview']
        _buffer = textview.get_buffer()
        end_iter = _buffer.get_end_iter()
        _buffer.insert(end_iter, "%s\n" % line)
        textview.scroll_to_mark(_buffer.get_insert(), 0)
