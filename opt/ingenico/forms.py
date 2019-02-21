#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from stat import *
import sys
import errno
from time import sleep
import threading
import shutil
import ttk
import tkFont
from Tkinter import *
from tkMessageBox import *
from ftplib import FTP
import settings

main_window = None
ftp = None
ftp_window = None
connecting_window = None
ftp_dirs = []
file_list = []
lastdir = ''
fd = None
total_bytes = 0
recv_bytes = 0
ftp_dir = ''
firmware_dir = ''
progress_window = None
progress_bar = None
progress_label = None
waiting_window = None
log_window = None
listbox = None
status = ''

def quit():
    global main_window
    global status

    if status == 'running':
	return
    main_window.destroy()

def position(window):
    return '+' + str((window.winfo_screenwidth() - window.winfo_width()) / 2) + '+' + \
		 str((window.winfo_screenheight() - window.winfo_height()) / 2)

def ftp_list_dirs(line):
    global ftp
    global ftp_window
    global ftp_dirs


    if line.startswith('d'):
	line = line.split()
	line = line[len(line) - 1]
	if line:
#	    print(line)
	    ftp_dirs.append(line)

def ftp_list_files(line):
    global firmware_dir

    elem = [None] * 4
    if line.startswith('d'):
	elem[0] = 'd'
    else:
	elem[0] = 'f'

    split = line.split()
    elem[1] = int(split[4])
    elem[2] = firmware_dir
    elem[3] = split[len(split) - 1]
    file_list.append(elem)

def file_write(data):
    global fd
    global recv_bytes
    global total_bytes
    global progress_window
    global progress_bar
    global progress_label

    fd.write(data)
    recv_bytes += len(data)
    progress_label['text'] = 'Загрузка: ' + str(recv_bytes) + ' / ' + str(total_bytes)
    progress_bar.step(len(data))
    progress_window.update_idletasks()

def ftp_onclick(event):
    global ftp
    global ftp_window
    global ftp_dir
    global firmware_dir
    global file_list
    global fd
    global recv_bytes
    global total_bytes
    global progress_bar
    global progress_window
    global progress_label
    global fnt
    global lastdir

    del file_list[:]
    firmware_dir = event.widget['text']
    cursor = ftp_window['cursor']
    ftp_window['cursor'] = 'clock'
    ftp_window.update_idletasks()

    try:
	ftp.retrlines('LIST -la ' + firmware_dir, ftp_list_files)
    except Exception as msg:
	showerror('Ошибка', 'Ошибка чтения каталога \'' + firmware_dir + '\': {0}'.format(msg), parent = ftp_window)
	return

    i = 0
    total_bytes = 0
    n = len(file_list)
    while i < n:
#	print(file_list[i])
	if file_list[i][0] == 'd':
	    firmware_dir = os.path.join(file_list[i][2], file_list[i][3])
	    try:
		ftp.retrlines('LIST -la ' + firmware_dir, ftp_list_files)
	    except Exception as msg:
		showerror('Ошибка', 'Ошибка чтения каталога \'' + firmware_dir + '\': {0}'.format(msg), parent = ftp_window)
		return
	else:
	    total_bytes += file_list[i][1]
	i += 1
	n = len(file_list)

    if lastdir != event.widget['text']:
	shutil.rmtree(os.path.join(settings.FIRMWARE_PATH, '$tmp$'), True)
	try:
	    os.mkdir(os.path.join(settings.FIRMWARE_PATH, '$tmp$'))
	except Exception as msg:
	    showerror('Ошибка', 'Ошибка создания временного каталога: {0}'.format(msg), parent = ftp_window)
	    return

    progress_window = Toplevel(ftp_window)
    progress_window.overrideredirect(True)
    progress_window.transient(ftp_window)
    progress_window['cursor'] = 'clock'
#    progress_window.geometry('280x50')
    progress_label = Label(progress_window,
			font = fnt,
			anchor = CENTER,
			borderwidth = 5,
			text = 'Загрузка: 0' + ' / ' + str(total_bytes))
    progress_label.pack(fill = 'both')
    progress_bar = ttk.Progressbar(progress_window, maximum = total_bytes + 1, length = 300, mode = 'determinate')
    progress_bar.pack(fill = 'both', padx = 5, pady = 5)
    progress_window.update_idletasks()
