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

import os

import gtk
import gobject
from gtkmvc import Model, TreeStoreModel, ListStoreModel

from wader.common.oal import get_os_object
from wader.common.contact import Contact
from wader.common.sms import Message, STO_INBOX, STO_DRAFTS, STO_SENT
from wader.gtk.consts import GLADE_DIR
from wader.gtk.translate import _


class Category(object):
    """
    I represent a category in the SMS/contacts application
    """

    def __init__(self, name, parent=None, pixbuf=None, visible_func=None):
        self.name = name
        self.parent = parent
        self.pixbuf = pixbuf
        self.visible_func = visible_func

    def __repr__(self):
        if self.parent:
            return "<Category %s, parent %s>" % (self.name, self.parent)

        return "<Category %s>" % (self.name)


class CategoriesModel(TreeStoreModel):

    COL_ICON = 0
    COL_NAME = 1
    COL_OBJECT = 2

    def __init__(self):
        super(CategoriesModel, self).__init__(gtk.gdk.Pixbuf,
                                              gobject.TYPE_STRING,
                                              gobject.TYPE_PYOBJECT)
        self.sms_iter = None
        self.cts_iter = None
        self.init_model()

    def init_model(self):
        self.sms_iter = self.add_category(Category(_("SMS")))
        self.cts_iter = self.add_category(Category(_("Contacts")))

    def add_category(self, category):
        column = [category.pixbuf, category.name, category]
        return self.append(category.parent, column)


def struct_to_contact(s):
    """
    Returns a :class:`~wader.common.contact.Contact` instance out of `s`
    """
    if not isinstance(s, Contact):
        index, name, number = s
        return Contact(name, number, index=index)

    return s


def clean_text(text):
    return text.replace('\n', ' ')


class ContactsModel(ListStoreModel):

    COL_NAME = 0
    COL_NUMBER = 1
    COL_OBJECT = 2

    def __init__(self, device=None, contacts=None):
        super(ContactsModel, self).__init__(gobject.TYPE_STRING,
                                            gobject.TYPE_STRING,
                                            gobject.TYPE_PYOBJECT)
        self.device = device

        if contacts is not None:
            map(self.add_contact, contacts)

    def add_contact(self, contact):
        c = struct_to_contact(contact)
        column = [c.name, c.number, c]

        return self.append(column)


class MessagesModel(ListStoreModel):
    """
    Model for the messages treeview
    """

    COL_TEXT = 0
    COL_NUMBER = 1
    COL_DATE = 2
    COL_OBJECT = 3

    def __init__(self, messages=None, contacts=None):
        super(MessagesModel, self).__init__(gobject.TYPE_STRING,
                                            gobject.TYPE_STRING,
                                            gobject.TYPE_STRING,
                                            gobject.TYPE_PYOBJECT)

        self.tz = None

        try:
            self.tz = get_os_object().get_tzinfo()
        except:
            pass

        self.contacts = []
        if contacts:
            self.contacts = map(struct_to_contact, contacts)
        if messages:
            map(self.add_sms, messages)

    def add_sms(self, m):
        if not isinstance(m, Message):
            m = Message.from_dict(m, self.tz)

        # we clean the text to avoid carriage returns in a row
        column = [clean_text(m.text), self.lookup_number(m.number),
                  m.datetime, m]
        return self.append(column)

    def lookup_number(self, number):
        for c in self.contacts:
            if c.number == number:
                return c.name

        return number


class SMSContactsModel(Model):
    """
    Model for the SMSContacts controller
    """

    def __init__(self, device):
        super(SMSContactsModel, self).__init__()
        self.device = device

        self.categories = None

    def get_categories_model(self):
        if self.categories is None:
            model = CategoriesModel()
            # SMS

            # inbox
            inbox_path = os.path.join(GLADE_DIR, 'inbox.png')
            inbox_pixbuf = gtk.gdk.pixbuf_new_from_file(inbox_path)

            def inbox_visible_func(m, _iter):
                obj = m.get_value(_iter, m.COL_OBJECT)
                return (False if not obj else obj.where == STO_INBOX)

            model.add_category(Category(_("Inbox"), parent=model.sms_iter,
                                        pixbuf=inbox_pixbuf,
                                        visible_func=inbox_visible_func))
            # drafts
            drafts_path = os.path.join(GLADE_DIR, 'folder.png')
            drafts_pixbuf = gtk.gdk.pixbuf_new_from_file(drafts_path)

            def drafts_visible_func(m, _iter):
                obj = m.get_value(_iter, m.COL_OBJECT)
                return (False if not obj else obj.where == STO_DRAFTS)

            model.add_category(Category(_("Drafts"), parent=model.sms_iter,
                                        pixbuf=drafts_pixbuf,
                                        visible_func=drafts_visible_func))
            # sent
            sent_path = os.path.join(GLADE_DIR, 'mail-sent.png')
            sent_pixbuf = gtk.gdk.pixbuf_new_from_file(sent_path)

            def sent_visible_func(m, _iter):
                obj = m.get_value(_iter, m.COL_OBJECT)
                return (False if not obj else obj.where == STO_SENT)

            model.add_category(Category(_("Sent"), parent=model.sms_iter,
                                        pixbuf=sent_pixbuf,
                                        visible_func=sent_visible_func))

            # Contacts
            cts_path = os.path.join(GLADE_DIR, 'contacts.png')
            cts_pixbuf = gtk.gdk.pixbuf_new_from_file(cts_path)
            model.add_category(Category(_("SIM"),
                                        parent=model.cts_iter,
                                        pixbuf=cts_pixbuf))
            self.categories = model

        return self.categories

    def get_contacts_model(self, contacts):
        return ContactsModel(contacts=contacts)

    def get_sms_model(self, messages, contacts=None):
        return MessagesModel(messages, contacts)


class SMSModel(Model):
    """
    Model for the send SMS controller
    """
    text = ''
    __observables__ = ('text',)

    def __init__(self, device):
        super(SMSModel, self).__init__()

        self.device = device
