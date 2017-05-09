#!/usr/bin/python

from __future__ import print_function
import argparse
import datetime
import json
import requests
import sys
from dateutil import parser as dateparser

airportinfo_url = 'http://www.airport-data.com/api/ap_info.json'
usno_url = 'http://api.usno.navy.mil/rstt/oneday'
one_hour = datetime.timedelta(hours=1)

def debug_print(string, level=1):
	if args.debug >= level:
		print(string, file=sys.stderr)

def makedate(datestring):
	return dateparser.parse(datestring).date()

def web_query(url, params={}, headers={}):
	debug_print('Sending query to remote API %s' % url)
	debug_print('Query parameters: %s' % str(params), level=2)
	try:
		r = requests.get(url, headers=headers, params=params, timeout=10)
		debug_print('Final URL of response: %s' % r.url, level=2)
		debug_print('Query time: %f seconds' % r.elapsed.total_seconds(), level=2)
		r.raise_for_status()

	except requests.exceptions.Timeout:
		print('Connecting to %s timed out' % url)
		sys.exit(1)

	except requests.exceptions.HTTPError:
		print('%s returned %d (%s) trying to do an API lookup' % (url, r.status_code, r.reason))
		sys.exit(2)

	return r.json()

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--airport", help="ICAO code for the airport", required=True)
parser.add_argument("-d", "--date", type=makedate, default=datetime.date.today().isoformat(), help="Date of the flight")
parser.add_argument("-D", "--debug", action='count')
args = parser.parse_args()

airport = web_query(airportinfo_url, params={'icao': args.airport})
debug_print(json.dumps(airport, sort_keys=True, indent=4, separators=(',', ': ')), level=2)

if not 'location' in airport or not airport['location']:
	print('Unable to find airport %s' % args.airport)
	print('Check that you are using the ICAO code for that airport (KDPA, not DPA)')
	print("If the airport doesn't have an ICAO code, use a nearby airport with one")
	sys.exit(3)

# The split on / is required for airport like KDPA where
# the location is "Chicago / west Chicago, IL"
location = airport['location'].split('/')[-1]

usno = web_query(usno_url, params={'loc': location, 'date': args.date.strftime('%m/%d/%Y')})
debug_print(json.dumps(usno, sort_keys=True, indent=4, separators=(',', ': ')), level=2)

phenTimes = dict((i['phen'], i['time']) for i in usno['sundata'])

sun_set = dateparser.parse(phenTimes['S'])
end_civil_twilight = dateparser.parse(phenTimes['EC'])

print("Night times for %s on %s" % (airport['name'], args.date.isoformat()))
print("")
print("%s -- Sun set\nPosition lights required" % sun_set.strftime('%I:%M %p'))
print("(14 CFR 91.209)")
print("")
print("%s -- End of civil twilight\nLogging of night time can start and aircraft must be night equipped" % end_civil_twilight.strftime('%I:%M %p'))
print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
print("")
print("%s -- One hour after sun set\nMust be night current to carry passengers and\nlogging of night takeoffs and landings can start" % (sun_set + one_hour).strftime('%I:%M %p'))
print("(14 CFR 61.57(b))")
