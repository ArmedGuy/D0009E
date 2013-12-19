# -*- coding: utf-8 -*-
from pluginbase import PluginBase

import HTMLParser
import httplib
import re

class Down(PluginBase):
	def __init__(self, bot):
		bot.registerCommand("!down", self.Down)
		bot.registerCommand("!nere", self.Down)
		bot.addHelp("down", "Usage: !down http://example.com")

	def Down(self, bot, channel, params):
		if len(params) < 1:
			return

		conn = httplib.HTTPConnection("downforeveryoneorjustme.com")
		conn.request("GET", "/%s" % params[0])
		resp = conn.getresponse()
		data = resp.read()

		search = re.search(r'<div id\=\"container\">\s+(.+)<p>.+?<\/p>.+<\/div>', data, re.S)

		if search:
			message = search.group(1)
			message = re.sub(r'<[^>]*?>', '', message)
			message = HTMLParser.HTMLParser().unescape(message)
			bot.sendMessage("PRIVMSG", channel,	"%s" % (message))
		else:
			bot.sendMessage("PRIVMSG", channel,	"No result. http://downforeveryoneorjustme.com is down.")

mainclass = Down