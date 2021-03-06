import time
import datetime
import pytz

import flask
import flask.json
from flaskext.csrf import csrf_exempt

from common import utils
from common.config import config
from www import server
from www import login


def get_notifications(cur, after=None):
	if after is None:
		cur.execute("""
			SELECT notificationkey, message, channel, subuser, useravatar, eventtime, monthcount
			FROM notification
			WHERE eventtime >= (CURRENT_TIMESTAMP - INTERVAL '2 days')
			ORDER BY notificationkey
		""")
	else:
		cur.execute("""
			SELECT notificationkey, message, channel, subuser, useravatar, eventtime, monthcount
			FROM notification
			WHERE eventtime >= (CURRENT_TIMESTAMP - INTERVAL '2 days')
			AND notificationkey > %s
			ORDER BY notificationkey
		""", (after,))
	return [dict(zip(('key', 'message', 'channel', 'user', 'avatar', 'time', 'monthcount'), row)) for row in cur.fetchall()]

@server.app.route('/notifications')
@login.with_session
@utils.with_postgres
def notifications(conn, cur, session):
	row_data = get_notifications(cur)
	for row in row_data:
		if row['time'] is None:
			row['duration'] = None
		else:
			row['duration'] = utils.nice_duration(datetime.datetime.now(row['time'].tzinfo) - row['time'], 2)
	row_data.reverse()

	if row_data:
		maxkey = row_data[0]['key']
	else:
		cur.execute("SELECT MAX(notificationkey) FROM notification")
		maxkey = cur.fetchone()[0]
		if maxkey is None:
			maxkey = -1

	return flask.render_template('notifications.html', row_data=row_data, maxkey=maxkey, session=session)

@server.app.route('/notifications/updates')
@utils.with_postgres
def updates(conn, cur):
	notifications = get_notifications(cur, int(flask.request.values['after']))
	for n in notifications:
		if n['time'] is not None:
			n['time'] = n['time'].timestamp()
	return flask.json.jsonify(notifications=notifications)

@csrf_exempt
@server.app.route('/notifications/newmessage', methods=['POST'])
@login.with_minimal_session
@utils.with_postgres
def new_message(conn, cur, session):
	if session["user"] != config["username"]:
		return flask.json.jsonify(error='apipass')
	data = {
		'message': flask.request.values['message'],
		'channel': flask.request.values.get('channel'),
		'user': flask.request.values.get('subuser'),
		'avatar': flask.request.values.get('avatar'),
		'time': float(flask.request.values['eventtime']) if 'eventtime' in flask.request.values else None,
		'monthcount': int(flask.request.values['monthcount']) if 'monthcount' in flask.request.values else None,
	}
	cur.execute("""
		INSERT INTO notification(message, channel, subuser, useravatar, eventtime, monthcount)
		VALUES (%s, %s, %s, %s, %s, %s)
		""", (
		data['message'],
		data['channel'],
		data['user'],
		data['avatar'],
		datetime.datetime.fromtimestamp(data['time'], pytz.utc) if data['time'] is not None else None,
		data['monthcount'],
	))
	utils.sse_send_event("/notifications/events", event="newmessage", data=flask.json.dumps(data))
	return flask.json.jsonify(success='OK')
