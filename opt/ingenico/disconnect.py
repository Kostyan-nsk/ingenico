#!/usr/bin/env python

import os
import sys
from errno import *
import time
from stat import *
import settings

def pid_exists(pid):

    if pid < 0:
        return False
    if pid == 0:
        raise ValueError('invalid PID 0')

    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == ESRCH:
            # ESRCH == No such process
            return False
        elif err.errno == EPERM:
            # EPERM clearly means there's a process to deny access to
            return True
        else:
            # According to "man 2 kill" possible error values are
            # (EINVAL, EPERM, ESRCH)
            raise
    else:
        return True

if not os.path.exists(settings.PID_FILE):
    sys.exit(0)

pid_file = open(settings.PID_FILE, 'r')
pid = int(pid_file.readline())
pid_file.close()

if not pid_exists(pid):
    print('Process not found')
    sys.exit(0)

if not os.path.exists(settings.PIPE):
    os.mkfifo(settings.PIPE)
    os.chmod(settings.PIPE, os.stat(settings.PIPE).st_mode | S_IWGRP | S_IWOTH)

pipe = open(settings.PIPE, 'w')
pipe.write('DISCONNECT\n')
pipe.close()
