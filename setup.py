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
setuptools file for Wader gtk
"""

import sys
from os.path import join, isdir, walk

from ez_setup import use_setuptools; use_setuptools()
from setuptools import setup

from wader.gtk.consts import (APP_VERSION, APP_NAME,
                              RESOURCES_DIR)

BIN_DIR = '/usr/bin'
APPLICATIONS = '/usr/share/applications'
PIXMAPS = '/usr/share/pixmaps'
DBUS_SYSTEMD = '/etc/dbus-1/system.d'

def list_files(path, exclude=None):
    result = []
    def walk_callback(arg, directory, files):
        for ext in ['.svn', '.git']:
            if ext in files:
                files.remove(ext)
        if exclude:
            for file in files:
                if file.startswith(exclude):
                    files.remove(file)
        result.extend(join(directory, file) for file in files
                      if not isdir(join(directory, file)))

    walk(path, walk_callback, None)
    return result

data_files = [
   (join(RESOURCES_DIR, 'glade'), list_files('resources/glade')),
   (join(RESOURCES_DIR, 'themes'), list_files('resources/themes')),
   (BIN_DIR, ['bin/wader-gtk']),
]

if sys.platform == 'linux2':
    append = data_files.append
    append((APPLICATIONS, ['resources/desktop/wader-gtk.desktop']))
    append((PIXMAPS, ['resources/desktop/wader-gtk.png']))
    append((DBUS_SYSTEMD, ['resources/dbus/wader-gtk.conf']))


packages = [
    'wader.gtk',
    'wader.gtk.models',
    'wader.gtk.controllers',
    'wader.gtk.views'
]

setup(name=APP_NAME,
      version=APP_VERSION,
      description='3G device manager for Linux',
      download_url="http://public.warp.es/wader",
      author='Pablo Martí Gamboa',
      author_email='pmarti@warp.es',
      license='GPL',
      packages=packages,
      data_files=data_files,
      zip_safe=False,
      test_suite='wader.test',
      classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Topic :: Communications :: Telephony',
        ]
)
