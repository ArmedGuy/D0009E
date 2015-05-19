#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket
import time
import threading
import traceback
import _thread
import random
import sys
import re
import signal
import configparser
from imp import reload

class ChannelStats:
	def __init__(self):
		self.lastMessage = time.time()
		self.names = []

class Bot:
	def __init__(self):
		self.loadSettings()

		self.channels = {}
		for chan in self.chans:
			self.channels[chan.upper()] = ChannelStats()
		self.names_cur_channel = None

		self.sock = None
		self.msg_re = re.compile(b'^(:([^ ]+))? *([^ ]+) +:?([^ ]*) *:?(.*)$')

		self.joined = False
		self.commands = {}
		self.contentCommands = {}
		self.queryCommands = {}
		self.authorized_users = []
		self.nextTalk = time.time() + 15

		self.loadPlugins()

	def loadPlugins(self):
		if "plugins" in dir(self):
			self.saveSettings()

		self.help = {}
		self.commands = {}
		self.byteCommands = {}
		self.contentCommands = {}
		self.queryCommands = {}
		self.plugins = []
		try:
			reload(__import__('plugins'))
			for i in __import__('plugins').__all__:
				try:
					plugin = __import__('plugins.%s' % i, fromlist=[None])
					reload(plugin)
					if "mainclass" in dir(plugin):
						print("Loading", i)
						obj = plugin.mainclass(self)
						if self.config.has_section(plugin.__name__):
							conflist = self.config.items(plugin.__name__)
							conf = {}
							for c in conflist:
								conf[c[0]] = c[1]
							obj.setConfig(conf)
						else:
							print("No config for plugin %s" % (plugin.__name__))
						self.plugins.append(obj)
				except:
					traceback.print_exc()
		except:
			traceback.print_exc()

	def loadSettings(self):
		self.config = configparser.RawConfigParser()
		self.config.read('d0009e.cfg')

		self.irc_server = (self.config.get('connection', 'server'),
				self.config.getint('connection', 'port'))
		self.nick = self.config.get('connection', 'nick')
		self.chans = self.config.get('connection', 'channels').split()

		admins = self.config.get('users', 'admins')
		self.users = [tuple(i.split(":")) for i in admins.split()]

	def saveSettings(self):
		self.lastSaveSettings = time.time()
		for plugin in self.plugins:
			conf = plugin.getConfigDict()
			for key in list(conf.keys()):
				self.config.set(plugin.__module__, key, conf[key])

		self.config.set('connection', 'channels', " ".join(self.chans))

		admins = " ".join([":".join(i) for i in self.users])
		self.config.set('users', 'admins', admins)

		try:
			f = open("d0009e.cfg", "w")
			self.config.write(f)
			f.close()
		except Exception as e:
			print("saveSettings failed")
			traceback.print_exc()

	def run(self):
		self.lastSaveSettings = 0

		self.running = True

		self.recvThread = RecvThread(self.sock)
		self.recvThread.start()

		self.connect()
		while self.running:
			if not self.recvThread.connected:
				print("Not connected, reconnecting")
				time.sleep(120)
				self.connect()

			try:
				self.handleCommands()
				if (time.time() - self.lastSaveSettings > 600):
					self.saveSettings()
			except:
				traceback.print_exc()

			if self.joined:
				for plugin in self.plugins:
					try:
						plugin.on_tick(self)
					except:
						traceback.print_exc()

			time.sleep(0.1)

		self.sock.close()

	def quit(self):
		print("Saving settings")
		self.saveSettings()

		print("Quitting")
		self.sendMessage("QUIT", ":SIGINT")
		self.running = False

		self.recvThread.quit = True
		self.recvThread.join()

	def connect(self):
		while True:
			try:
				self.recvThread.connecting = True
				self.joined = False
				if self.sock is not None:
					self.sock.close()

				for res in socket.getaddrinfo(self.irc_server[0], self.irc_server[1], socket.AF_UNSPEC, socket.SOCK_STREAM):
					af, socktype, proto, canonname, sa = res
					print("Connecting")
					print("af:",af)
					print("socktype:", socktype)
					print("proto:", proto)
					print("canonname:", canonname)
					print("sa:", sa)
					try:
						self.sock = socket.socket(af, socktype, proto)
					except socket.error as msg:
						print("Creating socket error", msg)
						self.sock = None
						continue
					try:
						self.sock.connect(sa)
					except socket.error as msg:
						print("Connect: Socket error", msg)
						self.sock.close()
						self.sock = None
						continue
					break
				if self.sock is None:
					print("Could not open socket")
					time.sleep(10)
					continue

				self.recvThread.sock = self.sock
				self.recvThread.connecting = False

				self.sendMessage('USER', '%s 8 *' % self.nick, 'Botten')
				self.sendMessage('NICK', self.nick)
				self.recvThread.connected = True
				return
			except Exception as e:
				traceback.print_exc()
				print("Connection failed, retrying in 10 seconds")
				time.sleep(10)

	def registerCommand(self, command, func):
		self.commands[command] = func

	def registerByteCommand(self, command, func):
		self.byteCommands[command] = func

	def registerContentCommand(self, regex, func):
		self.contentCommands[regex] = func

	def registerQueryCommand(self, command, func):
		self.queryCommands[command] = func

	def addHelp(self, command, helpMessage):
		self.help[command] = helpMessage

	def sendMessage(self, action, target, message = ""):
		if not hasattr(self.sendMessage, "history"):
			self.sendMessage.__func__.history = [] # static variable

		if type(message) != type([]):
			message = [message]

		for i,m in enumerate(message):
			# check history to see if we should do flood protection
			while True:
				# clean up history, remove everything older than 5 seconds
				self.sendMessage.__func__.history = [x for x in self.sendMessage.history if x > time.time() - 5]

				# pause if more than 10 messages was sent during the last 5 seconds
				# and no more than 1 message every 0.1 seconds
				if len(self.sendMessage.history) >= 10 or (len(self.sendMessage.history) >= 1 and self.sendMessage.history[-1] > time.time()-0.1):
					time.sleep(0.1)
				else:
					break
			# add new message to history
			self.sendMessage.history.append(time.time())


			m = str(m)
			m = m.replace("\r", "")
			m = m.replace("\n", "")

			if len(m) >= 450:
				m = "Error: Message too long"

			if m:
				# Julpynt
				tm = time.localtime()
				if action == "PRIVMSG" and tm.tm_mon == 12:
					colorstr = '\x0f\x03%02d'
					m = (colorstr % (random.randint(0,15))) + m
				buf = "%s %s :%s\r\n" % (action, target, m)
			else:
				buf = "%s %s\r\n" % (action, target)



			print("[031m>>[0m", buf, end=' ')
			while buf:
				try:
					sent = self.sock.send(buf.encode())
					buf = buf[sent:]
				except:
					traceback.print_exc()
					print("Failed to send message")
					self.recvThread.connected = False

	def sendByteMessage(self, action, target, message = b""):
		self.sendMessage(action.decode('utf-8'), target.decode('utf-8'),
				message.decode('utf-8'))

	def handleCommands(self):
		while self.recvThread.commands != []:
			line = self.recvThread.commands.pop()
			print("[032m<<[0m", line)

			m = self.msg_re.match(line)
			source, action, target, message = m.group(2, 3, 4, 5)

			command = message
			args = ""
			if b" " in message:
				command = message.split()[0].lower()
				args = message.split()[1:]

			if action.upper() == b"001" and not self.joined:
				for chan in self.chans:
					self.sendMessage("JOIN", chan)
				time.sleep(0.5)
				self.joined = True
			elif action.upper() == b"PING":
				self.sendMessage("PONG", target)
			elif action.upper() == b"ERROR":
				# Reconnect
				time.sleep(30)
				self.connect()
			elif action.upper() == b"353": # begin names
				m = re.search(b'. ([^ ]+) :?(.+)$', message)

				if not m:
					continue

				channel, names = m.group(1, 2)
				if self.names_cur_channel != channel:
					self.channels[channel.upper().decode('utf-8')].names = []
					self.names_cur_channel = channel

				# Remove prefixes
				names = re.sub(br'[^0-9a-zA-Z\\^\[\]^_`{|} -]', b'',  names)

				self.channels[channel.upper().decode('utf-8')].names.extend(names.split())

			elif action.upper() == b"366": # end names
				self.names_cur_channel = None

			elif action.upper() == b"JOIN":
				nick = source.split(b"!")[0]
				if not nick in self.channels[target.upper().decode('utf-8')].names:
					self.channels[target.upper().decode('utf-8')].names.append(nick)

			elif action.upper() == b"PART":
				nick = source.split(b"!")[0]
				self.channels[target.upper().decode('utf-8')].names.remove(nick)

			elif action.upper() == b"QUIT":
				nick = source.split(b"!")[0]

				for i in list(self.channels.values()):
					if nick in i.names:
						i.names.remove(nick)

			elif action.upper() == b"KICK":
				nick = message.split()[0]
				self.channels[target.upper().decode('utf-8')].names.remove(nick)

			elif action.upper() == b"NICK":
				nick = source.split(b"!")[0]
				newnick = target

				for i in list(self.channels.values()):
					if nick in i.names:
						i.names.remove(nick)
						i.names.append(newnick)
			elif command.upper() == b"!RELOAD" and args == "":
				if target.upper() == self.nick.upper():
					target = source.split(b"!")[0]
				if not source in self.authorized_users:
					self.sendByteMessage(b"PRIVMSG", target,
							b"reload: Access denied")
					continue

				print("Reloading")
				self.loadPlugins()
				self.sendByteMessage(b"PRIVMSG", target, b"reload successful")
			elif action.upper() == b"PRIVMSG":
				if target.upper() == self.nick.encode().upper():
					if message.upper() == b"\001VERSION\001":
						nick = source.split(b"!")[0].lstrip(b":")
						if nick[0] == b":": nick = nick[1:]
						self.sendByteMessage(b"NOTICE", nick,
							"\001VERSION En bot i sina bästa år\001".encode())
					elif message.upper() == b"\001TIME\001":
						nick = source.split(b"!")[0].lstrip(b":")
						self.sendByteMessage(b"NOTICE", nick,
							"\001Time 13:37 - The time of leet\001".encode())
					elif command.upper() == b"AUTH":
						nick, userhost = source.split(b"!")
						nick = nick.decode('utf-8')
						if len(args) >= 2:
							args[0] = args[0].decode('utf-8')
							args[1] = args[1].decode('utf-8')

						if len(args) >= 2 and (args[0].lower(), args[1]) in self.users:
							self.authorized_users.append(source)

							self.sendMessage("NOTICE", nick,
									"You are now authenticated as %s" % (args[0]))
						else:
							self.sendMessage(b"NOTICE", nick,
									"Wrong username or password")
					else:
						nick, userhost = source.split(b"!")
						try:
							if command in self.queryCommands:
								strargs = [x.decode('utf-8') for x in args]
								_thread.start_new_thread(self.queryCommands[command],
									(self, nick.decode('utf-8'), args))
							if command in self.byteCommands:
								_thread.start_new_thread(self.byteCommands[command],
									(self, nick, args))
							if command in self.commands:
								strargs = [x.decode('utf-8') for x in args]
								_thread.start_new_thread(self.commands[command.decode('utf-8')],
									(self, nick.decode('utf-8'), strargs))
						except Exception as e:
							traceback.print_exc()
							self.sendByteMessage(b"PRIVMSG", target, b"Error!!")

				elif target.upper().decode('utf-8') in self.channels:
					chanstats = self.channels[target.upper().decode('utf-8')]
					chanstats.lastMessage = time.time()

					try:
						strcommand = None
						try:
							strcommand = command.decode('utf-8')
						except:
							pass

						if command in self.byteCommands:
							_thread.start_new_thread(self.byteCommands[command],
								(self, target, args))
						elif strcommand and strcommand in self.commands:
							strargs = [x.decode('utf-8') for x in args]
							_thread.start_new_thread(self.commands[strcommand],
								(self, target.decode('utf-8'), strargs))
						else:
							strmessage = None
							try:
								strmessage = message.decode('utf-8')
							except:
								pass
							if strmessage:
								for contentCmd in self.contentCommands:
									if re.search(contentCmd, strmessage):
										_thread.start_new_thread(
												self.contentCommands[contentCmd],
												(self, target.decode('utf-8'),
													strmessage))
										break

					except Exception as e:
						traceback.print_exc()
						self.sendByteMessage(b"PRIVMSG", target, b"Error!!")

