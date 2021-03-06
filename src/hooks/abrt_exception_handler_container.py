#:mode=python:
# -*- coding: utf-8 -*-
## Copyright (C) 2018 Red Hat, Inc.

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Suite 500, Boston, MA  02110-1335  USA

"""
Module for the ABRT exception handling hook in container
"""

import sys
import os
from subprocess import Popen, PIPE

def log(msg):
    """Log message to stderr"""
    sys.stderr.write(msg)

def write_dump(tb_text, tb):
    if sys.argv[0]:
        if sys.argv[0][0] == "/":
            executable = os.path.abspath(sys.argv[0])
        elif sys.argv[0][0] == "-":
            executable = "python {0} ...".format(sys.argv[0])
        else:
            executable = sys.argv[0]
    else:
        # We don't know the path.
        # (BTW, we *can't* assume the script is in current directory.)
        executable = sys.argv[0]

    data = {
        "pid": os.getpid(),
        "executable": executable,
        "reason": tb_text.splitlines()[0],
        "backtrace": tb_text,
        "type": "Python"
    }

    import json
    try:
        json_str = '{{"ABRT": {0}}}\n'.format(json.dumps(data))
        p = Popen(['/usr/libexec/abrt-container-logger-python2'], stdin=PIPE)
        p.communicate(input=json_str.encode())
    except Exception as e:
        log("ERROR: {}\n".format(e))

def handleMyException((etype, value, tb)):
    """
    The exception handling function.

    progname - the name of the application
    version  - the version of the application
    """

    try:
        # Restore original exception handler
        sys.excepthook = sys.__excepthook__  # pylint: disable-msg=E1101

        import errno

        # Ignore Ctrl-C
        # SystemExit rhbz#636913 -> this exception is not an error
        if etype in [KeyboardInterrupt, SystemExit]:
            return sys.__excepthook__(etype, value, tb)

        # Ignore EPIPE: it happens all the time
        # Testcase: script.py | true, where script.py is:
        ## #!/usr/bin/python
        ## import os
        ## import time
        ## time.sleep(1)
        ## os.write(1, "Hello\n")  # print "Hello" wouldn't be the same
        #
        if etype == IOError or etype == OSError:
            if value.errno == errno.EPIPE:
                return sys.__excepthook__(etype, value, tb)

        log("detected unhandled Python exception in '{0}'"
            .format(sys.argv[0]))

        import traceback

        elist = traceback.format_exception(etype, value, tb)

        if tb != None and etype != IndentationError:
            tblast = traceback.extract_tb(tb, limit=None)
            if len(tblast):
                tblast = tblast[len(tblast)-1]
            extxt = traceback.format_exception_only(etype, value)
            if tblast and len(tblast) > 3:
                ll = []
                ll.extend(tblast[:3])
                ll[0] = os.path.basename(tblast[0])
                tblast = ll

            ntext = ""
            for t in tblast:
                ntext += str(t) + ":"

            text = ntext
            text += extxt[0]
            text += "\n"
            text += "".join(elist)

            trace = tb
            while trace.tb_next:
                trace = trace.tb_next
            frame = trace.tb_frame
            text += ("\nLocal variables in innermost frame:\n")
            try:
                for (key, val) in frame.f_locals.items():
                    text += "%s: %s\n" % (key, repr(val))
            except:
                pass
        else:
            text = str(value) + "\n"
            text += "\n"
            text += "".join(elist)

        # Send data to the stderr of PID=1 process
        write_dump(text, tb)

    except:
        # Silently ignore any error in this hook,
        # to not interfere with other scripts
        pass

    return sys.__excepthook__(etype, value, tb)


def installExceptionHandler():
    """
    Install the exception handling function.
    """
    sys.excepthook = lambda etype, value, tb: handleMyException((etype, value, tb))

# install the exception handler when the abrt_exception_handler
# module is imported
try:
    installExceptionHandler()
except Exception, e:
    pass

if __name__ == '__main__':
    # test exception raised to show the effect
    div0 = 1 / 0 # pylint: disable-msg=W0612
    sys.exit(0)
