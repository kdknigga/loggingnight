#!/usr/bin/env python3

import datetime
import logging
import os
import re
from sys import modules
from zoneinfo import ZoneInfo

import requests
from dateutil import parser as dateparser
from timezonefinder import TimezoneFinder

loglevel = os.environ.get("LN_LOGLEVEL", "warning")
loglevel_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

log = logging.getLogger("loggingnight-core")

if loglevel in loglevel_map:
    logging.basicConfig(
        level=loglevel_map[loglevel], format="%(levelname)s: %(message)s"
    )

try:
    import requests_cache

    log.info("Loaded requests_cache")
except ImportError:
    log.info("requests_cache unavailable")
    pass

tf = TimezoneFinder()
log.info("Using compiled TimezoneFinder: %s", str(TimezoneFinder.using_clang_pip()))
log.info("Using numba with TimezoneFinder: %s", str(TimezoneFinder.using_numba()))


def makedate(datestring):
    return dateparser.parse(datestring).date()


def total_seconds(td):
    if hasattr(td, "total_seconds"):
        return td.total_seconds()
    else:
        # timedelta has no total_seconds method in Python 2.6
        sec = td.seconds + td.days * 24 * 60 * 60
        return (float(td.microseconds) / 10**6) + sec


def seconds_to_degrees(seconds: str) -> float:
    """Takes decimal seconds with hemisphere abbreviation and returns signed decimal degrees
    174066.6241N -> 48.351840028"""
    hemisphere = seconds[-1]
    if hemisphere == "N" or hemisphere == "E":
        sign = 1
    elif hemisphere == "S" or hemisphere == "W":
        sign = -1
    else:
        raise ValueError(f"Invalid hemisphere abbreviation '{hemisphere}'")

    return (float(seconds[0:-1]) / 3600) * sign


def web_query(url, params=None, headers=None, verify_ssl=False):
    params = params or {}
    headers = headers or {}
    stats = {}

    r = requests.get(url, headers=headers, params=params, timeout=10, verify=verify_ssl)
    stats["final_url"] = r.url
    stats["query_time"] = total_seconds(r.elapsed)
    stats["status_code"] = r.status_code
    stats["status_text"] = r.reason
    stats["headers"] = r.headers
    if hasattr(r, "from_cache"):
        stats["from_cache"] = r.from_cache

    try:
        return {"query_stats": stats, "response": r.json()}
    except:
        return {"query_stats": stats}


class StarfieldProvider(object):
    """Use Starfield to calculate astronomical information"""

    from skyfield import almanac, api

    @staticmethod
    def nearest_minute(dt):
        return (dt + datetime.timedelta(seconds=30)).replace(second=0, microsecond=0)

    def __init__(self, airport=None, date=None, tz=None):
        self.airport = airport
        self.date = date
        self.usno = {"message": "Using the Starfield provider"}

    def lookup(self):
        log.info("Using the Starfield provider")
        ts = self.api.load.timescale()
        e = self.api.load("de421.bsp")

        lat_degs = seconds_to_degrees(self.airport["response"]["latitude_secs"])
        long_degs = seconds_to_degrees(self.airport["response"]["longitude_secs"])

        location = self.api.Topos(lat_degs, long_degs)

        tzstring = tf.timezone_at(
            lng=location.longitude.degrees, lat=location.latitude.degrees
        )

        if not tzstring:
            log.info("Unable to find timezone string, using UTC")
            tz = ZoneInfo("UTC")
            in_zulu = True
        else:
            tz = ZoneInfo(tzstring)
            in_zulu = False

        t0 = ts.utc(
            datetime.datetime.combine(
                self.date, datetime.time(hour=0, minute=0), tzinfo=tz
            )
        )
        t1 = ts.utc(
            datetime.datetime.combine(
                self.date, datetime.time(hour=23, minute=59), tzinfo=tz
            )
        )

        t, _ = self.almanac.find_discrete(
            t0, t1, self.almanac.dark_twilight_day(e, location)
        )

        start_civil_twilight = self.nearest_minute(t[2].utc_datetime()).astimezone(tz)
        sunrise = self.nearest_minute(t[3].utc_datetime()).astimezone(tz)
        sunset = self.nearest_minute(t[4].utc_datetime()).astimezone(tz)
        end_civil_twilight = self.nearest_minute(t[5].utc_datetime()).astimezone(tz)

        return {
            "sun_rise": sunrise,
            "sun_set": sunset,
            "start_civil_twilight": start_civil_twilight,
            "end_civil_twilight": end_civil_twilight,
            "in_zulu": in_zulu,
        }


