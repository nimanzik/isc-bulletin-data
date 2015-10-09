"""
This Python script is used to download ISC bulletin data, read and parse the
bulletin, and write a NLLoc phase file per event listed in the bulletin.
"""


import argparse
import urllib
from itertools import chain


class Parser(argparse.ArgumentParser):

    # class attributes
    __search2options = {'GLOBAL': None,
                        'RECT': ('bot_lat', 'top_lat', 'left_lon',
                                 'right_lon'),
                        'CIRC': ('ctr_lat', 'ctr_lon', 'max_dist_units',
                                 'radius'),
                        'POLY': ('coordvals',)}

    __query_client = "http://www.isc.ac.uk/cgi-bin/web-db-v4?"

    def __init__(self, *args, **kwargs):
        super(Parser, self).__init__(*args, **kwargs)

    def verify_search_options(self):
        self.args = self.parse_args()
        required = Parser.__search2options.pop(self.args.searchshape)
        conflicts = filter(None, Parser.__search2options.values())
        conflicts = list(chain(*conflicts))

        if (not all([getattr(self.args, r) for r in required]) or
                any([hasattr(self.args, c) for c in conflicts])):
            msg = '''Missing argument(s) for defined search shape. Check the
            dependent parameters for your considered search type.'''
            self.error(msg)

    def download_bulletin(self):
        args_dic = vars(self.args)
        args_dic.update(prime_only='on', include_phases='on',
                        include_headers='on')
        query_opts = ["=".join((k, str(v))) for (k, v) in args_dic.items()]
        query_opts = "&".join(query_opts)

        query_url = Parser.__query_client + query_opts
        self.bulletin, header = urllib.urlretrieve(query_url)

        return self.bulletin


if __name__ == "__main__":
    parser = Parser(description='Download ISC bulletin dataset.')

    # --- Geographic region ---
    parser.add_argument('--search', dest='searchshape', required=True,
                        choices=['GLOBAL', 'RECT', 'CIRC', 'POLY'])

    # --- RECT (rectangular) search type ---
    rect_group = parser.add_argument_group(title='RECT-rectangular search',
                                           description='''Dependent parameters
                                           for --search=RECT option.''')

    rect_group.add_argument('--blat', dest='bot_lat', type=float,
                            default=argparse.SUPPRESS, help='''Bottom latitude
                            of rectangular region (-90 to 90).''')

    rect_group.add_argument('--tlat', dest='top_lat', type=float,
                            default=argparse.SUPPRESS, help='''Top latitude of
                            rectangular region (-90 to 90).''')

    rect_group.add_argument('--llon', dest='left_lon', type=float,
                            default=argparse.SUPPRESS, help='''Left longitude
                            of rectangular region (-180 to 180).''')

    rect_group.add_argument('--rlon', dest='right_lon', type=float,
                            default=argparse.SUPPRESS, help='''Right longitude
                            of rectangular region (-180 to 180).''')

    # --- CIRC (circular) search type ---
    circ_group = parser.add_argument_group(title='CIRC-circular search',
                                           description='''Dependent parameters
                                           for --search=CIRC option.''')

    circ_group.add_argument('--clat', dest='ctr_lat', type=float,
                            default=argparse.SUPPRESS, help='''Central latitude
                            of circular region.''')

    circ_group.add_argument('--clon', dest='ctr_lon', type=float,
                            default=argparse.SUPPRESS, help='''Central longitude
                            of circular regio.''')

    circ_group.add_argument('--units', dest='max_dist_units',
                            choices=['deg', 'km'], default=argparse.SUPPRESS,
                            help='Units of distance for a circular search.')

    circ_group.add_argument('--radius', dest='radius', type=float,
                            default=argparse.SUPPRESS, help='''Radius for
                            circular search region: 0 to 180 if --units=deg,
                            0 to 20015 if --units=km.''')

    # --- POLY (customised polygon) search type ---
    poly_group = parser.add_argument_group(title='POLY-polygon search',
                                           description='''Dependent parameters
                                           for --search=POLY''')

    poly_group.add_argument('--coords', dest='coordvals',
                            default=argparse.SUPPRESS, help='''Comma seperated
                            list of coordinates for a desired polygon (lat1,
                            lon1, lat2, lon2, ..., latN, lonN, lat1, lon1).
                            Coordinates in the western and southern hemispheres
                            should be negative.''')

    # --- Time range ---
    parser.add_argument('--syear', dest='start_year', type=int, required=True,
                        help='Starting year for events (1904 to 2015).')

    parser.add_argument('--smonth', dest='start_month', required=True,
                        type=int, help='Starting month for events (1 to 12).')

    parser.add_argument('--sday', dest='start_day', type=int, required=True,
                        help='Starting day for events (1 to 31).')

    parser.add_argument('--stime', dest='start_time', required=True,
                        help='''Starting time for events HH:MM:SS
                        (00:00:00 to 23:59:59).''')

    parser.add_argument('--eyear', dest='end_year', type=int, required=True,
                        help='Ending year for events (1904 to 2015).')

    parser.add_argument('--emonth', dest='end_month', type=int, required=True,
                        help='Ending month for events (1 to 12).')

    parser.add_argument('--eday', dest='end_day', type=int, required=True,
                        help='Ending day for events (1 to 31).')

    parser.add_argument('--etime', dest='end_time', required=True,
                        help='''Ending time for events HH:MM:SS
                        (00:00:00 to 23:59:59).''')

    # --- Depth limits ---
    parser.add_argument('--Zmin', dest='min_dep', default=argparse.SUPPRESS,
                        type=float, help='Minimum depth of events (km).')

    parser.add_argument('--Zmax', dest='max_dep', default=argparse.SUPPRESS,
                        type=float, help='Maximum depth of events (km).')

    # --- Magnitude limits ---
    parser.add_argument('--Mmin', dest='min_mag', default=argparse.SUPPRESS,
                        type=float, help='Minimum magnitude of events.')

    parser.add_argument('--Mmax', dest='max_mag', default=argparse.SUPPRESS,
                        type=float, help='Maximum magnitude of events.')

    parser.add_argument('--Mtype', dest='req_mag_type',
                        default=argparse.SUPPRESS,
                        choices=['Any', 'MB', 'MS', 'MW', 'ML', 'MD'],
                        help='''Specific magnitude types. The selected magnitude
                                type will search for all possible magnitudes in
                                that category (e.g. MB will search for mb, mB,
                                Mb, mb1mx, etc).''')

    parser.add_argument('--Magcy', dest='req_mag_agcy',
                        default=argparse.SUPPRESS,
                        help='''Limit events to magnitudes computed by the
                                selected agency: {Any, prime, CODE (specific
                                agency code)}.''')

    # --- Defining phases limits ---
    parser.add_argument('--DPmin', dest='min_def', default=argparse.SUPPRESS,
                        type=int, help='Minimum number of defining phases.')

    parser.add_argument('--DPmax', dest='max_def', default=argparse.SUPPRESS,
                        type=int, help='Maximum number of defining phases.')

    args = parser.parse_args()
    parser.verify_search_options()
    bulletin = parser.download_bulletin()
