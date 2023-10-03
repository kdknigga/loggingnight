# loggingnight
Trouble remembering what the FAA says about night time logging and currency?  I gotchu, bro.

## Overview
loggingnight is both a web service and commandline application to simplify figuring out the rules around night flight in the USA.  Not only will loggingnight enumerate the different definitions of night and the rules that go with them, but it will also look up sunset information from the US Naval Observatory and show times tailored to a date and location.

## The web version
The production version (the master branch) lives at http://loggingnight.org/ and the development version (the dev branch) can be found at http://dev.loggingnight.org/

### Running the web version locally
I would recommend using virtualenv.

Here's a rough guide to getting started.  I'm sure there are a multitude of ways to get this done, so use what works for you.

```
$ git clone https://github.com/kdknigga/loggingnight.git
$ virtualenv loggingnight_virtenv
$ source loggingnight_virtenv/bin/activate
$ cd loggingnight
$ pip install --upgrade pip
$ pip install -r requirements.txt
```

You should be ready to go now.  To start up the app try:

```
$ python webapp.py
```

## The CLI version
### Setup
Requires python (tested on 2.7)

Used modules:
 - argparse
 - datetime
 - json
 - requests

Tested on CentOS 7

## Usage
```
$ ./loggingnight.py --help
usage: loggingnight.py [-h] -a AIRPORT [-d DATE] [-D] [-o OFFSET] [-z]

optional arguments:
  -h, --help            show this help message and exit
  -a AIRPORT, --airport AIRPORT
                        ICAO code for the airport
  -d DATE, --date DATE  Date of the flight
  -D, --debug
  -o OFFSET, --offset OFFSET
                        Time zone offset in hours from Zulu, -12.0 to +14.0
  -z, --zulu            Show times in Zulu
```

## Examples
```
$ ./loggingnight.py -a KDPA
Night times for Dupage Airport on 2017-05-08

07:59 PM -- Sun set
Position lights required
(14 CFR 91.209)

08:30 PM -- End of civil twilight
Logging of night time can start and aircraft must be night equipped
(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)

08:59 PM -- One hour after sun set
Must be night current to carry passengers and
logging of night takeoffs and landings can start
(14 CFR 61.57(b))
```

```
$ ./loggingnight.py -a KDPA -d "March 21, 2017"
Night times for Dupage Airport on 2017-03-21

07:06 PM -- Sun set
Position lights required
(14 CFR 91.209)

07:34 PM -- End of civil twilight
Logging of night time can start and aircraft must be night equipped
(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)

08:06 PM -- One hour after sun set
Must be night current to carry passengers and
logging of night takeoffs and landings can start
(14 CFR 61.57(b))
```

```
$ ./loggingnight.py -a KIND -z
Night times for Indianapolis International Airport on 2017-05-29

0104Z -- Sun set
Position lights required
(14 CFR 91.209)

0136Z -- End of civil twilight
Logging of night time can start and aircraft must be night equipped
(14 CFR 61.51(b)(3)(i), 14 CFR 91.205(c), and 14 CFR 1.1)

0204Z -- One hour after sun set
Must be night current to carry passengers and
logging of night takeoffs and landings can start
(14 CFR 61.57(b))
```
