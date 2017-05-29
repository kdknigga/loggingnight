#!/usr/bin/env python

from __future__ import print_function
import datetime
import re
import requests
from dateutil import parser as dateparser

def makedate(datestring):
    return dateparser.parse(datestring).date()

class LoggingNight(object):
    """Provide an ICAO code and a date and get what the FAA considers night"""

    AIRPORTINFO_URL = 'http://www.airport-data.com/api/ap_info.json'
    USNO_URL = 'http://api.usno.navy.mil/rstt/oneday'
    ONE_HOUR = datetime.timedelta(hours=1)

    @staticmethod
    def total_seconds(td):
        if hasattr(td, 'total_seconds'):
            return td.total_seconds()
        else:
            # timedelta has no total_seconds method in Python 2.6
            sec = td.seconds + td.days * 24 * 60 * 60
            return (float(td.microseconds) / 10**6) + sec

    @staticmethod
    def fix_location(location):
        # The split on / is required for airport like KDPA where
        # the location is "Chicago / west Chicago, IL"
        location = location.split('/')[-1]
    
        # KSTL and KSUS have location "St Louis, MO" but USNO wants
        # Saint abbreviated with the dot, i.e., "St."
        st_no_dot = re.compile(r'^St(?!\.)\b')
        location = st_no_dot.sub('St.', location)
        return location

    def web_query(self, url, params=None, headers=None, exit_on_http_error=True):
        params = params or {}
        headers = headers or {}
        stats = {}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        stats['final_url'] = r.url
        stats['query_time'] = self.total_seconds(r.elapsed)
        stats['status_code'] = r.status_code
        stats['status_text'] = r.reason

        if exit_on_http_error:
            r.raise_for_status()

        return {'query_stats': stats, 'response': r.json()}

    class LocationException(IOError):
        """An error occured finding airport location information"""

    class AstronomicalException(IOError):
        """An error occured finding astronomical information"""

    def __init__(self, icao, date, zulu, offset):
        self.icao = icao
        self.date = date
        self.zulu = zulu
        self.offset = offset

        self.tz = None
        if self.offset is not None and self.zulu == True:
            raise ValueError('Specify either a timezone offset or Zulu time, not both')
        elif self.zulu == True:
            self.tz = '0'
        elif self.offset is not None:
            self.tz = str(self.offset)

        self.airport = self.web_query(self.AIRPORTINFO_URL, params={'icao': self.icao})
        if not 'response' in self.airport or not 'location' in self.airport['response'] \
        or not self.airport['response']['location']:
            raise self.LocationException('Unable to find location information for %s.  Make sure you\'re using an ICAO identifier (KDPA vs DPA)' % self.icao)

        self.location = self.fix_location(self.airport['response']['location'])

        self.usno = {}
        self.in_zulu = False

        if self.tz is None:
            self.usno = self.web_query(self.USNO_URL, params={'loc': self.location, 'date': self.date.strftime('%m/%d/%Y')}, exit_on_http_error=False)
            self.in_zulu = False

        if not 'response' in self.usno or not 'sundata' in self.usno['response']:
            # The USNO hasn't recognized our location, probably.  Try again with lat+long.
            # Lookups with lat+long require a timezone
            self.location = self.airport['response']['latitude'] + ',' + self.airport['response']['longitude']
            self.offset = self.tz if self.tz is not None else '0'
            self.usno = self.web_query(self.USNO_URL, params={'coords': self.location, 'date': self.date.strftime('%m/%d/%Y'), 'tz': self.offset})
            self.in_zulu = float(self.offset) == 0

        if not 'response' in self.usno or not 'sundata' in self.usno['response']:
            raise self.AstronomicalException('Unable to find sun data for %s' % self.location)

        self.phenTimes = dict((i['phen'], i['time']) for i in self.usno['response']['sundata'])

        self.name = self.airport['response']['name']
        self.sun_set = dateparser.parse(self.phenTimes['S'])
        self.end_civil_twilight = dateparser.parse(self.phenTimes['EC'])
        self.hour_after_sunset = self.sun_set + self.ONE_HOUR

if __name__ == "__main__":
    import argparse
    import datetime
    import pprint
    import sys

    def debug_print(string, level=1):
        if args.debug >= level:
            print(string, file=sys.stderr)

    def format_time(t, in_zulu):
        if in_zulu:
            return t.strftime('%I%MZ')
        else:
            return t.strftime('%I:%M %p')

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--airport", help="ICAO code for the airport", required=True)
    parser.add_argument("-d", "--date", type=makedate,
                        default=datetime.date.today().isoformat(), help="Date of the flight")
    parser.add_argument("-D", "--debug", action='count')
    parser.add_argument("-o", "--offset", type=float, help="Time zone offset in hours from Zulu, -12.0 to +14.0")
    parser.add_argument("-z", "--zulu", action='store_true', help="Show times in Zulu")
    args = parser.parse_args()

    ln = LoggingNight(args.airport, args.date, args.zulu, args.offset)

    debug_print("Airport debug info:", level=2)
    debug_print(pprint.pformat(ln.airport, indent=4), level=2)
    debug_print("", level=2)
    debug_print("US Naval Observatory debug info:", level=2)
    debug_print(pprint.pformat(ln.usno, indent=4), level=2)

    print("Night times for %s on %s" % (ln.name, ln.date.isoformat()))
    if ln.in_zulu and ln.tz is None:
        print("  - All times are in Zulu; use --offset or --zulu to force a time zone.")
    print("")
    print("%s -- Sun set\nPosition lights required" % format_time(ln.sun_set, ln.in_zulu))
    print("(14 CFR 91.209)")
    print("")
    print("%s -- End of civil twilight" % format_time(ln.end_civil_twilight, ln.in_zulu))
    print("Logging of night time can start and aircraft must be night equipped")
    print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
    print("")
    print("%s -- One hour after sun set" % format_time(ln.hour_after_sunset, ln.in_zulu))
    print("Must be night current to carry passengers and")
    print("logging of night takeoffs and landings can start")
    print("(14 CFR 61.57(b))")

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
