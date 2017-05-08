#!/usr/bin/python

import argparse
import json
import requests
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--airport", help="ICAO code for the airport")
args = parser.parse_args()

airportinfo_url = 'http://www.airport-data.com/api/ap_info.json'
usno_url = 'http://api.usno.navy.mil/rstt/oneday'

airport_get_data = {'icao': args.airport}

airport_r = requests.get(airportinfo_url, params=airport_get_data, timeout=10)
airport_r.raise_for_status()

print json.dumps(airport_r.json(), sort_keys=True, indent=4, separators=(',', ': '))

location = airport_r.json()['location'].split('/')[-1]
usno_get_data = {'loc': location, 'date': 'today'}
#usno_get_data = {'loc': 'west Chicago, IL', 'date': 'today'}

usno_r = requests.get(usno_url, params=usno_get_data, timeout=10)
usno_r.raise_for_status()

print json.dumps(usno_r.json(), sort_keys=True, indent=4, separators=(',', ': '))
