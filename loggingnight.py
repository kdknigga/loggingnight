#!/usr/bin/env python

from __future__ import print_function
import datetime
import requests
from dateutil import parser as dateparser

def makedate(datestring):
    return dateparser.parse(datestring).date()

class LoggingNight(object):
    AIRPORTINFO_URL = 'http://www.airport-data.com/api/ap_info.json'
    USNO_URL = 'http://api.usno.navy.mil/rstt/oneday'
    ONE_HOUR = datetime.timedelta(hours=1)

    def web_query(self, url, params=None, headers=None):
        params = params or {}
        headers = headers or {}
        stats = {}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        stats['final_url'] = r.url
        stats['query_time'] = r.elapsed.total_seconds()
        stats['status_code'] = r.status_code
        stats['status_text'] = r.reason
        r.raise_for_status()

        return {'query_stats': stats, 'response': r.json()}

    class LocationException(IOError):
        """An error occured finding airport location information"""

    class AstronomicalException(IOError):
        """An error occured finding astronomical information"""

    def __init__(self, icao, date):
        self.icao = icao
        self.date = date

        self.airport = self.web_query(self.AIRPORTINFO_URL, params={'icao': self.icao})
        if not 'response' in self.airport or not 'location' in self.airport['response'] \
        or not self.airport['response']['location']:
            raise self.LocationException('Unable to find location information for %s' % self.icao)

        # The split on / is required for airport like KDPA where
        # the location is "Chicago / west Chicago, IL"
        self.location = self.airport['response']['location'].split('/')[-1]

        self.usno = self.web_query(self.USNO_URL, params={'loc': self.location, 'date': self.date.strftime('%m/%d/%Y')})
        if not 'response' in self.usno or not 'sundata' in self.usno['response']:
            raise self.AstronomicalException('Unable to find sun data')

        self.phenTimes = dict((i['phen'], i['time']) for i in self.usno['response']['sundata'])

        self.name = self.airport['response']['name']
        self.sun_set = dateparser.parse(self.phenTimes['S'])
        self.end_civil_twilight = dateparser.parse(self.phenTimes['EC'])
        self.hour_after_sunset = self.sun_set + self.ONE_HOUR

if __name__ == "__main__":
    import argparse
    import datetime
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--airport", help="ICAO code for the airport", required=True)
    parser.add_argument("-d", "--date", type=makedate,
                        default=datetime.date.today().isoformat(), help="Date of the flight")
    parser.add_argument("-D", "--debug", action='count')
    args = parser.parse_args()

    ln = LoggingNight(args.airport, args.date)

    print("Night times for %s on %s" % (ln.name, ln.date.isoformat()))
    print("")
    print("%s -- Sun set\nPosition lights required" % ln.sun_set.strftime('%I:%M %p'))
    print("(14 CFR 91.209)")
    print("")
    print("%s -- End of civil twilight" % ln.end_civil_twilight.strftime('%I:%M %p'))
    print("Logging of night time can start and aircraft must be night equipped")
    print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
    print("")
    print("%s -- One hour after sun set" % ln.hour_after_sunset.strftime('%I:%M %p'))
    print("Must be night current to carry passengers and")
    print("logging of night takeoffs and landings can start")
    print("(14 CFR 61.57(b))")

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
