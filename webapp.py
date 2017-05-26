#!/usr/bin/env python

import datetime
import flask
import json
import requests
from dateutil import parser as dateparser
from flask import Flask, render_template, request
from loggingnight import LoggingNight

application = Flask('__name__')
application.config['DEBUG'] = True

@application.route('/')
def index():
    icao_identifier = request.args.get('airport')
    date = dateparser.parse(request.args.get('date', datetime.date.today().isoformat())).date()

    return render_template('index.html', icao_identifier=icao_identifier, date=date.isoformat())

@application.route('/lookup', methods=['POST'])
def lookup():
    icao_identifier = request.form['airport']
    date = dateparser.parse(request.form['date']).date()

    try:
        ln = LoggingNight(icao_identifier, date, None, None)
    except Exception as e:
        return str(e)
    except:
        flask.abort(500)

    result = dict(
        airport=icao_identifier,
        name=ln.name,
        date=date.isoformat(),
        sunset=ln.sun_set.strftime('%I:%M %p'),
        end_civil=ln.end_civil_twilight.strftime('%I:%M %p'),
        one_hour=ln.hour_after_sunset.strftime('%I:%M %p')
        )

    return json.dumps(result)
        
if __name__ == '__main__':
    application.run()
        
# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