class USNOProvider(object):
    """Use the USNO API server for astronomical information"""

    USNO_URL = "https://aa.usno.navy.mil/api/rstt/oneday"

    class AstronomicalException(IOError):
        """An error occured finding astronomical information"""

    def __init__(self, airport=None, date=None, tz=None):
        self.airport = airport
        self.date = date
        self.tz = tz
        self.usno = {}

    def lookup(self):
        log.info("Using the USNO provider")

        lat_degs = seconds_to_degrees(self.airport["response"]["latitude_secs"])
        long_degs = seconds_to_degrees(self.airport["response"]["longitude_secs"])
        location = str(lat_degs) + "," + str(long_degs)

        if self.tz is None:
            tzstring = tf.timezone_at(lng=long_degs, lat=lat_degs)

            if not tzstring:
                log.info("Unable to find timezone string, using UTC")
                offset = 0
                in_zulu = True
            else:
                noon = datetime.time(hour=12, minute=0, second=0)
                utc_datetime = datetime.datetime.combine(
                    date=self.date, time=noon, tzinfo=ZoneInfo("UTC")
                )
                local_datetime = datetime.datetime.combine(
                    date=self.date, time=noon, tzinfo=ZoneInfo(tzstring)
                )
                offset = (utc_datetime - local_datetime) / datetime.timedelta(hours=1)
                in_zulu = False
        else:
            offset = self.tz
            if offset == 0:
                in_zulu = True
            else:
                in_zulu = False

        self.usno = web_query(
            self.USNO_URL,
            params={
                "ID": "lndo",
                "coords": location,
                "date": self.date.strftime("%Y-%m-%d"),
                "tz": offset,
            },
        )

        if not self.usno["query_stats"]["status_code"] in {200, 304}:
            raise self.AstronomicalException(
                "The USNO seems to be having problems: %d %s"
                % (
                    self.usno["query_stats"]["status_code"],
                    self.usno["query_stats"]["status_text"],
                )
            )

        if not "response" in self.usno or (
            not "properties" in self.usno["response"]
            and not "data" in self.usno["response"]["properties"]
            and not "sundata" in self.usno["response"]["properties"]["data"]
        ):
            raise self.AstronomicalException(
                "Unable to find sun data for %s" % location
            )

        phenTimes = dict(
            (i["phen"], i["time"])
            for i in self.usno["response"]["properties"]["data"]["sundata"]
        )
        sun_rise = dateparser.parse(phenTimes["Rise"])
        sun_set = dateparser.parse(phenTimes["Set"])
        start_civil_twilight = dateparser.parse(phenTimes["Begin Civil Twilight"])
        end_civil_twilight = dateparser.parse(phenTimes["End Civil Twilight"])

        return {
            "sun_rise": sun_rise,
            "sun_set": sun_set,
            "start_civil_twilight": start_civil_twilight,
            "end_civil_twilight": end_civil_twilight,
            "in_zulu": in_zulu,
        }


