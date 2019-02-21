#!/usr/bin/env python

import socket
from time import sleep
import sys
import threading
import binascii
import glob
import os
from stat import *
from ftplib import FTP
import settings

s = None
conn = None
ftp = None
ftp_thread = None
ftp_mutex = None
firmware = None

def abort():
    global log
    global s
    global conn
    global ftp

    log.close()
    if ftp is not None:
	ftp.close()
    if conn is not None:
	conn.close()
    if s is not None:
	s.close()
    try:
	os.remove(settings.PID_FILE)
    except Exception:
	sys.exc_clear()

    sys.exit(1)

def logwrite(str):
    global log
    global log_sem
    global logbuf

    for line in str.splitlines():
	logbuf.append(line)
	log_sem.release()
    log.write(str + '\n')
    log.flush()

def hex(s):
    n = len(s)
    i = 0
    ss = bytearray(s)
    result = ''

    while i < n:
	if ss[i] < 32:
	    ss[i] = 46
	i += 1

    for i in range(0, n, 16):
	if n >= i + 16:
	    k = 16
	else:
	    k = n - i
	result += '{:08X} '.format(i) + ' '.join([binascii.hexlify(s)[j:j + 2] for j in range(i * 2, (i + k) * 2, 2)]).ljust(48) + ss[i:i + k] + '\n'

    return result

def delete(line):
    global ftp

    if 'DIRECTORY.SIZ' in line or 'DIRFREE.SIZ' in line:
	return

    if not line.startswith('d'):
	line = line.split()
	file = line[len(line) - 1]
	if file:
	    try:
		ftp.delete(file)
	    except Exception:
		sys.exc_clear()

def ftp_noop_thread():
    global ftp
    global ftp_mutex

    while True:
	sleep(5)
	ftp_mutex.acquire()

	if ftp is not None:
	    try:
		ftp.sendcmd('NOOP')
	    except Exception as msg:
		sys.exc_clear()
	else:
	    ftp_mutex.release()
	    break

	ftp_mutex.release()

def pipe_thread():
    global event
    global firmware
    global logbuf
    global log_sem

    received = False
    while not received:
	pipe = open(settings.PIPE, 'r')
	while True:
	    line = pipe.readline()
	    if line == '':
		break

	    line = line.rstrip()
	    if line.startswith('FIRMWARE ') or line == 'DISCONNECT':
		received = True
		break
	pipe.close()

    if line == 'DISCONNECT':
	logwrite('DISCONNECTED')
	abort()

    firmware = line[9:]
    event.set()

    while True:
	log_sem.acquire()
	pipe = open(settings.PIPE, 'w')
	pipe.write('LOG ' + logbuf.pop(0) + '\n')
	pipe.close()

logbuf = []
log_sem = threading.Semaphore(0)
try:
    log = open(settings.LOG_FILE, 'w')
except Exception as msg:
    print('Failed to open/create file ' + settings.LOG_FILE + ': {0}'.format(msg))
    sys.exit(1)

pid = None
try:
    pid = open(settings.PID_FILE, 'w')
except Exception as msg:
    print('Failed to open/create pid-file ' + settings.PID_FILE + ': {0}'.format(msg))
    sys.exc_clear()

if pid is not None:
    pid.write(str(os.getpid()))
    pid.close()

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except Exception as msg:
    logwrite('Failed to create socket: {0}'.format(msg))
    abort()

if len(sys.argv) < 5:
    logwrite('Not enough actual parameters')
    abort()

try:
    s.bind((sys.argv[4], 6000))
except Exception as msg:
    logwrite('Failed to bind socket: {0}'.format(msg))
    abort()

s.listen(1)
conn, addr = s.accept()
#logwrite('Connected by ' + str(addr))

try:
    request = conn.recv(1024)
except Exception as msg:
    logwrite('Failed to receive packet: {0}'.format(msg))
    abort()

#logwrite('Received request:\n' + hex(request))

if len(request) < 40:
    logwrite('Error: Bad request')
    abort()

ver = str(request[2:5])
identifier = binascii.hexlify(request[31:35]) + '-' + binascii.hexlify(request[35:39])
if ver == 'M40':
    logwrite('Detected terminal: iCT2xx ' + identifier + '\n')
elif ver == 'M44':
    logwrite('Detected terminal: iWL2xx ' + identifier + '\n')
elif ver == 'M46':
    logwrite('Detected terminal: iPP3xx ' + identifier + '\n')
