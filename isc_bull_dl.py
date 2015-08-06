"""
This Python script is used to download ISC bulletin data, read and parse the
bulletin, and write a NLLoc phase file per event listed in the bulletin.
"""


import argparse


parser = argparse.ArgumentParser(prog='ISC_bulletin_dl',
                                 description='Download ISC bulletin dataset.')

### Geographic region ###
parser.add_argument("--search",
                    dest="searchshape",
                    required=True,
                    choices=["GLOBAL","RECT","CIRC","POLY"])

### RECT (rectangular) search type ###
rect_group = parser.add_argument_group(title='RECT-rectangular search',
                                       description='Dependent parameters for --search=RECT')
rect_group.add_argument('--blat',
                        dest='bot_lat',
                        help='Bottom latitude of rectangular region (-90 to 90).')
rect_group.add_argument('--tlat',
                        dest='top_lat',
                        help='Top latitude of rectangular region (-90 to 90).')
rect_group.add_argument('--llon',
                        dest='left_lon',
                        help='Left longitude of rectangular region (-180 to 180).')
rect_group.add_argument('--rlon',
                        dest='right_lon',
                        help='Right longitude of rectangular region (-180 to 180).')

### CIRC (circular) search type ###
circ_group = parser.add_argument_group(title='CIRC-circular search',
                                       description='Dependent parameters for --search=CIRC')
circ_group.add_argument('--clat',
                        dest='ctr_lat',
                        help='Central latitude of circular region.')
circ_group.add_argument('--clon',
                        dest='ctr_lon',
                        help='Central longitude of circular regio.')
circ_group.add_argument('--units',
                        dest='max_dist_units',
                        choices=['deg', 'km'],
                        help='Units of distance for a circular search.')
circ_group.add_argument('--radius',
                        dest='radius',
                        help="Radius for circular search region: 0 to 180 " +\
                             "if --units=deg, 0 to 20015 if --units=km.")

### POLY (customised polygon) search type ###
poly_group = parser.add_argument_group(title='POLY-polygon search',
                                       description='Dependent parameters for --search=POLY')
poly_group.add_argument('--coords',
                        dest='coordvals',
                        help="Comma seperated list of coordinates for a "    +\
                             "desired polygon. Coordinates in the western "  +\
                             "and southern hemispheres should be negative. " +\
                             "(lat1,lon1,lat2,lon2,...,latN,lonN,lat1,lon1)")

### Time range ###
parser.add_argument("--syear",
                    dest="start_year",
                    required=True,
                    help="Starting year for events (1904 to 2015).")

parser.add_argument("--smonth",
                    dest="start_month",
                    required=True,
                    help="Starting month for events (1 to 12).")

parser.add_argument("--sday",
                    dest="start_day",
                    required=True,
                    help="Starting day for events (1 to 31).")

parser.add_argument("--stime",
                    dest="start_time",
                    required=True,
                    help="Starting time for events HH:MM:SS (00:00:00 to 23:59:59).")


parser.add_argument("--eyear",
                    dest="end_year",
                    required=True,
                    help="Ending year for events (1904 to 2015).")

parser.add_argument("--emonth",
                    dest="end_month",
                    required=True,
                    help="Ending month for events (1 to 12).")

parser.add_argument("--eday",
                    dest="end_day",
                    required=True,
                    help="Ending day for events (1 to 31).")

parser.add_argument("--etime",
                    dest="end_time",
                    required=True,
                    help="Ending time for events HH:MM:SS (00:00:00 to 23:59:59).")

### Depth limits ###
parser.add_argument("--Zmin", dest="min_dep", help="Minimum depth of events (km).")
parser.add_argument("--Zmax", dest="max_dep", help="Maximum depth of events (km).")

### Magnitude limits ###
parser.add_argument("--Mmin", dest="min_mag", help="Minimum magnitude of events.")
parser.add_argument("--Mmax", dest="max_mag", help="Maximum magnitude of events.")

parser.add_argument("--Mtype",
                    dest="req_mag_type",
                    choices=["Any","MB","MS","MW","ML","MD"],
                    help="Specific magnitude types. The selected magnitude " +\
                         "type will search for all possible magnitudes in "  +\
                         "that category (e.g. MB will search for mb, mB, Mb, mb1mx, etc).")

parser.add_argument('--Magcy',
                    dest='req_mag_agcy',
                    help='Limit events to magnitudes computed by the selected ' +\
                         'agency: {Any, prime, CODE (specific agency code)}.')


### Defining phases limits ###
parser.add_argument('--DPmin', dest='min_def', help='Minimum number of defining phases.')
parser.add_argument('--DPmax', dest='max_def', help='Maximum number of defining phases.')



args = parser.parse_args()

def get_search_opts(search_type):
    """
    :param search_type: Desired search type defining the geographic region
    :type search_type: str
    :returns: A list of dependent parameters (options) of search_type
    """
    search = ('GLOBAL', 'RECT', 'CIRC', 'POLY')
    glob_opts = None
    rect_opts = ['bot_lat', 'top_lat', 'left_lon', 'right_lon']
    circ_opts = ['ctr_lat', 'ctr_lon', 'max_dist_units', 'radius']
    poly_opts = ['coordvals']
    opts = (glob_opts, rect_opts, circ_opts, poly_opts)
    search2opts = dict(zip(search, opts))

    return search2opts[search_type]

def verify_search_opts(options):
    global parser
    global args
    if not all([getattr(args,name) for name in options]):
        msg = "Missing argument(s) for defined search shape. " +\
              "Check the dependent parameters for your considered search type."
        parser.error(msg)

options = get_search_opts(args.searchshape)
verify_search_opts(options)