class LoggingNight(object):
    """Provide an ICAO code and a date and get what the FAA considers night"""

    AIRPORTINFO_URL = "https://api.aeronautical.info/dev/"
    ONE_HOUR = datetime.timedelta(hours=1)

    @staticmethod
    def enable_cache(expire_after=691200):
        if not "requests_cache" in modules:
            return False

        requests_cache.install_cache(
            "loggingnight_cache", backend="sqlite", expire_after=expire_after
        )
        return True

    @staticmethod
    def garbage_collect_cache():
        if LoggingNight.enable_cache:
            requests_cache.remove_expired_responses()
            log.info("running cache garbage collection")
        else:
            log.info("unable to collect garbage, unable to enable_cache")

    @staticmethod
    def get_cache_entries():
        if LoggingNight.enable_cache:
            cache = requests_cache.get_cache()
            for entry in cache.values():
                yield (entry.expires.isoformat(), entry.url)

    class LocationException(IOError):
        """An error occured finding airport location information"""

    def __init__(self, icao, date, zulu=None, offset=None, try_cache=False):
        self.icao = icao.strip().upper()
        self.date = date
        self.zulu = zulu
        self.offset = offset
        self.try_cache = try_cache

        if self.try_cache:
            self.cache_enabled = self.enable_cache()
        else:
            self.cache_enabled = False

        self.tz = None
        if self.offset is not None and self.zulu == True:
            raise ValueError("Specify either a timezone offset or Zulu time, not both")
        elif self.zulu == True:
            self.tz = "0"
        elif self.offset is not None:
            self.tz = str(self.offset)

        self.airport = web_query(
            self.AIRPORTINFO_URL,
            params={
                "appid": "loggingnight",
                "airport": self.icao,
                "include": ["demographic", "geographic"],
            },
            verify_ssl=True,
        )

        if not self.airport["query_stats"]["status_code"] in {200, 304}:
            raise self.LocationException(
                "Received the following error looking up the airport: %d %s"
                % (
                    self.airport["query_stats"]["status_code"],
                    self.airport["query_stats"]["status_text"],
                )
            )

        if (
            not "response" in self.airport
            or not "city" in self.airport["response"]
            or not self.airport["response"]["city"]
        ):
            raise self.LocationException(
                "Unable to find location information for %s.  Make sure you're using an ICAO identifier (for example, KDPA not DPA)"
                % self.icao
            )

        # Look up astronomical data here
        self.astro_provider = USNOProvider(self.airport, self.date, self.tz)
        #self.astro_provider = StarfieldProvider(self.airport, self.date, self.tz)
        times = self.astro_provider.lookup()

        self.name = self.airport["response"]["name"]
        self.city_st = (
            self.airport["response"]["city"]
            + ", "
            + self.airport["response"]["state_code"]
        )
        self.sun_rise = times["sun_rise"]
        self.sun_set = times["sun_set"]
        self.start_civil_twilight = times["start_civil_twilight"]
        self.end_civil_twilight = times["end_civil_twilight"]
        self.hour_before_sunrise = self.sun_rise - self.ONE_HOUR
        self.hour_after_sunset = self.sun_set + self.ONE_HOUR
        self.in_zulu = times["in_zulu"]


if __name__ == "__main__":
    import argparse
    import datetime
    import pprint
    import sys

    def format_time(t, in_zulu):
        if in_zulu:
            return t.strftime("%I%MZ")
        else:
            return t.strftime("%I:%M %p")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a", "--airport", help="ICAO code for the airport", required=True
    )
    parser.add_argument(
        "-d",
        "--date",
        type=makedate,
        default=datetime.date.today().isoformat(),
        help="Date of the flight",
    )
    parser.add_argument(
        "-o",
        "--offset",
        type=float,
        help="Time zone offset in hours from Zulu, -12.0 to +14.0",
    )
    parser.add_argument("-z", "--zulu", action="store_true", help="Show times in Zulu")
    parser.add_argument(
        "-c",
        "--cache",
        action="store_true",
        help="Attempt to use cache to reduce remote API calls",
    )
    args = parser.parse_args()

    ln = LoggingNight(
        args.airport,
        args.date,
        zulu=args.zulu,
        offset=args.offset,
        try_cache=args.cache,
    )

    log.debug("Airport debug info:")
    log.debug(pprint.pformat(ln.airport, indent=4))
    if hasattr(ln.astro_provider, "usno"):
        log.debug("USNO debug info:")
        log.debug(pprint.pformat(ln.astro_provider.usno, indent=4))

    print("Night times for %s on %s" % (ln.name, ln.date.isoformat()))
    if ln.in_zulu and ln.tz is None:
        print("  - All times are in Zulu; use --offset or --zulu to force a time zone.")
    print("")
    print(
        "%s -- Sun set\nPosition lights required" % format_time(ln.sun_set, ln.in_zulu)
    )
    print("(14 CFR 91.209)")
    print("")
    print(
        "%s -- End of civil twilight" % format_time(ln.end_civil_twilight, ln.in_zulu)
    )
    print("Logging of night time can start and aircraft must be night equipped")
    print("(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)")
    print("")
    print(
        "%s -- One hour after sun set" % format_time(ln.hour_after_sunset, ln.in_zulu)
    )
    print("Must be night current to carry passengers and")
    print("logging of night takeoffs and landings can start")
    print("(14 CFR 61.57(b))")

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