#    progress_window.geometry('+' + str((ftp_window.winfo_screenwidth() - 280) / 2) + '+' + str((ftp_window.winfo_screenheight() - 50) / 2))
    progress_window.geometry(position(progress_window))
    progress_window.update_idletasks()

    i = 0
    recv_bytes = 0
    while i < len(file_list):
	if file_list[i][0] == 'd':
	    i += 1
	    continue

	dir, subdir = os.path.split(file_list[i][2])
	if dir == '':
	    subdir = ''
	else:
	    try:
		os.makedirs(os.path.join(settings.FIRMWARE_PATH, '$tmp$', subdir))
	    except Exception as oe:
		if oe.errno == errno.EEXIST:
		    pass
		else:
		    progress_window.destroy()
		    showerror('Ошибка', 'Ошибка создания подкаталога \'' + subdir + '\': {0}'.format(oe), parent = ftp_window)
		    return

#	print(os.path.join(settings.FIRMWARE_PATH, '$tmp$', subdir, file_list[i][3]))
	if lastdir == event.widget['text']:
	    try:
		size = os.path.getsize(os.path.join(settings.FIRMWARE_PATH, '$tmp$', subdir, file_list[i][3]))
	    except Exception:
		size = -1
		pass
	    if size == file_list[i][1]:
		recv_bytes += file_list[i][1]
		progress_label['text'] = 'Загрузка: ' + str(recv_bytes) + ' / ' + str(total_bytes)
		progress_bar.step(file_list[i][1])
		progress_window.update_idletasks()
		i += 1
		continue

	try:
	    fd = open(os.path.join(settings.FIRMWARE_PATH, '$tmp$', subdir, file_list[i][3]), 'wb')
	except Exception as msg:
	    progress_window.destroy()
	    showerror('Ошибка', 'Ошибка создания файла \'' + os.path.join(subdir, file_list[i][3]) + '\': {0}'.format(msg), parent = ftp_window)
	    return
	try:
	    ftp.retrbinary('RETR ' + os.path.join(file_list[i][2], file_list[i][3]), file_write)
	except Exception as msg:
	    progress_window.destroy()
	    lastdir = event.widget['text']
	    showerror('Ошибка', 'Ошибка приема файла \'' + os.path.join(subdir, file_list[i][3]) + '\': {0}'.format(msg), parent = ftp_window)
	    ftp_back_onclick()
	    return
	finally:
	    fd.close()
	i += 1

    progress_window.destroy()
    ftp_window['cursor'] = cursor
    try:
	shutil.rmtree(os.path.join(settings.FIRMWARE_PATH, event.widget['text']), False)
    except Exception as oe:
	if oe.errno == errno.ENOENT:
	    pass
	else:
	    showerror('Ошибка', 'Ошибка удаления старого каталога \'' + event.widget['text'] + '\': {0}'.format(oe), parent = ftp_window)
	    return
    try:
	shutil.move(os.path.join(settings.FIRMWARE_PATH, '$tmp$'), os.path.join(settings.FIRMWARE_PATH, event.widget['text']))
    except Exception as msg:
	showerror('Ошибка', 'Ошибка переименования временного каталога в \'' + event.widget['text'] + '\': {0}'.format(oe), parent = ftp_window)
	return

    lastdir = ''
    showinfo(' ', 'Загрузка успешно завершена', parent = ftp_window)

def ftp_back_onclick():
    global ftp_window
    global ftp_bittons
    global ftp

    ftp.close()
    ftp = None
    ftp_window.destroy()
    ftp_window = None
    del ftp_dirs[:]
    create_main_window()

def pipe_thread(firmware):
    global main_window
    global waiting_window
    global status

    pipe = open(settings.PIPE, 'w')

    if status == 'cancelled':
	pipe.close()
	print('pipe thread exited with status: ' + status)
	waiting_window.quit()
	main_window.update_idletasks()
	return

    waiting_window.quit()
    main_window.update_idletasks()
    pipe.write('FIRMWARE ' + firmware + '\n')
    pipe.close()

