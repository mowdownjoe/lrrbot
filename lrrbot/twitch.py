import json

from common import utils
from common.config import config
from lrrbot import storage


def get_info(username=None, use_fallback=True):
	"""
	Get the Twitch info for a particular user or channel.

	Defaults to the stream channel if not otherwise specified.

	For response object structure, see:
	https://github.com/justintv/Twitch-API/blob/master/v3_resources/channels.md#example-response

	May throw exceptions on network/Twitch error.
	"""
	if username is None:
		username = config['channel']

	# Attempt to get the channel data from /streams/channelname
	# If this succeeds, it means the channel is currently live
	res = utils.http_request("https://api.twitch.tv/kraken/streams/%s" % username)
	data = json.loads(res)
	channel_data = data.get('stream') and data['stream'].get('channel')
	if channel_data:
		channel_data['live'] = True
		channel_data['viewers'] = data['stream'].get('viewers')
		channel_data['stream_created_at'] = data['stream'].get('created_at')
		return channel_data

	if not use_fallback:
		return None

	# If that failed, it means the channel is offline
	# Ge the channel data from here instead
	res = utils.http_request("https://api.twitch.tv/kraken/channels/%s" % username)
	channel_data = json.loads(res)
	channel_data['live'] = False
	return channel_data

def get_game(name, all=False):
	"""
	Get the game information for a particular game.

	For response object structure, see:
	https://github.com/justintv/Twitch-API/blob/master/v3_resources/search.md#example-response-1	

	May throw exceptions on network/Twitch error.
	"""
	search_opts = {
		'query': name,
		'type': 'suggest',
		'live': 'false',
	}
	res = utils.http_request("https://api.twitch.tv/kraken/search/games", search_opts)
	res = json.loads(res)
	if all:
		return res['games']
	else:
		for game in res['games']:
			if game['name'] == name:
				return game
		return None

def get_game_playing(username=None):
	"""
	Get the game information for the game the stream is currently playing
	"""
	channel_data = get_info(username, use_fallback=False)
	if not channel_data or not channel_data['live']:
		return None
	if channel_data.get('game') is not None:
		return get_game(name=channel_data['game'])
	return None

def get_subscribers(channel=None, count=5, offset=None, latest=True):
	if channel is None:
		channel = config['channel']
	if channel not in storage.data['twitch_oauth']:
		return None
	headers = {
		"Authorization": "OAuth %s" % storage.data['twitch_oauth'][channel],
	}
	data = {
		"limit": count,
		"direction": "desc" if latest else "asc",
	}
	if offset is not None:
		data['offset'] = offset
	res = utils.http_request("https://api.twitch.tv/kraken/channels/%s/subscriptions" % channel, headers=headers, data=data)
	subscriber_data = json.loads(res)
	return [
		(sub['user']['display_name'], sub['user'].get('logo'), sub['created_at'])
		for sub in subscriber_data['subscriptions']
	]
