#!/usr/bin/env python3

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

application = Flask(
    "__name__", static_url_path="/assets", static_folder="templates/assets"
)

dev_mode = os.environ.get("LOGGINGNIGHT_DEV", "false")
if dev_mode == "true":
    import pprint

    application.config["DEBUG"] = True
else:
    application.config["DEBUG"] = False


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

    schedule.every(6).hours.do(LoggingNight.garbage_collect_cache)


@application.route("/")
def index():
    icao_identifier = request.args.get("airport")

    try:
        date = dateparser.parse(
            request.args.get("date", datetime.date.today().isoformat())
        ).date()
    except ValueError:
        date = datetime.date.today()

    if icao_identifier:
        try:
            result = do_lookup(icao_identifier, date)
        except Exception as e:
            result = {
                "airport": icao_identifier,
                "date": date.isoformat(),
                "error": str(e),
            }
            return render_template("index.html", dev_mode=dev_mode, result=result), 400
    else:
        result = None

    return render_template("index.html", dev_mode=dev_mode, result=result)


def do_lookup(icao_identifier, date):
    ln = LoggingNight(icao_identifier, date, try_cache=True)

    if ln.in_zulu:
        time_format = "%H%M Zulu"
    else:
        time_format = "%I:%M %p"

    if dev_mode == "true":
        result = dict(
            airport=icao_identifier,
            name=ln.name,
            city=ln.city_st,
            date=date.isoformat(),
            sunrise=ln.sun_rise.strftime(time_format),
            sunset=ln.sun_set.strftime(time_format),
            start_civil=ln.start_civil_twilight.strftime(time_format),
            end_civil=ln.end_civil_twilight.strftime(time_format),
            hour_before=ln.hour_before_sunrise.strftime(time_format),
            hour_after=ln.hour_after_sunset.strftime(time_format),
            airport_debug=pprint.pformat(ln.airport, indent=4),
            # usno_debug=pprint.pformat(ln.usno, indent=4)
        )
    else:
        result = dict(
            airport=icao_identifier,
            name=ln.name,
            city=ln.city_st,
            date=date.isoformat(),
            sunrise=ln.sun_rise.strftime(time_format),
            sunset=ln.sun_set.strftime(time_format),
            start_civil=ln.start_civil_twilight.strftime(time_format),
            end_civil=ln.end_civil_twilight.strftime(time_format),
            hour_before=ln.hour_before_sunrise.strftime(time_format),
            hour_after=ln.hour_after_sunset.strftime(time_format),
        )

    return result


@application.route("/lookup", methods=["POST"])
def lookup():
    icao_identifier = flask.escape(request.form["airport"])
    datestring = flask.escape(request.form["date"])

    if datestring:
        try:
            date = dateparser.parse(datestring).date()
        except ValueError:
            return "Unable to understand date %s" % datestring, 400
    else:
        date = datetime.date.today()

    try:
        result = do_lookup(icao_identifier, date)
    except Exception as e:
        return str(e), 400
    except:
        flask.abort(500)

    return json.dumps(result)


@application.route("/displayCache")
def displayCache():
    if LoggingNight.enable_cache():
        return Response(
            json.dumps(
                list(
                    (str(timestamp), url)
                    for timestamp, url in LoggingNight.get_cache_entries()
                )
            ),
            mimetype="application/json",
        )
    else:
        return False


@application.route("/sitemap.txt")
@application.route("/static/sitemap.txt")
def sitemap():
    base_url = "https://loggingnight.org/?airport="
    # fmt: off
    icao_airports = ["VNY", "DVT", "APA", "PRC", "HIO", "FFZ", "IWA", "GFK", "LGB", "SEE", "MYF", "SFB", "SNA", "CHD", "FPR", "FRG", "TMB", \
                     "PAO", "RVS", "VRB", "DAB", "PMP", "PVU", "SDL", "RHV", "CNO", "DTO", "BJC", "PDK", "FIN", "SGJ", "ORF", "CRQ", "DCU", \
                     "SMO", "ISM", "LVK", "VGT", "EUL", "BFI", "BDN", "HPN", "FXE", "CRG", "CMA", "LAL", "AWO", "ORD", "ATL", "LAX", "DFW", \
                     "DEN", "CLT", "LAS", "IAH", "JFK", "SFO", "SEA", "PHX", "EWR", "MIA", "DTW", "MSP", "LGA", "BOS", "PHL", "FLL", "MCO", \
                     "DCA", "SLC", "BWI", "IAD", "MDW", "PDX", "MEM", "SAN", "STL", "BNA", "TPA", "HOU", "SJC", "OAK", "SDF", "CVG", "AUS", \
                     "DAL", "RDU", "IND", "PIT", "DAB", "OGG", "SMF", "MSY", "SJU", "MCI", "DPA", "ARR", "OKK", "OSH"]

    faa_airports = ["S50", "1R8", "52F", "LL10", "8I3", "ANC", "PANC", "HNL", "PHNL"]
    # fmt: on

    urls = ["%s%s" % (base_url, airport) for airport in icao_airports]
    urls.extend(["%sK%s" % (base_url, airport) for airport in icao_airports])
    urls.extend(["%s%s" % (base_url, airport) for airport in faa_airports])
    urls.append("%sKOKK&date=1983-08-23" % base_url)

    return ("\n".join(urls), 200, {"Content-Type": "text/plain"})


if __name__ == "__main__":
    application.run()

# vi: modeline tabstop=8 expandtab shiftwidth=4 softtabstop=4 syntax=python
