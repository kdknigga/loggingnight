#!/usr/bin/env python

import os
import datetime
import flask
import json
import schedule
import threading
import time
from dateutil import parser as dateparser
from flask import Flask, render_template, request, Response
from loggingnight import LoggingNight

application = Flask('__name__')

dev_mode = os.environ.get('LOGGINGNIGHT_DEV', 'false')
if dev_mode == "true":
    import pprint
    application.config['DEBUG'] = True
else:
    application.config['DEBUG'] = False

@application.before_first_request
def enable_housekeeping(run_interval=3600):
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @staticmethod
        def run():
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(run_interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()

    schedule.every(1).hour.do(LoggingNight.garbage_collect_cache)

@application.route('/')
def index():
    icao_identifier = request.args.get('airport')

    try:
        date = dateparser.parse(request.args.get('date', datetime.date.today().isoformat())).date()
    except ValueError:
        date = datetime.date.today()

    return render_template('index.html', dev_mode=dev_mode, icao_identifier=icao_identifier, date=date.isoformat())

@application.route('/lookup', methods=['POST'])
def lookup():
    icao_identifier = request.form['airport']

    try:
        date = dateparser.parse(request.form['date']).date()
    except ValueError:
        return "Unable to understand date %s" % request.form['date'], 400

    try:
        ln = LoggingNight(icao_identifier, date, try_cache=True)
    except Exception as e:
        return str(e), 400
    except:
        flask.abort(500)

    if dev_mode == "true":
        result = dict(
            airport=icao_identifier,
            name=ln.name,
            date=date.isoformat(),
            sunset=ln.sun_set.strftime('%I:%M %p'),
            end_civil=ln.end_civil_twilight.strftime('%I:%M %p'),
            one_hour=ln.hour_after_sunset.strftime('%I:%M %p'),
            airport_debug=pprint.pformat(ln.airport, indent=4),
            usno_debug=pprint.pformat(ln.usno, indent=4)
            )
    else:
        result = dict(
            airport=icao_identifier,
            name=ln.name,
            date=date.isoformat(),
            sunset=ln.sun_set.strftime('%I:%M %p'),
            end_civil=ln.end_civil_twilight.strftime('%I:%M %p'),
            one_hour=ln.hour_after_sunset.strftime('%I:%M %p')
            )

    return json.dumps(result)

@application.route('/displayCache', methods=['GET'])
def displayCache():
    if LoggingNight.enable_cache():
        return Response(json.dumps(list((str(timestamp), url) for timestamp, url in LoggingNight.get_cache_entries())), mimetype='application/json')
    else:
        return False
        
if __name__ == '__main__':
    application.run()
        
# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
