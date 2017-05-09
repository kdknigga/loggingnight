# loggingnight
Trouble remembering what the FAA says about night time logging and currency?  I gotchu, bro.

## Usage
```$ ./loggingnight.py --help
usage: loggingnight.py [-h] -a AIRPORT [-d DATE] [-D]

optional arguments:
  -h, --help            show this help message and exit
  -a AIRPORT, --airport AIRPORT
                        ICAO code for the airport
  -d DATE, --date DATE  Date of the flight
  -D, --debug```

## Examples
```$ ./loggingnight.py -a KDPA
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
(14 CFR 61.57(b))```

```$ ./loggingnight.py -a KDPA -d 05/08/2017
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
(14 CFR 61.57(b))```
