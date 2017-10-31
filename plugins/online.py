# -*- coding: utf-8 -*-
from .pluginbase import PluginBase

import urllib.request, urllib.error, urllib.parse
import re

class Online(PluginBase):
	def __init__(self, bot):
		bot.registerCommand("!online", self.handleOnline)
		bot.addHelp("online", "Usage: !online [<server>]")

	def handleOnline(self, bot, channel, params):
		bot.sendMessage("PRIVMSG", channel, self.getOnline)
    
	def getOnline(self, server):
		try:
			url = "http://www.ludd.ltu.se/~armedguy/users_online.php"
			f = urllib.request.urlopen(url)
			data = f.read().decode('utf-8')
			json = json.reads(data)
			if server not in json:
				return "Server not found"
			else:
				return "Users online on %s: %s" % (server, ", ".join(json[server]))
		except:
			return "Could not get online users"
            

mainclass = Online