def waiting_window_onclick():
    global status

    status = 'cancelled'
    pipe = open(settings.PIPE, 'r')
    pipe.close()

def log_thread():
    global main_window
    global log_window
    global listbox
    global status

    while True:
	pipe = open(settings.PIPE, 'r')
	while True:
	    line = pipe.readline()
	    if line == '':
		break
	    if not line.startswith('LOG '):
		continue
	    line = line[4:].rstrip()
	    listbox.insert(END, line)
	    listbox.see(END)
	    log_window.update_idletasks()
	    if line == 'Done!' or line.startswith('ERROR: '):
		pipe.close
		sleep(10)
		if line.startswith('ERROR: '):
		    status = line
		log_window.quit()
		main_window.update_idletasks()
		return
	pipe.close()

def main_window_onclick(event):
    global main_window
    global waiting_window
    global log_window
    global listbox
    global status

    if status == 'running':
	return

    status = 'running'

    if not os.path.exists(settings.PIPE):
	os.mkfifo(settings.PIPE)
	os.chmod(settings.PIPE, os.stat(settings.PIPE).st_mode | S_IWGRP | S_IWOTH)

    waiting_window = Toplevel(main_window)
    waiting_window.overrideredirect(True)
    waiting_window.transient(main_window)
#    waiting_window.geometry('320x70')
    Label(waiting_window, text = 'Ожидание подключения терминала...', anchor = CENTER, borderwidth = 5).pack(fill = 'both')
    Button(waiting_window, text = 'Отмена', command = waiting_window_onclick).pack(side = 'bottom', pady = 5)
    waiting_window.update_idletasks()
#    waiting_window.geometry('+' + str((main_window.winfo_screenwidth() - waiting_window.winfo_width()) / 2) + '+' + str((main_window.winfo_screenheight() - waiting_window.winfo_height()) / 2))
    waiting_window.geometry(position(waiting_window))
    waiting_window.update_idletasks()

    threading.Thread(target = pipe_thread, args = [event.widget['text']]).start()

    waiting_window.mainloop()
    waiting_window.destroy()

    if status == 'cancelled':
	status = ''
	return

    log_window = Toplevel(main_window)
    log_window.transient(main_window)
    log_window.overrideredirect(True)
    scrollbar = Scrollbar(log_window, orient = VERTICAL)
    scrollbar.pack(side='right', fill = 'y')
    listbox = Listbox(log_window,
			height = 24,
			width = 64,
			background = 'black',
			foreground = '#F2F1F0',
			font = tkFont.Font(size = 10),
			selectmode = SINGLE,
			yscrollcommand = scrollbar.set)
    listbox.pack(side = 'left')
    scrollbar['command'] = listbox.yview
    log_window.update_idletasks()

    threading.Thread(target = log_thread).start()

    log_window.mainloop()
    log_window.destroy()

    if status.startswith('ERROR: '):
	err = status[7:]
	status = ''
	showerror('Ошибка', err, parent = main_window)
    else:
	status = ''
	showinfo(' ', 'Операция завершена', parent = main_window)

def create_main_window():
    global main_window

    main_window = Tk()
    tkFont.nametofont('TkDefaultFont').configure(size = 12)
    main_window.protocol('WM_DELETE_WINDOW', quit)
    main_window.title('Прошивки')
    main_window.resizable(False, False)

    i = 0
    buttons = []
    for dir in os.listdir(settings.FIRMWARE_PATH):
	if os.path.isdir(os.path.join(settings.FIRMWARE_PATH, dir)) and dir != '$tmp$':
	    buttons.append(Button(main_window, text = dir))
	    buttons[i].bind('<Button-1>', main_window_onclick)
	    buttons[i].pack(fill = 'both')
	    i += 1
    buttons.append(Button(main_window, text = 'Загрузить с сервера', command = create_ftp_window))
    buttons[len(buttons) - 1].pack(fill = 'both', pady = (10, 0))
    buttons.append(Button(main_window, text = 'Выход', command = quit))
    buttons[len(buttons) - 1].pack(fill = 'both')

    main_window.update_idletasks()
    main_window.geometry(position(main_window))
    main_window.update_idletasks()
    main_window.mainloop()

