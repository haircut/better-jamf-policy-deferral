#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2017 Matthew Warren
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
"""
Better Jamf Policy Deferral
    Allows much more flexibility in user policy deferrals.
"""

import os
import sys
import time
import argparse
import datetime
import plistlib
import subprocess

# Configuration
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# Deferment LaunchDaemon Config
# LaunchDaemon label: reverse-domain-formatted organization identifier.
# Do not include '.plist'!
DEFAULT_LD_LABEL = "com.contoso.deferred-policy"
# Trigger: What custom trigger should be called to actually kick off the policy?
DEFAULT_LD_JAMF_TRIGGER = "trigger_for_deferred_policy"

# If any app listed here is running on the client, no GUI prompts will be shown
# and this program will exit silently with a non-zero exit code.
# Examples include are to prevent interrupting presentations.
BLOCKING_APPS = ['Keynote', 'Microsoft PowerPoint']

# Paths to binaries
JAMF = "/usr/local/bin/jamf"
JAMFHELPER = ("/Library/Application Support/JAMF/bin/jamfHelper.app/Contents"
              "/MacOS/jamfHelper")

# Prompt GUI Config
GUI_WINDOW_TITLE = "IT Notification"
GUI_HEADING = "Software Updates are ready to be installed."
GUI_ICON = ("/System/Library/CoreServices/Software Update.app/Contents/"
            "Resources/SoftwareUpdate.icns")
GUI_MESSAGE = """Software updates are available for your Mac.

NOTE: Some required updates will require rebooting your computer once installed.

You may schedule these updates for a convenient time by choosing when to start installation.
"""
# The order here is important as it affects the display of deferment options in
# the GUI prompt. We set 300 (i.e. a five minute delay) as the first and
# therefore default option.
GUI_DEFER_OPTIONS = ["300", "0", "1800", "3600", "14400", "43200", "604800"]
GUI_BUTTON = "Okay"

# Confirmation dialog Config
GUI_S_HEADING = "Update scheduled"
GUI_S_ICON = ("/System/Library/CoreServices/Software Update.app/Contents/"
              "Resources/SoftwareUpdate.icns")
GUI_S_BUTTON = "OK"
# This string should contain '{date}' somewhere so that it may be replaced by
# the specific datetime for which installation is scheduled
GUI_S_MESSAGE = """Installation of required updates will begin on {date}."""

# Error message dialog
GUI_E_HEADING = "An error occurred."
GUI_E_ICON = ("/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources"
              "/AlertStopIcon.icns")
GUI_E_MESSAGE = ("A problem occurred processing your request. Please contact "
                 "your administrator for assistance.")

