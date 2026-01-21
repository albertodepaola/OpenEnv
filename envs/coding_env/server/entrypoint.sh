#!/bin/bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# Entrypoint script for coding-env Docker container
# Handles:
# 1. Dynamic package installation from ADDITIONAL_IMPORTS environment variable
# 2. Xvfb virtual display startup for headless UI support
# 3. Launching the main application

set -e

# Python standard library modules that should NOT be pip installed
STDLIB_MODULES="abc aifc argparse array ast asynchat asyncio asyncore atexit audioop base64 bdb binascii binhex bisect builtins bz2 calendar cgi cgitb chunk cmath cmd code codecs codeop collections colorsys compileall concurrent configparser contextlib contextvars copy copyreg crypt csv ctypes curses dataclasses datetime dbm decimal difflib dis distutils doctest email encodings ensurepip enum errno faulthandler fcntl filecmp fileinput fnmatch fractions ftplib functools gc getopt getpass gettext glob graphlib grp gzip hashlib heapq hmac html http idlelib imaplib imghdr imp importlib inspect io ipaddress itertools json keyword lib2to3 linecache locale logging lzma mailbox mailcap marshal math mimetypes mmap modulefinder msilib msvcrt multiprocessing netrc nis nntplib numbers operator optparse os ossaudiodev parser pathlib pdb pickle pickletools pipes pkgutil platform plistlib poplib posix posixpath pprint profile pstats pty pwd py_compile pyclbr pydoc queue quopri random re readline reprlib resource rlcompleter runpy sched secrets select selectors shelve shlex shutil signal site smtpd smtplib sndhdr socket socketserver spwd sqlite3 ssl stat statistics string stringprep struct subprocess sunau symtable sys sysconfig syslog tabnanny tarfile telnetlib tempfile termios test textwrap threading time timeit tkinter token tokenize trace traceback tracemalloc tty turtle turtledemo types typing unicodedata unittest urllib uu uuid venv warnings wave weakref webbrowser winreg winsound wsgiref xdrlib xml xmlrpc zipapp zipfile zipimport zlib"

# Function to check if a module is in stdlib
is_stdlib() {
    local module=$1
    for stdlib in $STDLIB_MODULES; do
        if [ "$module" = "$stdlib" ]; then
            return 0
        fi
    done
    return 1
}

# Install additional packages from ADDITIONAL_IMPORTS environment variable
if [ -n "$ADDITIONAL_IMPORTS" ]; then
    echo "[entrypoint.sh] Processing ADDITIONAL_IMPORTS: $ADDITIONAL_IMPORTS"

    # Convert comma-separated list to space-separated
    IFS=',' read -ra IMPORTS <<< "$ADDITIONAL_IMPORTS"

    PACKAGES_TO_INSTALL=""
    for import in "${IMPORTS[@]}"; do
        # Trim whitespace
        import=$(echo "$import" | xargs)

        if [ -n "$import" ]; then
            if is_stdlib "$import"; then
                echo "[entrypoint.sh] Skipping stdlib module: $import"
            else
                echo "[entrypoint.sh] Will install: $import"
                PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $import"
            fi
        fi
    done

    if [ -n "$PACKAGES_TO_INSTALL" ]; then
        echo "[entrypoint.sh] Installing packages:$PACKAGES_TO_INSTALL"
        pip install --no-cache-dir $PACKAGES_TO_INSTALL
    else
        echo "[entrypoint.sh] No packages to install (all were stdlib)"
    fi
fi

# Start Xvfb virtual display for headless UI support
echo "[entrypoint.sh] Starting Xvfb on display :99"
Xvfb :99 -screen 0 1024x768x24 &
XVFB_PID=$!

# Wait for Xvfb to start
sleep 1

# Check if Xvfb is running
if kill -0 $XVFB_PID 2>/dev/null; then
    echo "[entrypoint.sh] Xvfb started successfully (PID: $XVFB_PID)"
else
    echo "[entrypoint.sh] WARNING: Xvfb failed to start"
fi

# Export DISPLAY for UI applications
export DISPLAY=:99

# Execute the main command
echo "[entrypoint.sh] Starting application: $@"
exec "$@"