def connecting_thread():
    global connecting_window
    global ftp
    global ftp_dir
    global status

    ftp = FTP(timeout = 30)

    k = settings.FTP_SERVER.rstrip('/').find('/')
    if k >= 0:
	server = settings.FTP_SERVER[:k]
	ftp_dir = settings.FTP_SERVER[k:].rstrip('/')
    else:
	server = settings.FTP_SERVER.rstrip('/')
	ftp_dir = '/'

    try:
	ftp.connect(server)
    except Exception as msg:
	ftp = None

    if ftp is None:
	status = '{0}'.format(msg)
	connecting_window.quit()
	main_window.update_idletasks()
	return

    try:
	ftp.login(settings.FTP_USER, settings.FTP_PASSWORD)
    except Exception as msg:
	status = '{0}'.format(msg)
	connecting_window.quit()
	main_window.update_idletasks()
	return

    try:
	ftp.cwd(ftp_dir)
    except Exception as msg:
	status = '{0}'.format(msg)
	connecting_window.quit()
	main_window.update_idletasks()
	return

    try:
	ftp.dir(ftp_list_dirs)
    except Exception as msg:
	status = '{0}'.format(msg)
	connecting_window.quit()
	main_window.update_idletasks()
	return

    status = ''
    connecting_window.quit()
    main_window.update_idletasks()


def create_ftp_window():
    global ftp
    global ftp_window
    global connecting_window
    global ftp_dirs
    global main_window
    global status
    global fnt

    if status == 'running':
	return

    connecting_window = Toplevel(main_window)
    connecting_window.overrideredirect(True)
    connecting_window.transient(main_window)
    connecting_window.geometry('320x32')
    Label(connecting_window, text = 'Подключение к серверу...', anchor = CENTER, borderwidth = 5).pack(fill = 'both')
    connecting_window.update_idletasks()
    connecting_window.geometry(position(connecting_window))
    connecting_window.update_idletasks()

    status = 'running'
    threading.Thread(target = connecting_thread).start()
    connecting_window.mainloop()
    connecting_window.destroy()

    if status != '':
#	ftp_window.destroy()
	showerror('Ошибка', 'Ошибка подключения к FTP: ' + status, parent = main_window)
	status = ''
	return

    status = ''
    i = 0
    ftp_buttons = []
    ftp_window = Tk()
    while i < len(ftp_dirs):
	ftp_buttons.append(Button(ftp_window, text = ftp_dirs[i], font = fnt))
	ftp_buttons[i].bind('<Button-1>', ftp_onclick)
#	ftp_buttons[i]['font'] = fnt
	ftp_buttons[i].pack(fill = 'both')
	i += 1
    ftp_buttons.append(Button(ftp_window, font = fnt, text = 'Назад', command = ftp_back_onclick))
    ftp_buttons[i].pack(fill = 'both', pady = (10, 0))

#    main_window.quit()
    main_window.destroy()
    ftp_window.title('FTP')
    ftp_window.geometry(position(ftp_window))
    ftp_window.update_idletasks()
    ftp_window.geometry(position(ftp_window))
    ftp_window.resizable(False, False)
    ftp_window.protocol('WM_DELETE_WINDOW', ftp_back_onclick)
    ftp_window.mainloop()

def auth_onclick():
    global auth
    global main_window
    global auth_entry

    if auth_entry.get().rstrip() != settings.PASSWORD:
	sys.exit(1)

    auth.destroy()
    create_main_window()

auth = Tk()
tkFont.nametofont('TkDefaultFont').configure(size = 12)
fnt = tkFont.Font(family = 'TkDefaultFont', size = 12)
auth.title(' ')
auth.resizable(False, False)
Label(auth, text = 'Введите пароль', anchor = CENTER, borderwidth = 5).pack(fill = 'both')
auth_entry = Entry(auth, width = 16, font = fnt)
auth_entry.pack(fill = 'both')
Button(auth, text = 'Авторизация', command = auth_onclick).pack(side = 'bottom', pady = 5)
#auth.geometry('160x100')
auth.update_idletasks()
auth.geometry(position(auth))
auth.update_idletasks()
auth.mainloop()