class RecvThread(threading.Thread):
	def __init__(self, sock):
		self.sock = sock
		self.quit = False
		self.connected = False
		self.connecting = True
		self.commands = []
		threading.Thread.__init__(self)

	def run(self):
		buffer = b""
		socket.setdefaulttimeout(30)
		endpoint_notconnected_count = 0
		while not self.quit:
			if self.connecting:
				time.sleep(0.1)
				continue # wait until connected before doing anything
			if self.sock is None:
				self.connected = False
				continue
			try:
				buffer += self.sock.recv(1024)
				commands = buffer.split(b"\r\n")[:-1]
				buffer = buffer[buffer.rfind(b"\r\n")+2:]
				for command in commands:
					self.addCommand(command)
				endpoint_notconnected_count = 0
			except socket.timeout:
				print("Timeout")
				#self.connected = False
			except socket.error as xxx_todo_changeme:
				(value, message) = xxx_todo_changeme.args
				if value == 103: # software caused connection reset
					print(value, message)
					self.connected = False
				elif value == 104: # connection reset by peer
					print(value, message)
					self.connected = False
				elif value == 107: # transport endpoint not connected
					print(value, message)
					endpoint_notconnected_count += 1
					if endpoint_notconnected_count > 20:
						self.connected = False
						endpoint_notconnected_count = 0
					time.sleep(2)
				elif value == 110: # connection timed out
					print(value, message)
					print("Sleeping 10 seconds, then retrying")
					time.sleep(10)
					self.connected = False
				elif value == 9: # Bad socket descriptor
					print(value, message)
					print("Sleeping 10 seconds, then retrying")
					time.sleep(10)
					self.connected = False
				else:
					traceback.print_exc()
					print("else:", value, message)
					time.sleep(0.1)
			except Exception as e:
				print("other exception")
				traceback.print_exc()
				time.sleep(0.1)

	def addCommand(self, command):
		self.commands.append(command)

b = Bot()

def keyint(signum, frame):
	print("Received signal:", signum)
	b.quit()

signal.signal(signal.SIGINT, keyint)

b.run()
