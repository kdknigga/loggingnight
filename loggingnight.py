#!/usr/bin/env python

from __future__ import print_function
import argparse
import datetime
import json
import sys
import requests
from dateutil import parser as dateparser

AIRPORTINFO_URL = 'http://www.airport-data.com/api/ap_info.json'
USNO_URL = 'http://api.usno.navy.mil/rstt/oneday'
ONE_HOUR = datetime.timedelta(hours=1)

def debug_print(string, level=1):
    if args.debug >= level:
        print(string, file=sys.stderr)

def total_seconds(td):
    if hasattr(td, 'total_seconds'):
        return td.total_seconds()
    else:
        # timedelta has no total_seconds method in Python 2.6
        sec = td.seconds + td.days * 24 * 60 * 60
        return (float(td.microseconds) / 10**6) + sec

def makedate(datestring):
    return dateparser.parse(datestring).date()

def web_query(url, params=None, headers=None):
    params = params or {}
    headers = headers or {}

    debug_print('Sending query to remote API %s' % url)
    debug_print('Query parameters: %s' % str(params), level=2)
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        debug_print('Final URL of response: %s' % r.url, level=2)
        debug_print('Query time: %f seconds' % total_seconds(r.elapsed), level=2)
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
parser.add_argument("-d", "--date", type=makedate,
                    default=datetime.date.today().isoformat(), help="Date of the flight")
parser.add_argument("-D", "--debug", action='count')
args = parser.parse_args()

airport = web_query(AIRPORTINFO_URL, params={'icao': args.airport})
debug_print(json.dumps(airport, sort_keys=True, indent=4, separators=(',', ': ')), level=2)

if not 'location' in airport or not airport['location']:
    print('Unable to find airport %s' % args.airport)
    print('Check that you are using the ICAO code for that airport (KDPA, not DPA)')
    print("If the airport doesn't have an ICAO code, use a nearby airport with one")
    sys.exit(3)

# The split on / is required for airport like KDPA where
# the location is "Chicago / west Chicago, IL"
location = airport['location'].split('/')[-1]

usno = web_query(USNO_URL, params={'loc': location, 'date': args.date.strftime('%m/%d/%Y')})
debug_print(json.dumps(usno, sort_keys=True, indent=4, separators=(',', ': ')), level=2)

phenTimes = dict((i['phen'], i['time']) for i in usno['sundata'])

sun_set = dateparser.parse(phenTimes['S'])
end_civil_twilight = dateparser.parse(phenTimes['EC'])

print("Night times for %s on %s" % (airport['name'], args.date.isoformat()))
print("")
print("%s -- Sun set\nPosition lights required" % sun_set.strftime('%I:%M %p'))
print("(14 CFR 91.209)")
print("")
print("%s -- End of civil twilight" % end_civil_twilight.strftime('%I:%M %p'))
print("Logging of night time can start and aircraft must be night equipped")
print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
print("")
print("%s -- One hour after sun set" % (sun_set + ONE_HOUR).strftime('%I:%M %p'))
print("Must be night current to carry passengers and")
print("logging of night takeoffs and landings can start")
print("(14 CFR 61.57(b))")
