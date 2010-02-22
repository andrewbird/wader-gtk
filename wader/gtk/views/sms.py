# -*- coding: utf-8 -*-
# Copyright (C) 2008-2009  Warp Networks, S.L.
# Author: Pablo Marti
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

import os
from time import strftime
import datetime

import gtk
import pango

from gtkmvc import View

from wader.gtk.translate import _
from wader.gtk._sexy import ICON_ENTRY_SECONDARY
from wader.gtk.consts import GLADE_DIR
from wader.common.oal import get_os_object

CTS_APP_WIDTH = 200
CTS_APP_HEIGHT = 300

CTS_NAME_WIDTH = 150
CTS_NUMBER_WIDTH = 100

MAIN_APP_WIDTH = 550
MAIN_APP_HEIGHT = 400
MAIN_APP_YALIGN = .6

SMS_APP_WIDTH = 350
SMS_APP_HEIGHT = 250

SMS_DATETIME_WIDTH = 100
SMS_TEXT_WIDTH = 150
SMS_NAME_WIDTH = 70

THROBBER = gtk.gdk.PixbufAnimation(os.path.join(GLADE_DIR, 'throbber.gif'))


class SMSContactsView(View):

    glade = os.path.join(GLADE_DIR, "sms.glade")
    top = 'main_window'

    def __init__(self, **kwds):
        self.throbber = None
        super(SMSContactsView, self).__init__(**kwds)

    def init_ui(self, ctrl):
        icon = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)
        ctrl.search_entry.set_icon(ICON_ENTRY_SECONDARY, icon)

        alignment = gtk.Alignment(yalign=MAIN_APP_YALIGN)
        alignment.add(ctrl.search_entry)
        self['hbox3'].pack_start(alignment, expand=False)

        window = self.get_top_widget()
        window.set_title(_("Manage SMS and Contacts"))
        window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        window.set_size_request(MAIN_APP_WIDTH, MAIN_APP_HEIGHT)
        window.set_property('resizable', True)

    def init_categories_treeview(self, model):
        # left treeview
        treeview = self['treeview1']
        treeview.set_model(model)
        treeview.get_selection().set_mode(gtk.SELECTION_SINGLE)

        column = gtk.TreeViewColumn()
        column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)

        cell = gtk.CellRendererPixbuf()
        cell.set_property('xalign', .9)
        column.pack_start(cell, expand=False)
        column.add_attribute(cell, 'pixbuf', model.COL_ICON)

        cell = gtk.CellRendererText()
        cell.set_property('xalign', .9)
        column.pack_start(cell, expand=True)
        column.add_attribute(cell, 'text', model.COL_NAME)

        treeview.append_column(column)

    def init_secondary_treeview(self):
        treeview = self['treeview2']
        model = treeview.get_model()
        if model:
            if isinstance(model, gtk.TreeModelFilter):
                model = model.get_model()

            model.clear()
            treeview.set_model(None)

        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        map(treeview.remove_column, treeview.get_columns())

        return treeview

    def start_throbber(self):
        if self.throbber is None:
            self.throbber = gtk.Image()
            self['hbox8'].pack_start(self.throbber, expand=False)
            self.throbber.set_from_animation(THROBBER)
            self.throbber.show()

    def stop_throbber(self):
        if self.throbber is not None:
            self.throbber.hide()
            self['hbox8'].remove(self.throbber)
            self.throbber = None

    def load_sms(self, sms):
        textbuffer = self['sms_textview'].get_buffer()
        textbuffer.set_text(sms.text)

        self['delete_toolbutton'].set_sensitive(True)

    def load_contact(self, contact):
        self['name_entry'].set_text(contact.name)
        self['number_entry'].set_text(contact.number)

        self['delete_toolbutton'].set_sensitive(True)

    def load_contacts_model(self, model, ctrl):
        treeview = self.init_secondary_treeview()

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Name"), cell, text=model.COL_NAME)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_NAME)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(CTS_NAME_WIDTH)
        cell.set_property('editable', True)
        cell.connect('edited', ctrl.on_contact_name_cell_edited)
        treeview.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Number"), cell, text=model.COL_NUMBER)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_NUMBER)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(CTS_NUMBER_WIDTH)
        cell.set_property('editable', True)
        cell.connect('edited', ctrl.on_contact_number_cell_edited)
        treeview.append_column(column)

        treeview.set_model(model)

    def load_sms_model(self, model):
        treeview = self.init_secondary_treeview()

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Subject"), cell, text=model.COL_TEXT)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_TEXT)
        cell.set_property('editable', False)
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(SMS_TEXT_WIDTH)
        treeview.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Number"), cell, text=model.COL_NUMBER)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_NUMBER)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(SMS_NAME_WIDTH)
        cell.set_property('editable', False)
        treeview.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Received at"), cell,
                                    text=model.COL_DATE)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_DATE)
        cell.set_property('editable', False)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(SMS_DATETIME_WIDTH)

        # render date func
        def render_date(cellview, cell, model, _iter, tz):
            if isinstance(model, gtk.TreeModelFilter):
                # we are dealing with the filtered model
                _iter = model.convert_iter_to_child_iter(_iter)
                model = model.get_model()

            sms = model.get_value(_iter, model.COL_OBJECT)
            if sms.datetime is not None:
                try:
                    delta = datetime.datetime.now(tz) - sms.datetime
                    # show date if more than one day has passed
                    # otherwise, show time of recept
                    fmt = "%x" if delta.days >= 1 else "%X"
                except TypeError:
                    # dt might be == None
                    fmt = "%x"

                cell.set_property('text',
                                  strftime(fmt, sms.datetime.timetuple()))
            else:
                # no datetime, a SMS_SUBMIT
                cell.set_property('text', _('no timestamp'))

        column.set_cell_data_func(cell, render_date,
                                  get_os_object().get_tzinfo())
        treeview.append_column(column)

        # some boilerplate to be able to sort SMS by date
        def sort_func(m, iter1, iter2, data):
            date1 = m.get_value(iter1, m.COL_DATE)
            date2 = m.get_value(iter2, m.COL_DATE)

            if date1 and not date2:
                return 1
            if date2 and not date1:
                return -1

            return cmp(date1, date2)

        model.set_sort_column_id(model.COL_DATE, gtk.SORT_DESCENDING)
        model.set_sort_func(model.COL_DATE, sort_func, None)

        treeview.set_model(model)

    def set_visible_func(self, visible_func):
        model = self['treeview2'].get_model()
        if not model or not visible_func:
            return

        if hasattr(model, 'add_contact'):
            # do not filter the contact model
            return

        if isinstance(model, gtk.TreeModelFilter):
            model = model.get_model()

        model = model.filter_new()
        model.set_visible_func(visible_func)
        self['treeview2'].set_model(model)