else:
    logwrite('Unknown terminal variant: ' + ver)
    abort()

response = b'\x10\x13\x4C\x4C\x54\x30\x31\x30\x31\x49\x4E\x47\x45\x4E\x49\x43\x4F\x30\x30\x30\x30'
try:
    conn.send(response)
except Exception as msg:
    logwrite('Failed to send packet: {0}'.format(msg))
    abort()

try:
    request = conn.recv(1024)
except Exception as msg:
    logwrite('Failed to receive packet: {0}'.format(msg))
    abort()

if request != b'\x11\x01\x00':
    logwrite('Warning: unrecognized request:\n' + hex(request))

response = b'\x20\x01\x01'
try:
    conn.send(response)
except Exception as msg:
    logwrite('Failed to send packet: {0}'.format(msg))
    abort()

try:
    request = conn.recv(1024)
except Exception as msg:
    logwrite('Failed to receive packet: {0}'.format(msg))
    abort()

if request != b'\x21\x1b\x00\x53\x59\x53\x54\x45\x4d\x20\x20\x20\x20\x20\x53\x57\x41\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20':
    logwrite('Warning: unrecognized request:\n' + hex(request))


i = 0
while i < 10:
    sleep(1)
    ftp = FTP()
    try:
	ftp.connect(sys.argv[5])
    except Exception as msg:
	ftp = None
    if ftp is not None:
	break
    i += 1

if ftp is None:
    logwrite('Failed to connect to FTP: {0}'.format(msg))
    abort()

try:
    ftp.login('ftpuser', '123456')
except Exception as msg:
    logwrite('FTP log in failed: {0}'.format(msg))
    abort()

try:
    ftp.cwd('/')
except Exception as msg:
    logwrite('Failed to change directory to /: {0}'.format(msg))
    abort()

ftp_mutex = threading.Lock()
threading.Thread(target = ftp_noop_thread).start()
if not os.path.exists(settings.PIPE):
    os.mkfifo(settings.PIPE)
    os.chmod(settings.PIPE, os.stat(settings.PIPE).st_mode | S_IWGRP | S_IWOTH)
threading.Thread(target =pipe_thread).start()
event = threading.Event()
event.wait()

script = None
for script in glob.glob(os.path.join(settings.FIRMWARE_PATH, firmware, '*.' + ver)):
    break

if script is None:
    logwrite('ERROR: firmware file list not found')
    abort()

try:
    f = open(script, 'r')
except Exception as msg:
    logwrite('ERROR: Failed to open file ' + script + ': {0}'.format(msg))
    abort()

dirs = []
ftp_mutex.acquire()
for line in f.readlines():
    line = line.rstrip()

    if line.startswith('-e'):
	dir = line[2:]
	try:
	    ftp.cwd('/' + dir)
	except Exception as msg:
	    logwrite('ERROR: Failed to change dir to ' + dir + ': {0}'.format(msg))
	    abort()
	if dir not in dirs and dir != 'SWAP':
	    logwrite('Erasing /' + dir)
	    try:
		ftp.retrlines('LIST', delete)
	    except Exception:
		sys.exc_clear()
	    dirs.append(dir)
	continue

    if line.startswith('.\\'):
	line = line[2:].replace('\\', '/')

    try:
	fp = open(os.path.join(settings.FIRMWARE_PATH, firmware, line), 'r')
    except Exception as msg:
	logwrite('ERROR: Failed to open file ' + line + ': {0}'.format(msg))
	continue

    path, file = os.path.split(line)
    logwrite('Uploading /' + dir + '/' + file)
    try:
	ftp.storbinary('STOR ' + file, fp)
    except Exception as msg:
	logwrite('Failed to upload file ' + line + ': {0}'.format(msg))
    finally:
	fp.close()

f.close()
ftp.close()
ftp = None
ftp_mutex.release()
sleep(1)

request = b'\x22\x01\x00'
try:
    conn.send(request)
except Exception as msg:
    logwrite('ERROR: Failed to send packet: {0}'.format(msg))
    abort()

try:
    response = conn.recv(1024)
except Exception as msg:
    logwrite('ERROR: Failed to receive packet: {0}'.format(msg))
    abort()

if response != request:
    logwrite('Warning: unrecognized response:\n' + hex(response))

request = b'\x00\x01\x00'
try:
    conn.send(request)
except Exception as msg:
    logwrite('ERROR: Failed to send packet: {0}'.format(msg))
    abort()

sleep(1)
conn.close()
s.close()

logwrite('Done!')
log.close()