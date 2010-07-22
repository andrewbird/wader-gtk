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
Controllers for SMS and Contacts functionality
"""

import gtk

from messaging.sms import SmsSubmit, is_gsm_text
from messaging.sms.consts import (SEVENBIT_SIZE as SEVENBIT, UCS2_SIZE as UCS2,
                                  SEVENBIT_MP_SIZE as SEVENBIT_MP,
                                  UCS2_MP_SIZE as UCS2_MP)



from wader.common.contact import Contact
from wader.common.sms import Message, STO_DRAFTS, STO_INBOX, STO_SENT
from wader.common.consts import SMS_INTFACE, CTS_INTFACE
from wader.common.signals import SIG_SMS
from wader.gtk.controllers import Controller
from wader.gtk.logger import logger
from wader.gtk.models.sms import ContactsModel, SMSModel
from wader.gtk.views.sms import ContactListView, SMSView, ContactsView
from wader.gtk.utils import get_error_msg
from wader.gtk.translate import _
from wader.gtk import dialogs
from wader.gtk._sexy import IconEntry

SMS_TAB, CTS_TAB = range(2)


class ContactsController(Controller):
    """
    Controller for adding contacts
    """

    def __init__(self, model, view, parent):
        super(ContactsController, self).__init__(model, view)

        self.parent = parent
        self.contact = None

    def register_view(self, view):
        super(ContactsController, self).register_view(view)
        self.connect_to_signals()

    def connect_to_signals(self):
        self.view.get_top_widget().connect('delete_event',
                                           self.on_delete_event_cb)
        self.view['name_entry'].connect('activate', self.on_entry_activated)
        self.view['number_entry'].connect('activate', self.on_entry_activated)

    def on_delete_event_cb(self, *args):
        self.close_controller()

        self.parent = None
        self.contact = None

    def on_entry_activated(self, widget):
        self.on_add_button_clicked(widget)

    def on_add_button_clicked(self, widget):
        name = self.view['name_entry'].get_text()
        number = self.view['number_entry'].get_text()

        if name == '' or number == '':
            title = _('Name or number not specified')
            msg = _('You must provide a valid name and number')
            dialogs.show_error_dialog(title, msg)

            widget = (name == '') and 'name_entry' or 'number_entry'
            self.view[widget].grab_focus()
            return

        self.model.device.Add(name, number,
                              dbus_interface=CTS_INTFACE,
                              reply_handler=self.on_contact_added_cb,
                              error_handler=logger.error)
        # save contact till we receive its index, and then we will add
        # it to the treeview model
        self.contact = Contact(name, number)

    def on_contact_added_cb(self, index):
        self.contact.index = index

        if self.parent.treeview_index == CTS_TAB:
            # only update model if we are in contacts mode
            model = self.parent.view['treeview2'].get_model()
            if isinstance(model, gtk.TreeModelFilter):
                model = model.get_model()

            model.add_contact(self.contact)
            self.contact = None

        self.on_delete_event_cb(None)

    def on_contact_added_eb(self, error):
        title = _("Error adding contact")
        dialogs.show_error_dialog(title, get_error_msg(error))


class ContactListController(Controller):
    """
    Controller for the list of contacts
    """

    def __init__(self, model, view, parent):
        super(ContactListController, self).__init__(model, view)
        self.parent = parent

    def register_view(self, view):
        super(ContactListController, self).register_view(view)
        self.view['contact_treeview'].connect('row-activated',
                                              self.on_row_activated)
        self.view['contact_treeview'].connect('cursor-changed',
                                              self.on_cursor_changed)

    def _set_selected_numbers(self, treeview=None):
        if treeview is None:
            treeview = self.view['contact_treeview']

        model, selected = treeview.get_selection().get_selected_rows()
        if not selected:
            return

        iters = [model.get_iter(path) for path in selected]
        objs = [model.get_value(_iter, model.COL_OBJECT) for _iter in iters]
        map(self.parent.view.add_contact, objs)

    def on_row_activated(self, treeview, path, col):
        self._set_selected_numbers(treeview)

    def on_cursor_changed(self, treeview):
        model, selected = treeview.get_selection().get_selected_rows()
        self.view['contact_button'].set_sensitive(len(selected))

    def on_contacts_button_clicked(self, widget):
        self._set_selected_numbers()


class SMSContactsController(Controller):
    """
    Controller for the SMS and Contacts window
    """

    def __init__(self, model, view, parent):
        super(SMSContactsController, self).__init__(model, view)
        self.parent = parent
        self.category = None
        self.search_entry = IconEntry()
        self.search_entry_cid = None
        self.cts_completion = None
        self.sms_completion = None

        self.treeview_index = None
        self.signal_matches = []

    def register_view(self, view):
        super(SMSContactsController, self).register_view(view)

        self.init_ui()
        self.connect_to_signals()
        self.setup_completions()

    def connect_to_signals(self):
        self.view.get_top_widget().connect('delete_event',
                                  self.on_delete_event_cb)
        # treeview
        self.view['treeview2'].connect('key_press_event',
                                       self.on_treeview2_key_press_event)
        # search entry stuff
        try:
            self.search_entry.connect('icon-pressed',
                                      self.on_search_entry_clear_cb)
        except TypeError:
            # python-sexy is not installed, ignore
            pass

        # connect to SIG_SMS and add SMS to model
        sm = self.model.device.connect_to_signal(SIG_SMS,
                                                 self.on_sms_received_cb)
        self.signal_matches.append(sm)

    def init_ui(self):
        model = self.model.get_categories_model()
        self.view.init_categories_treeview(model)

        treeview = self.view['treeview1']
        sel = treeview.get_selection()
        sel.connect('changed', self.on_categories_treeview_changed)

        # expand sections by default
        _iter = model.get_iter_first()
        while _iter:
            path = model.get_path(_iter)
            treeview.expand_row(path, True)
            _iter = model.iter_next(_iter)

        # delete_toolbutton should only be enabled if there's
        # a selected row
        self.view['delete_toolbutton'].set_sensitive(False)

    def setup_completions(self):
        self.cts_completion = gtk.EntryCompletion()
        self.sms_completion = gtk.EntryCompletion()
        for completion in [self.cts_completion, self.sms_completion]:
            completion.set_property('popup-set-width', False)
            completion.set_property('minimum-key-length', 0)
            completion.set_inline_selection(True)
            completion.set_popup_single_match(True)

        # contacts completion
        self.cts_completion.connect('match-selected',
                                self.on_search_entry_match_cb)

        # sms completion
        if gtk.pygtk_version >= (2, 14, 0):

            def sms_match_func(completion, key, _iter):
                model = completion.get_model()
                text = model.get_value(_iter, model.COL_TEXT)
                return key in text

            self.sms_completion.set_match_func(sms_match_func)
            self.sms_completion.connect('match-selected',
                                        self.on_search_entry_match_cb)

    # callbacks and functionality
    def on_delete_event_cb(self, *args):
        while self.signal_matches:
            sm = self.signal_matches.pop()
            sm.remove()

        self.close_controller()

    def on_quit_menuitem_activate(self, widget):
        self.on_delete_event_cb(widget)

    def on_new_toolbutton_clicked(self, widget):
        if self.treeview_index == SMS_TAB:
            self._new_sms()
        else:
            self._new_contact()

    def on_delete_toolbutton_clicked(self, widget):
        selected = self._get_selected_objects(self.view['treeview2'])
        model = selected['model']

        if self.treeview_index == SMS_TAB:
            delete_func = self._delete_sms
        else:
            delete_func = self._delete_contact

        map(delete_func, selected['objs'])
        map(model.remove, selected['iters'])

    def _new_contact(self):
        model = ContactsModel(device=self.model.device)
        view = ContactsView()
        ctrl = ContactsController(model, view, parent=self)
        view.set_parent_view(self.view)

        view.show()

    def _new_sms(self):
        model = SMSModel(self.model.device)
        view = SMSView()
        ctrl = SMSController(model, view, self)
        view.set_parent_view(self.view)

        view.show()

    def _delete_contact(self, contact):
        self.model.device.Delete(contact.index,
                                 dbus_interface=CTS_INTFACE,
                                 reply_handler=lambda: None,
                                 error_handler=logger.error)

    def _delete_sms(self, sms):
        self.model.device.Delete(sms.index,
                                 dbus_interface=SMS_INTFACE,
                                 reply_handler=lambda: None,
                                 error_handler=logger.error)

    # Search entry callbacks
    def on_search_entry_clear_cb(self, entry, icon_pos, button):
        entry.set_text('')

    def on_search_entry_match_cb(self, completion, filtermodel, _iter):
        treeview = self.view['treeview2']
        sel = treeview.get_selection()
        sel.unselect_all()
        # convert the iter
        childiter = filtermodel.convert_iter_to_child_iter(_iter)
        # select path in original model
        model = filtermodel.get_model()
        sel.select_path(model.get_path(childiter))

    # DBus callbacks
    def on_sms_received_cb(self, index, complete):
        """
        Executed whenever a new SMS is received

        It will append the SMS to the treeview model
        """
        # XXX: Handle complete argument
        # only process it if we're in SMS mode
        if self.treeview_index == SMS_TAB:

            def process_sms_eb(error):
                title = _("Error reading SMS %d") % index
                dialogs.show_error_dialog(title, get_error_msg(error))

            def process_sms_cb(sms):
                model = self.view['treeview2'].get_model()
                if isinstance(model, gtk.TreeModelFilter):
                    model = model.get_model()

                _iter = model.add_sms(sms)
                # XXX: This used to work before without any further
                # explicit action :S
                path = model.get_path(_iter)
                # notify the treeview about the new row
                model.row_inserted(path, _iter)

            # read the SMS and show it to the user
            self.model.device.Get(index,
                                  dbus_interface=SMS_INTFACE,
                                  reply_handler=process_sms_cb,
                                  error_handler=process_sms_eb)

    # Treeviews callbacks and functionality
    def get_selected_row(self, treeview=None):
        """
        Returns the selected row in ``treeview``
        """
        if treeview is None:
            treeview = self.view['treeview2']

        col = treeview.get_cursor()[0]
        model = treeview.get_model()
        return model[col]

    def on_treeview2_row_activated(self, treeview, path, col):
        model = treeview.get_model()
        if isinstance(model, ContactsModel):
            # we'll ignore activated events in the contact model
            # as the way to edit contacts is straight from treeview
            return

        if isinstance(model, gtk.TreeModelFilter):
            model = model.get_model()

        row = self.get_selected_row(treeview)
        obj = row[model.COL_OBJECT]

        m = SMSModel(self.model.device)
        ctrl = SMSController(m, self)
        view = SMSView(ctrl)
        view.set_parent_view(self.view)

        view.show()
        view.set_text(obj.text)

    def on_treeview2_cursor_changed(self, treeview):
        model, selected = treeview.get_selection().get_selected_rows()
        self.view['delete_toolbutton'].set_sensitive(len(selected) > 0)

    def on_categories_treeview_changed(self, selection):
        """
        executed whenever the categories treeview focus changes
        """
        model, _iter = selection.get_selected()
        cat = model.get(_iter, model.COL_OBJECT)[0]
        if cat.name == "SMS" or model.is_ancestor(model.sms_iter, _iter):
            index = SMS_TAB
        else:
            index = CTS_TAB

        self.view.set_visible_func(cat.visible_func)

        if self.treeview_index == index:
            # do not request a new *.List command if its not necessary
            return

        self.treeview_index = index

        # potentially long operation, show throbber
        self.view.start_throbber()

        if self.treeview_index == SMS_TAB:
            self.model.device.List(dbus_interface=SMS_INTFACE,
                                   reply_handler=self.on_sms_list_cb,
                                   error_handler=self.on_sms_list_eb)
            self.category = cat

        elif self.treeview_index == CTS_TAB:
            self.model.device.List(dbus_interface=CTS_INTFACE,
                                   reply_handler=self.on_contacts_list_cb,
                                   error_handler=self.on_contacts_list_eb)

        # there's no contact/SMS selected, so make it not sensitive
        self.view['delete_toolbutton'].set_sensitive(False)

    def on_contact_name_cell_edited(self, widget, path, newname):
        model = self.view['treeview2'].get_model()
        if newname != model[path][model.COL_NAME] and newname != '':
            model[path][model.COL_NAME] = newname
            contact = model[path][model.COL_OBJECT]
            contact.name = newname
            self.model.device.Edit(contact.index, newname, contact.number,
                                   dbus_interface=CTS_INTFACE,
                                   reply_handler=self.on_contact_edited_cb,
                                   error_handler=logger.error)

    def on_contact_number_cell_edited(self, widget, path, newnumber):
        model = self.view['treeview2'].get_model()
        if newnumber != model[path][model.COL_NUMBER] and newnumber != '':
            model[path][model.COL_NUMBER] = newnumber
            contact = model[path][model.COL_OBJECT]
            contact.number = newnumber
            self.model.device.Edit(contact.index, contact.name, newnumber,
                                   dbus_interface=CTS_INTFACE,
                                   reply_handler=self.on_contact_edited_cb,
                                   error_handler=logger.error)

    # actions callbacks
    def on_sms_list_cb(self, sms):
        """
        Callback for org.freedesktop.ModemManager.Gsm.Sms.List

        Loads ``sms`` in the model substituting known numbers by
        its contact name
        """

        def setup_widgets(model):
            self.sms_completion.clear()
            self.sms_completion.set_model(model)
            self.search_entry.set_completion(self.sms_completion)

            if self.category is not None:
                self.view.set_visible_func(self.category.visible_func)
                self.category = None

        def on_contacts_list_cb(contacts):
            model = self.model.get_sms_model(sms, contacts)
            self.view.load_sms_model(model)
            setup_widgets(model)
            # end of potentially long operation
            self.view.stop_throbber()

        def on_contacts_list_eb(error):
            """
            An error has occurred while getting the contacts, ignore 'em
            """
            model = self.model.get_sms_model(sms)
            self.view.load_sms_model(model)
            setup_widgets(model)
            # end of potentially long operation
            self.view.stop_throbber()

        if sms:
            self.model.device.List(dbus_interface=CTS_INTFACE,
                                   reply_handler=on_contacts_list_cb,
                                   error_handler=on_contacts_list_eb)
        else:
            # do not Contacts.List if there are no SMS to process
            model = self.model.get_sms_model(sms)
            self.view.load_sms_model(model)
            setup_widgets(model)
            self.view.stop_throbber()

    def on_sms_list_eb(self, error):
        """
        Errback for org.freedesktop.ModemManager.Gsm.Sms.List

        Show an error message to the user in case something goes bad
        """
        # end of potentially long operation
        self.view.stop_throbber()

        title = _("Error while reading SMS list")
        dialogs.show_error_dialog(title, get_error_msg(error))

    def on_contacts_list_cb(self, contacts):
        """
        Callback for org.freedesktop.ModemManager.Gsm.Contacts.List

        Loads ``contacts`` in the model, taking care of previous
        signal handlers
        """
        model = self.model.get_contacts_model(contacts)
        self.view.load_contacts_model(model, self)

        self.cts_completion.clear()
        self.cts_completion.set_text_column(model.COL_NAME)
        self.cts_completion.set_model(model)
        self.search_entry.set_completion(self.cts_completion)

        # end of potentially long operation
        self.view.stop_throbber()

    def on_contacts_list_eb(self, error):
        """
        Errback for org.freedesktop.ModemManager.Gsm.Contacts.List

        Show an error message to the user in case something goes bad
        """
        # end of potentially long operation
        self.view.stop_throbber()

        title = _("Error while reading contacts list")
        dialogs.show_error_dialog(title, get_error_msg(error))

    def on_contact_edited_cb(self, index):
        """
        executed when the contact has been edited successfully
        """

    def on_treeview2_button_press_event(self, treeview, event):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            model, pathlist = treeview.get_selection().get_selected_rows()
            if pathlist:
                if self.treeview_index == CTS_TAB:
                    menu = self._build_contact_menu(pathlist, treeview)
                else:
                    menu = self._build_sms_menu(pathlist, treeview)

                menu.popup(None, None, None, event.button, event.time)
                return True # selection is lost otherwise

    def on_treeview2_key_press_event(self, treeview, event):
        # key Del was pressed
        if event.keyval == 65535:
            model, pathlist = treeview.get_selection().get_selected_rows()
            if pathlist:
                self._delete_rows(None, pathlist, treeview)

    # helpers
    def _get_selected_objects(self, treeview):
        m, selected = treeview.get_selection().get_selected_rows()
        # we might deal with a TreeModelFilter
        selection = selected
        if isinstance(m, gtk.TreeModelFilter):
            selection = map(m.convert_path_to_child_path, selected)
            m = m.get_model()

        iters = map(m.get_iter, selection)
        objs = [m.get_value(_iter, m.COL_OBJECT) for _iter in iters]
        return dict(objs=objs, iters=iters, model=m)

    def _delete_rows(self, menuitem, pathlist, treeview):
        selected = self._get_selected_objects(treeview)
        m = selected['model']

        intface = CTS_INTFACE if isinstance(m, ContactsModel) else SMS_INTFACE
        for obj in selected['objs']:
            self.model.device.Delete(obj.index, dbus_interface=intface)

        for _iter in selected['iters']:
            m.remove(_iter)

    def _build_contact_menu(self, pathlist, treeview):
        menu = gtk.Menu()
        item = gtk.MenuItem(_("_Send SMS"))
        item.connect("activate", self._send_sms_to_contact, treeview)
        item.show()
        menu.append(item)

        item = gtk.ImageMenuItem(_("_Delete"))
        img = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)
        item.set_image(img)
        item.connect("activate", self._delete_rows, pathlist, treeview)
        item.show()
        menu.append(item)

        return menu

    def _build_sms_menu(self, pathlist, treeview):
        selected = self._get_selected_objects(treeview)

        menu = gtk.Menu()

        if len(selected['objs']) == 1:
            # only show reply or send from storage when only one SMS is sel
            obj = selected['objs'][0]

            item = None

            if obj.where <= STO_INBOX:
                item = gtk.MenuItem(_("_Reply"))
                callback = self._send_sms_to_contact
            elif obj.where == STO_DRAFTS:
                item = gtk.MenuItem(_("_Send"))
                callback = self._send_sms_from_storage
            elif obj.where == STO_SENT:
                # if the SMS is in STO_SENT then only deleting is allowed
                pass

            if item:
                item.connect("activate", callback, treeview)
                item.show()
                menu.append(item)

        item = gtk.ImageMenuItem(_("_Delete"))
        img = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)
        item.set_image(img)
        item.connect("activate", self._delete_rows, pathlist, treeview)
        item.show()
        menu.append(item)

        return menu

    def _send_sms_from_storage(self, menuitem, treeview):
        model = SMSModel(self.model.device)
        view = SMSView()
        ctrl = SMSController(model, view, self, mode=STORAGE)

        view.set_parent_view(self.view)

        selected = self._get_selected_objects(treeview)
        ctrl.set_message_to_send(selected)

        view.show()

    def _send_sms_to_contact(self, menuitem, treeview):
        selected = self._get_selected_objects(treeview)

        model = SMSModel(self.model.device)
        view = SMSView()
        ctrl = SMSController(model, view, self)

        view.set_parent_view(self.view)
        map(view.add_contact, selected['objs'])

        view.show()


IDLE, SENDING = range(2)
STORAGE, REGULAR = range(2)


class SMSController(Controller):
    """
    Controller for the SMS window
    """

    def __init__(self, model, view, parent, mode=REGULAR):
        super(SMSController, self).__init__(model, view)
        self.state = IDLE
        self.mode = mode
        self.has_changed = False

        self.parent = parent
        self.context_id = None
        self.selected = None
        self.messages = []

    def register_view(self, view):
        super(SMSController, self).register_view(view)
        self.connect_to_signals()

    def connect_to_signals(self):
        # destroy event
        self.view.get_top_widget().connect('delete_event',
                                  self.on_delete_event_cb)
        # textbuffer changed
        textbuffer = self.view['text_textview'].get_buffer()
        textbuffer.connect('changed', self.on_textbuffer_changed)

    def set_storage_mode(self):
        self.view.get_top_widget().set_title(_("Send SMS from storage"))
        self.view['contacts_button'].set_sensitive(False)
        self.view['save_toolbutton'].set_sensitive(False)
        self.has_changed = False

    def set_regular_mode(self):
        self.view.get_top_widget().set_title(_("Send SMS"))

    def set_message_to_send(self, selected):
        self.selected = selected
        sms = selected['objs'][0]
        self.view.set_number(sms.number)
        self.view.set_text(sms.text)
        self.set_storage_mode()

    # properties
    def property_text_value_change(self, model, old, new):
        statusbar = self.view['statusbar1']
        if not self.context_id:
            self.context_id = statusbar.get_context_id("main")

        statusbar.push(self.context_id, self._get_statusbar_text(new))

    def _get_statusbar_text(self, text):
        if not len(text):
            return ''

        # get the number of messages
        # we use a default number for encoding purposes
        num_sms = len(SmsSubmit('+342453435', text).to_pdu())
        if num_sms == 1:
            max_length = SEVENBIT if is_gsm_text(text) else UCS2
            return "%d/%d" % (len(text), max_length)
        else:
            max_length = SEVENBIT_MP if is_gsm_text(text) else UCS2_MP
            used = len(text) - (max_length * (num_sms - 1))
            return "%d/%d   (%d SMS)" % (used, max_length, num_sms)

    # callbacks
    def on_textbuffer_changed(self, textbuffer):
        self.model.text = self.view.get_text()
        self.has_changed = True

    def on_contacts_entry_changed(self, entry):
        self.view['send_toolbutton'].set_sensitive(len(entry.get_text()) > 0)
        self.view['save_toolbutton'].set_sensitive(len(entry.get_text()) > 0)
        self.has_changed = True

    def on_contacts_button_clicked(self, widget):

        def on_contacts_list_cb(contacts):
            model = ContactsModel(contacts=contacts)
            view = ContactListView(model)
            ctrl = ContactListController(self.model, view, self)

            view.show()

        self.model.device.List(dbus_interface=CTS_INTFACE,
                               reply_handler=on_contacts_list_cb,
                               error_handler=logger.error)

    def on_send_toolbutton_clicked(self, widget):
        numbers = self.view.get_numbers()
        text = self.view.get_text()

        if not numbers:
            title = _('Invalid number')
            msg = _('You must provide a valid number')
            dialogs.show_error_dialog(title, msg)
            self.view['contacts_entry'].grab_focus()
            return

        if text == '':
            title = _('No text to send')
            msg = _('Are you sure you want to send a blank message?')
            if not dialogs.show_warning_request_cancel_ok(title, msg):
                # user cancelled it
                self.view['text_textview'].grab_focus()
                return

        if self.mode == STORAGE and not self.has_changed:
            # sending from storage
            sms = self.selected['objs'][0]
            self.model.device.SendFromStorage(sms.index,
                                             dbus_interface=SMS_INTFACE,
                                             reply_handler=self.on_sms_sent_cb,
                                             error_handler=self.on_sms_sent_eb)
        else:
            self.state = SENDING
            for number in numbers:
                self.model.device.Send(dict(number=number, text=text),
                                       dbus_interface=SMS_INTFACE,
                                       reply_handler=self.on_sms_sent_cb,
                                       error_handler=self.on_sms_sent_eb)
            self.state = IDLE

    def on_save_toolbutton_clicked(self, widget):
        numbers = self.view.get_numbers()
        text = self.view.get_text()

        if not numbers:
            title = _('Invalid number')
            msg = _('You must provide a valid number')
            dialogs.show_error_dialog(title, msg)
            self.view['contacts_entry'].grab_focus()
            return

        if text == '':
            title = _('No text to save')
            msg = _('Are you sure you want to store a blank message?')
            if not dialogs.show_warning_request_cancel_ok(title, msg):
                # user cancelled it
                self.view['text_textview'].grab_focus()
                return

        self.messages = [Message(num, text) for num in numbers]
        for sms in self.messages:
            self.model.device.Save(sms.to_dict(),
                                   dbus_interface=SMS_INTFACE,
                                   reply_handler=self.on_sms_saved_cb,
                                   error_handler=self.on_sms_saved_eb)

    # functionality callbacks
    def on_delete_event_cb(self, *args):
        self.close_controller()

    def on_sms_sent_cb(self, indexes):
        """
        Executed when a SMS has been successfully sent
        """
        if self.parent.treeview_index == SMS_TAB:
            # only update model if we are in SMS mode
            if self.selected:
                sms = self.selected['objs'][0]
                _iter = self.selected['iters'][0]
                model = self.selected['model']
                # remove the drafts message
                model.remove(_iter)
                # now append the message in Sent
                sms.where = STO_SENT
                model.add_sms(sms)
                self.selected = None

        # hide ourselves if we are not sending more SMS...
        if self.state == IDLE:
            self.on_delete_event_cb(None)

    def on_sms_sent_eb(self, error):
        """
        Executed when an error has occurred sending a SMS
        """
        title = _('Error while sending SMS')
        dialogs.show_error_dialog(title, get_error_msg(error))

    def on_sms_saved_cb(self, indexes):
        """
        Executed when a SMS has been successfully saved
        """
        if self.parent.treeview_index == SMS_TAB:
            # only update model if we are in SMS mode
            model = self.parent.view['treeview2'].get_model()
            if isinstance(model, gtk.TreeModelFilter):
                model = model.get_model()

            sms = self.messages.pop(0)
            sms.index = indexes[-1]
            sms.where = STO_DRAFTS
            model.add_sms(sms)

        if not self.messages:
            # destroy the window now that we are done
            self.on_delete_event_cb(None)

    def on_sms_saved_eb(self, error):
        """
        Executed when an error has occurred saving a SMS
        """
        title = _('Error while saving SMS')
        dialogs.show_error_dialog(title, get_error_msg(error))
