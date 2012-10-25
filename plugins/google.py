# -*- coding: utf-8 -*-
from pluginbase import PluginBase

import urllib
from urllib import FancyURLopener
import random
import re

class UrlOpener(FancyURLopener):
	version = "D0009E/0.1"

class Google(PluginBase):
	def __init__(self, bot):
		bot.registerCommand("!google", self.handleGoogle)
		bot.addHelp("google", "Usage: !google search terms")

	# Send a link back to the user via IRC. If possible, use the !link shortener
	def reportLink(self, bot, channel, url, title):
		if "!link" in bot.commands:
			bot.commands["!link"](bot, channel, [url])
		else:
			bot.sendMessage("PRIVMSG", channel, "%s [ %s ]" % (title, url))

	def handleGoogle(self, bot, channel, params):
		url = "http://www.google.se/search?q=%s&ie=utf-8&oe=utf-8&rls=en" % \
				(urllib.quote_plus(" ".join(params)))
		title = "No Title"

		try:
			file = UrlOpener().open(url)
		except IOError:
			bot.sendMessage("PRIVMSG", channel, "Error opening url.")
			return

		data = file.read(1024*1024)
		file.close()

		# What you see in your browser isn't what google sends over the socket.
		# Here's a regex that works as of 2012-10-24
		m = re.search('<a href="\/url\?q=(.*?)&amp;.*?>(.*?)<\/a>', data)
		if m:
			title = re.sub('<.+?>', '', m.group(2))
			url = urllib.unquote(m.group(1));

		self.reportLink(bot, channel, url, title)

mainclass = Google