# Program Logic
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def choices_with_default(choices, default):
    """This closure defines an argparser custom action that ensures an argument
       value is in a list of choices, and if not, sets the argument to a default
       value.

       Implementing this argparser action instead of using only a 'choices' list
       for the argument works better for a script called from Jamf where an
       optional parameter may be omitted from the policy definition, but
       subsequent parameters are passed, ie. script.py 1 2 3 [omitted] 5 6
    """
    class customAction(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if (values in choices) or (values == default):
                setattr(args, self.dest, values)
            else:
                setattr(args, self.dest, default)

    return customAction


def build_argparser():
    """Creates the argument parser"""
    description = "Allows much more flexibility in user policy deferrals."
    parser = argparse.ArgumentParser(description=description)

    # Collect parameters 1-3 into a list; we'll ignore them
    parser.add_argument("params", nargs=3)

    # Assign names to other passed parameters
    parser.add_argument("mode", nargs="?",
                        action=choices_with_default(['prompt', 'cleanup'],
                                                    'prompt'))
    parser.add_argument("launchdaemon_label",
                        default=DEFAULT_LD_LABEL, nargs="?")
    parser.add_argument("jamf_trigger",
                        default=DEFAULT_LD_JAMF_TRIGGER, nargs="?")
    parser.add_argument("unused", nargs="*")

    return parser.parse_known_args()[0]


def calculate_deferment(add_seconds):
    """Returns the timedelta day, hour and minute of the chosen deferment

    Args:
        (int) add_seconds: Number of seconds into the future to calculate

    Returns:
        (int) day: Day of the month
        (int) hour: Hour of the day
        (int) minute: Minute of the hour
        (str) fulldate: human-readable date
    """
    add_seconds = int(add_seconds)
    now = datetime.datetime.now()
    diff = datetime.timedelta(seconds=add_seconds)
    future = now + diff

    return (int(future.strftime("%d")),
            int(future.strftime("%-H")),
            int(future.strftime("%-M")),
            str(future.strftime("%B %-d at %-I:%M %p")))


def display_prompt():
    """Displays prompt to allow user to schedule update installation

    Args:
        None

    Returns:
        (int) defer_seconds: Number of second user wishes to defer installation
    """
    try:
        defer = subprocess.check_output([JAMFHELPER,
                                     '-windowType', 'utility',
                                     '-title', GUI_WINDOW_TITLE,
                                     '-heading', GUI_HEADING,
                                     '-icon', GUI_ICON,
                                     '-description', GUI_MESSAGE,
                                     '-button1', GUI_BUTTON,
                                     '-showDelayOptions',
                                     ' '.join(GUI_DEFER_OPTIONS),
                                     '-lockHUD'])
    except Exception, e:
            defer = str(e.output)
    # Slice return value of jamfhelper output to remove the button index
    defer = defer[:-1]
    if defer:
        return defer
    else:
        return int(0)


def display_confirm(start_date):
    """Displays confirmation of when user scheduled update to install

    Args:
        (str) start_date: human-readable datetime of scheduled install

    Returns:
        None
    """
    confirm = subprocess.check_output([JAMFHELPER,
                                       '-windowType', 'utility',
                                       '-title', GUI_WINDOW_TITLE,
                                       '-heading', GUI_S_HEADING,
                                       '-icon', GUI_S_ICON,
                                       '-description',
                                       GUI_S_MESSAGE.format(date=start_date),
                                       '-button1', GUI_S_BUTTON,
                                       '-timeout', "60",
                                       '-lockHUD'])


def display_error():
    """Displays an error if the LaunchDaemon cannot be written"""

    errmsg = subprocess.check_output([JAMFHELPER,
                                      '-windowType', 'utility',
                                      '-title', GUI_WINDOW_TITLE,
                                      '-heading', GUI_E_HEADING,
                                      '-icon', GUI_E_ICON,
                                      '-description', GUI_E_MESSAGE,
                                      '-button1', "Close",
                                      '-timeout', "60",
                                      '-lockHUD'])


def check_pid(process_name):
    """Checks for a pid of a running process"""
    pid = subprocess.Popen(['pgrep', process_name],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    pid.communicate()
    if pid.returncode > 0:
        return False
    else:
        return True


def detect_blocking_apps():
    """Determines if any blocking apps are running

    Args:
        none

    Returns:
        (bool) true/false if any blocking app is running
    """
    blocking_app_running = False
    for app in BLOCKING_APPS:
        if check_pid(app):
            print "Blocking app {} is running.".format(app)
            blocking_app_running = True

    return blocking_app_running


def write_launchdaemon(job_definition, path):
    """Writes the passed job definition to a LaunchDaemon"""

    success = True

    try:
        with open(path, 'w+') as output_file:
            plistlib.writePlist(job_definition, output_file)
    except IOError:
        print "Unable to write LaunchDaemon!"
        success = False

    # Permissions and ownership
    try:
        os.chmod(path, 0644)
    except:
        print "Unable to set permissions on LaunchDaemon!"
        success = False

    try:
        os.chown(path, 0, 0)
    except:
        print "Unable to set ownership on LaunchDaemon!"
        success = False

    # Load job
    load_job = subprocess.Popen(['launchctl', 'load', path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    load_job.communicate()

    if load_job.returncode > 0:
        print "Unable to load LaunchDaemon!"
        success = False

    return success


def main():
    """Main program"""
    # Build the argparser
    args = build_argparser()

    # Assemble path to LaunchDaemon
    ld_path = os.path.join('/Library/LaunchDaemons',
                           '{}.plist'.format(args.launchdaemon_label))

    if args.mode == 'prompt':
        # Make sure the policy hasn't already been deferred
        if os.path.exists(ld_path):
            print "It appears the user has already chosen to defer this policy."
            sys.exit(1)

        # Check for blocking apps
        if detect_blocking_apps():
            print "A blocking app was running"
            sys.exit(1)

        secs = display_prompt()

        # Define the LaunchDaemon
        daemon = {'Label': args.launchdaemon_label,
                  'UserName': 'root',
                  'GroupName': 'wheel',
                  'LaunchOnlyOnce': True,
                  'ProgramArguments': ['/usr/local/bin/jamf',
                                       'policy',
                                       '-event',
                                       args.jamf_trigger]
                 }

        # Handle start interval of LaunchDaemon based on user's deferrment
        if secs == 0:
            # User chose to "start now" so add the RunAtLoad key
            daemon['RunAtLoad'] = True
        else:
            # User chose to defer, so calculate the deltas and set the
            # StartCalendarInterval key
            day, hour, minute, datestring = calculate_deferment(secs)
            daemon['StartCalendarInterval'] = {'Day': day,
                                               'Hour': hour,
                                               'Minute': minute
                                              }

        # Try to write the LaunchDaemon
        if write_launchdaemon(daemon, ld_path):
            # Show confirmation of selected date if deferred
            if secs > 0:
                display_confirm(datestring)

            sys.exit(0)

        else:
            display_error()
            sys.exit(1)

    elif args.mode == 'cleanup':
        # Check if the LaunchDaemon exists
        if os.path.exists(ld_path):
            # Remove the file
            # Normally you would unload the job first, but since that job will
            # be running the script to remove itself, the policy execution would
            # hang. No bueno. Instead, combining the LaunchOnlyOnce key and
            # unlinking the file ensures it only runs once and is then deleted
            # so it doesn't load back up on next system boot.
            try:
                os.remove(ld_path)
                print "File at {} removed".format(ld_path)
            except OSError:
                print "Unable to remove {}; does it exist?".format(ld_path)

            sys.exit(0)

        else:
            print "No LaunchDaemon found at {}".format(ld_path)
            # Nothing to do, so exit
            sys.exit(0)


if __name__ == '__main__':
    main()
