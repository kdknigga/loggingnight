#!/usr/bin/env python3

import datetime
import json
import os
import threading
import time

import flask
import markupsafe
import schedule
import sentry_sdk
from dateutil import parser as dateparser
from flask import Flask, Response, render_template, request

from loggingnight import LoggingNight

sentry_debug: bool = False
sentry_traces_sample_rate: float = 0.001
sentry_profiles_sample_rate: float = 0.001
gc_hours: int = 6
dev_mode: bool = False

app_env: str = os.environ.get("ENVIRONMENT", "local")
match app_env:
    case "production":
        pass
    case "development":
        sentry_traces_sample_rate = 0.5
        sentry_profiles_sample_rate = 0.0
        dev_mode = True
    case "debug":
        sentry_traces_sample_rate = 1.0
        sentry_profiles_sample_rate = 1.0
        sentry_debug = True
        dev_mode = True
        gc_hours = 1
    case _:
        # Default to "local"
        app_env = "local"
        sentry_traces_sample_rate = 1.0
        sentry_profiles_sample_rate = 1.0
        dev_mode = True
        gc_hours = 1

sentry_dsn: str | None = os.environ.get("SENTRY_DSN", None)
if sentry_dsn is not None:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=sentry_traces_sample_rate,
        profiles_sample_rate=sentry_profiles_sample_rate,
        enable_tracing=True,
        debug=sentry_debug,
        environment=app_env,
    )


def enable_housekeeping(run_interval: int = 3600):
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        def run(self) -> None:
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(run_interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()

    schedule.every(gc_hours).hours.do(LoggingNight.garbage_collect_cache)


enable_housekeeping()

application = Flask(
    "__name__", static_url_path="/assets", static_folder="templates/assets"
)

if dev_mode:
    import pprint

application.config["DEBUG"] = dev_mode


@application.route("/")
def index() -> tuple[str, int] | str:
    icao_identifier: str | None = request.args.get("airport")

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


def do_lookup(icao_identifier: str, date) -> dict[str, str]:
    ln = LoggingNight(icao_identifier, date, try_cache=True)

    if ln.in_zulu:
        time_format = "%H%M Zulu"
    else:
        time_format = "%I:%M %p"

    if dev_mode:
        # pylint: disable=use-dict-literal
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
            usno_debug=pprint.pformat(ln.astro_provider.usno, indent=4),
        )
    else:
        # pylint: disable=use-dict-literal
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
def lookup() -> tuple[str, int] | str:
    icao_identifier = markupsafe.escape(request.form["airport"])
    datestring = markupsafe.escape(request.form["date"])

    if datestring:
        try:
            date = dateparser.parse(datestring).date()
        except ValueError:
            return f"Unable to understand date {datestring}", 400
    else:
        date = datetime.date.today()

    try:
        result: dict[str, str] = do_lookup(icao_identifier, date)
    except Exception as e:
        return str(e), 400
    except:  # pylint: disable=bare-except # noqa
        flask.abort(500)

    return json.dumps(result)


@application.route("/displayCache")
def displayCache() -> Response:
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

    return Response(response="", status=204)


@application.route("/sitemap.txt")
@application.route("/static/sitemap.txt")
def sitemap() -> tuple[str, int, dict[str, str]]:
    # pylint: disable=consider-using-f-string
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