class ContactListView(View):
    glade = os.path.join(GLADE_DIR, "sms.glade")
    top = 'contacts_list_window'

    def __init__(self, contacts_model, **kwds):
        super(ContactListView, self).__init__(**kwds)
        self.style_ui()
        self.setup_treeview(contacts_model)
        self.get_top_widget().set_size_request(CTS_APP_WIDTH, CTS_APP_HEIGHT)

    def style_ui(self):
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(GLADE_DIR,
                                                         'contacts.svg'))
        self.get_top_widget().set_icon(icon)

    def setup_treeview(self, model):
        treeview = self['contact_treeview']
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Name"), cell, text=model.COL_NAME)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_NAME)
        cell.set_property('editable', False)
        treeview.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Number"), cell, text=model.COL_NUMBER)
        column.set_resizable(True)
        column.set_sort_column_id(model.COL_NUMBER)
        cell.set_property('editable', False)
        treeview.append_column(column)

        treeview.set_model(model)


class SMSView(View):

    glade = os.path.join(GLADE_DIR, "sms.glade")
    top = 'sms_window'

    def __init__(self):
        super(SMSView, self).__init__()
        self.style_ui()

    def style_ui(self):
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(GLADE_DIR,
                                                         'inbox.svg'))
        window = self.get_top_widget()
        window.set_icon(icon)
        window.set_size_request(SMS_APP_WIDTH, SMS_APP_HEIGHT)

    def set_text(self, text):
        self['text_textview'].get_buffer().set_text(text)

    def set_number(self, number):
        numbers = self.get_numbers()
        if not numbers:
            self['contacts_entry'].set_text(number)
        else:
            numbers.append(number)
            # use a set to avoid duplicates
            self['contacts_entry'].set_text(','.join(set(numbers)))

    def add_contact(self, contact):
        self.set_number(contact.number)

    def get_numbers(self):
        numbers = self['contacts_entry'].get_text().strip()
        return numbers.split(',') if numbers else []

    def get_text(self):
        _buffer = self['text_textview'].get_buffer()
        return _buffer.get_text(*_buffer.get_bounds())


class ContactsView(View):
    """View for the add contact window"""

    glade = os.path.join(GLADE_DIR, "sms.glade")
    top = 'contacts_window'

    def __init__(self, **kwds):
        super(ContactsView, self).__init__(**kwds)
        self.style_ui()

    def style_ui(self):
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(GLADE_DIR,
                                                         'contacts.svg'))
        window = self.get_top_widget()
        window.set_icon(icon)
