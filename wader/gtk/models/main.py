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

import dbus
import dbus.mainloop.glib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
import gobject
from gtkmvc import Model

from wader.gtk.logger import logger
from wader.gtk.dialogs import show_error_dialog
from wader.gtk.models.profile import ProfileModel
from wader.gtk.models.preferences import PreferencesModel
from wader.gtk.translate import _
from wader.gtk.utils import dbus_error_is, get_error_msg
from wader.gtk.signals import NET_MODE_SIGNALS
from wader.gtk.config import config
from wader.common.consts import (WADER_SERVICE, WADER_OBJPATH, WADER_INTFACE,
                                 WADER_DIALUP_SERVICE, WADER_DIALUP_OBJECT,
                                 CRD_INTFACE, NET_INTFACE, MDM_INTFACE,
                                 NM_SYSTEM_SETTINGS_CONNECTION,
                                 WADER_DIALUP_INTFACE, WADER_KEYRING_INTFACE)
import wader.common.aterrors as E
import wader.common.signals as S

UPDATE_INTERVAL = CONFIG_INTERVAL = 2 * 1000 # 2ms
NETREG_INTERVAL = 5 * 1000 # 5ms

AUTH_TIMEOUT = 150        # 2.5m
ENABLE_TIMEOUT = 2 * 60   # 2m
REGISTER_TIMEOUT = 3 * 60 # 3m

ONE_MB = 2**20

