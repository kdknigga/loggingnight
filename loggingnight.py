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

def format_time(t, in_zulu):
    if in_zulu:
        return t.strftime('%I%MZ')
    else:
        return t.strftime('%I:%M %p')

def web_query(url, params=None, headers=None, exit_on_http_error=True):
    params = params or {}
    headers = headers or {}

    debug_print('Sending query to remote API %s' % url)
    debug_print('Query parameters: %s' % str(params), level=2)
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        debug_print('Final URL of response: %s' % r.url, level=2)
        debug_print('Query time: %f seconds' % total_seconds(r.elapsed), level=2)

        if exit_on_http_error:
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
parser.add_argument("-o", "--offset", type=float, help="Time zone offset in hours from Zulu, -12.0 to +14.0")
parser.add_argument("-z", "--zulu", action='store_true', help="Show times in Zulu")
args = parser.parse_args()

tz = None
if args.offset is not None and args.zulu == True:
    print('Specify either a timezone offset (-o/--offset) or Zulu time (-z/--zulu), not both')
    sys.exit(3)
elif args.zulu == True:
    tz = '0'
elif args.offset is not None:
    tz = str(args.offset)

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

date = args.date.strftime('%m/%d/%Y')
usno = {}
in_zulu = False

# Skip this query if the user specifies a time zone offset
if tz is None:
    usno = web_query(USNO_URL, params={'loc': location, 'date': date}, exit_on_http_error=False)
    debug_print(json.dumps(usno, sort_keys=True, indent=4, separators=(',', ': ')), level=2)
    in_zulu = False

# Use airport coordinates if the user wants a particular
# time zone offset or if USNO doesn't understand the
# location returned from AIRPORTINFO_URL
if not 'sundata' in usno or not usno['sundata']:
    coords = airport['latitude'] + ',' + airport['longitude']
    offset = tz if tz is not None else '0'
    usno = web_query(USNO_URL, params={'coords': coords, 'date': date, 'tz': offset})
    debug_print(json.dumps(usno, sort_keys=True, indent=4, separators=(',', ': ')), level=2)
    in_zulu = float(offset) == 0

phenTimes = dict((i['phen'], i['time']) for i in usno['sundata'])

sun_set = dateparser.parse(phenTimes['S'])
end_civil_twilight = dateparser.parse(phenTimes['EC'])

print("Night times for %s on %s" % (airport['name'], args.date.isoformat()))
if in_zulu and tz is None:
    print("  - All times are in Zulu; use --offset or --zulu to force a time zone.")
print("")
print("%s -- Sun set\nPosition lights required" % format_time(sun_set, in_zulu))
print("(14 CFR 91.209)")
print("")
print("%s -- End of civil twilight" % format_time(end_civil_twilight, in_zulu))
print("Logging of night time can start and aircraft must be night equipped")
print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
print("")
print("%s -- One hour after sun set" % format_time(sun_set + ONE_HOUR, in_zulu))
print("Must be night current to carry passengers and")
print("logging of night takeoffs and landings can start")
print("(14 CFR 61.57(b))")