class MainModel(Model):

    __properties__ = {
        'rssi' : 0,
        'profile' : None,
        'device' : None,
        'device_path' : None,
        'dial_path' : None,
        'operator' : _('Unknown'),
        'status' : _('Not registered'),
        'tech' : _('Unknown'),

        'pin_required': False,
        'puk_required': False,
        'puk2_required': False,
        'sim_error' : False,
        'net_error' : '',
        'key_needed' : False,

        'rx_bytes': 0,
        'tx_bytes': 0,
        'total_bytes': 0,

        'transfer_limit_exceeded': False
    }

    def __init__(self):
        super(MainModel, self).__init__()
        self.bus = dbus.SystemBus()
        self.obj = None
        self.conf = config
        # we have to break MVC here :P
        self.ctrl = None
        # DialStats SignalMatch
        self.stats_sm = None
        self.dialer_manager = None
        self.preferences_model = PreferencesModel(self, lambda: self.device)
        self._init_wader_object()

    def _init_wader_object(self):
        try:
            self.obj = self.bus.get_object(WADER_SERVICE, WADER_OBJPATH)
        except dbus.DBusException, e:
            title = _("Error while starting wader")
            details = _("Check that your installation is correct and your "
                        " OS/distro is supported: %s" % e)
            show_error_dialog(title, details)
            raise SystemExit()
        else:
            # get the active device
            self.obj.EnumerateDevices(dbus_interface=WADER_INTFACE,
                                      reply_handler=self._get_devices_cb,
                                      error_handler=self._get_devices_eb)

    def _connect_to_signals(self):
        self.obj.connect_to_signal("DeviceAdded", self._device_added_cb)
        self.obj.connect_to_signal("DeviceRemoved", self._device_removed_cb)

        self.bus.add_signal_receiver(self._on_network_key_needed_cb,
                                     "KeyNeeded",
                                     NM_SYSTEM_SETTINGS_CONNECTION)
        self.bus.add_signal_receiver(self._on_keyring_key_needed_cb,
                                     "KeyNeeded",
                                     WADER_KEYRING_INTFACE)

    def _device_added_cb(self, udi):
        logger.info('Device with udi %s added' % udi)
        if not self.device:
            self._get_devices_cb([udi])

    def _device_removed_cb(self, udi):
        logger.info('Device with udi %s removed' % udi)

        if self.device_path:
            logger.info('Device path: %s' % self.device_path)

        if udi == self.device_path:
            self.device = None
            self.device_path = None
            self.dial_path = None
            self.operator = _('Unknown')
            self.status = _('No device')
            self.tech = '----'
            self.rssi = 0

    def _on_network_key_needed_cb(self, opath, tag):
        logger.info("KeyNeeded received, opath: %s tag: %s" % (opath, tag))
        self.ctrl.on_net_password_required(opath, tag)

    def _on_keyring_key_needed_cb(self, opath):
        logger.info("KeyNeeded received")
        self.ctrl.on_keyring_password_required(opath)

    def get_dialer_manager(self):
        if not self.dialer_manager:
            o = self.bus.get_object(WADER_DIALUP_SERVICE, WADER_DIALUP_OBJECT)
            self.dialer_manager = dbus.Interface(o, WADER_DIALUP_INTFACE)

        return self.dialer_manager

    def quit(self, quit_cb):
        def quit_eb(e):
            logger.error("Error while removing device: %s" % get_error_msg(e))
            quit_cb()

        if self.device_path and self.obj:
            logger.debug("Removing device %s before quit." % self.device_path)
            self.device.Enable(False,
                               dbus_interface=MDM_INTFACE,
                               reply_handler=quit_cb,
                               error_handler=quit_eb)
        else:
            quit_cb()

    def get_imsi(self, callback):
        def errback(failure):
            msg = "Error while getting IMSI for device %s"
            logger.error(msg % self.device_path)
            callback(None)

        self.device.GetImsi(dbus_interface=CRD_INTFACE,
                            reply_handler=lambda imsi: callback(imsi),
                            error_handler=errback)

    def _get_devices_eb(self, error):
        logger.error(error)
        # connecting to signals is safe now
        self._connect_to_signals()

    def _get_devices_cb(self, opaths):
        if len(opaths):
            if self.device_path:
                logger.warn("Device %s is already active" % self.device_path)
                return

            self.device_path = opaths[0]
            logger.info("Setting up device %s" % self.device_path)
            self.device = self.bus.get_object(WADER_SERVICE, self.device_path)

            self.pin_required = False
            self.puk_required = False
            self.puk2_required = False
            self.total_bytes = self.conf.get('statistics', 'total_bytes', 0)

            self.enable_device()
        else:
            logger.warn("No devices found")

        # connecting to signals is safe now
        self._connect_to_signals()

    def enable_device(self):
        # enabling the device is an expensive operation
        self.ctrl.view.start_throbber()

        self.device.Enable(True,
                           dbus_interface=MDM_INTFACE,
                           timeout=ENABLE_TIMEOUT,
                           reply_handler=self._enable_device_cb,
                           error_handler=self._enable_device_eb)

        # -1 == special value for Initialising
        self._get_regstatus_cb((-1, None, None))

    def _enable_device_cb(self):
        logger.info("Device enabled")

        self.pin_required = False
        self.puk_required = False
        self.puk2_required = False

        self.device.connect_to_signal(S.SIG_RSSI, self._rssi_changed_cb)
        self.device.connect_to_signal(S.SIG_NETWORK_MODE,
                                      self._network_mode_changed_cb)

        self.device.GetSignalQuality(dbus_interface=NET_INTFACE,
                                     reply_handler=self._rssi_changed_cb,
                                     error_handler=lambda m:
                                        logger.warn("Cannot get RSSI %s" % m))

        self._start_network_registration()
        # delay the profile creation till the device is completely enabled
        self._get_config()

    def _enable_device_eb(self, e):
        if dbus_error_is(e, E.SimPinRequired):
            self.pin_required = True
        elif dbus_error_is(e, E.SimPukRequired):
            self.puk_required = True
        elif dbus_error_is(e, E.SimPuk2Required):
            self.puk2_required = True
        else:
            self.sim_error = get_error_msg(e)

        logger.debug("Error enabling device:\n%s" % get_error_msg(e))

    def _start_network_registration(self):
        self._get_regstatus_cb((2, None, None))
        self.device.Register("",
                             dbus_interface=NET_INTFACE,
                             timeout=REGISTER_TIMEOUT,
                             reply_handler=self._network_register_cb,
                             error_handler=self._network_register_eb)

    def _get_regstatus(self, first_time=False):
        self.device.GetRegistrationInfo(dbus_interface=NET_INTFACE,
                            reply_handler=self._get_regstatus_cb,
                            error_handler=lambda e:
                                logger.warn("Error getting registration "
                                            "status: %s " % get_error_msg(e)))

        if not first_time and self.status != _("Scanning"):
            return False

        # Get Configuration
    def _get_config(self):
        uuid = self.conf.get('profile', 'uuid')
        if uuid and not self.profile:
            from wader.gtk.profiles import manager
            try:
                profile = manager.get_profile_by_uuid(uuid)
                if profile:
                    profiles_model = self.preferences_model.profiles_model
                    model = ProfileModel(profiles_model, profile=profile,
                                         device_callable=lambda: self.device)
                    profiles_model.add_profile(model)
                    self.profile = model

                return
            except Exception, e:
                logger.warn("Error loading initial profile %s %s" % (uuid, e))

            logger.warn("No profile, creating one")
            # ugly and breaks MVC but necessary
            self.ctrl.ask_for_new_profile()

    def _network_register_cb(self, ignored=None):
        self._get_regstatus(first_time=True)
        # once we are registered stop the throbber
        self.ctrl.view.stop_throbber()

    def _network_register_eb(self, error):
        logger.error("Error while registering to home network %s" % error)
        try:
            self.net_error = E.error_to_human(error)
        except KeyError:
            self.net_error = error

        # fake a +CREG: 0,3
        self._get_regstatus_cb((3, None, None))
        # registration failed, stop the throbber
        self.ctrl.view.stop_throbber()

    def _rssi_changed_cb(self, rssi):
        logger.info("RSSI changed %d" % rssi)
        self.rssi = rssi

    def _get_regstatus_cb(self, (status, operator_code, operator_name)):
        if status == -1:
            self.status = _('Initialising')
        if status == 1:
            self.status = _("Registered")
        elif status == 2:
            self.status = _("Scanning")
        elif status == 3:
            self.status = _("Reg. rejected")
        elif status == 4:
            self.status = _("Unknown Error")
        elif status == 5:
            self.status = _("Roaming")

        if operator_name is not None:
            self.operator = operator_name

        if status in [1, 5]:
            return False

        def obtain_registration_info():
            self.device.GetRegistrationInfo(dbus_interface=NET_INTFACE,
                                        reply_handler=self._get_regstatus_cb,
                                        error_handler=logger.warn)

        gobject.timeout_add_seconds(3, obtain_registration_info)
        return True

    def _network_mode_changed_cb(self, net_mode):
        logger.info("Network mode changed %s" % net_mode)
        self.tech = NET_MODE_SIGNALS[net_mode]

    def _send_pin_eb(self, e):
        logger.error("SendPin failed %s" % get_error_msg(e))
        pin_errors = [E.GEN_ERROR, E.PIN_ERROR]
        if e.get_dbus_name() in pin_errors:
            # setting pin_required = True doesn't works and we have
            # to break MVC and ask the controller directly
            self.ctrl.ask_for_pin()
        else:
            logger.error("Unknown error while "
                         "authenticating %s" % get_error_msg(e))

    def _send_puk_eb(self, e):
        logger.error("SendPuk failed: %s" % get_error_msg(e))

    def send_pin(self, pin, cb):
        logger.info("Trying authentication with PIN %s" % pin)
        self.device.SendPin(pin,
                            timeout=AUTH_TIMEOUT,
                            dbus_interface=CRD_INTFACE,
                            reply_handler=lambda *args: cb(),
                            error_handler=self._send_pin_eb)

    def send_puk(self, puk, pin, cb):
        logger.info("Trying authentication with PUK %s, PIN %s" % (puk, pin))
        self.device.SendPuk(puk, pin,
                            dbus_interface=CRD_INTFACE,
                            reply_handler=lambda *args: cb(),
                            error_handler=self._send_puk_eb)

    def check_transfer_limit(self):
        warn_limit = self.conf.get('statistics', 'warn_limit', True)
        if warn_limit:
            transfer_limit = self.conf.get('statistics', 'transfer_limit', 50.0)
            transfer_limit = float(transfer_limit) * ONE_MB
            if self.total_bytes > transfer_limit:
                self.transfer_limit_exceeded = True
            else:
                self.transfer_limit_exceeded = False
        else:
            self.transfer_limit_exceeded = False

    def on_dial_stats(self, stats):
        try:
            total = int(self.conf.get('statistics', 'total_bytes'))
        except ValueError:
            total = 0

        self.rx_bytes, self.tx_bytes = stats
        self.total_bytes = total + self.rx_bytes + self.tx_bytes
        self.check_transfer_limit()

    def start_stats_tracking(self):
        self.stats_sm = self.bus.add_signal_receiver(self.on_dial_stats,
                                                     S.SIG_DIAL_STATS,
                                                     MDM_INTFACE)
    def stop_stats_tracking(self):
        if self.stats_sm is not None:
            self.stats_sm.remove()
            self.stats_sm = None

        self.rx_bytes = 0
        self.tx_bytes = 0
        self.conf.set('statistics', 'total_bytes', self.total_bytes)

