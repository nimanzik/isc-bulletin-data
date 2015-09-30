# -*- coding: utf-8 -*-
"""
Read and parse ISC bulletin of earthquake data (in ISF format) and write a
phase data file (in NLLOC_OBS format) per event listed in the bulletin.

:version: 0.0.1
:author:
    - Nima Nooshiri
:contact:
    - nooshiri@gfz-potsdam.de
"""

import os
import sys
import subprocess
import re
import datetime as dt

import numpy as np
import pandas as pd

from util import InputError


class ProgressBar(object):
    """
    This is the ProgressBar class, which updates and prints a simple progress
    bar on the screen as standard output.

    :Example:

    >>> pbar = ProgressBar(500)
    >>> pbar.start()
    >>> for i in xrange(1,501):
    >>>     pbar.update(i, percentage=False)
    >>> pbar.finish()
    """

    def __init__(self, max_value):
        self.max_value = max_value

    def start(self):
        sys.stdout.write("[...] Parsing the bulletin file...\n")

    def update(self, curr_value, percentage=True):
        term_width = int(subprocess.check_output(['stty', 'size']).split()[1])
        term_width -= 10
        self.curr_value = curr_value
        progress = int(np.floor(self.curr_value * 100.0 / self.max_value))
        left = "\rProcessing"
        if percentage:
            right = "%d%%" % (progress)
        else:
            right = "%d/%d" % (self.curr_value, self.max_value)
        bar_width = term_width - len(left) - len(right)
        block = int(np.floor(progress/100.0 * bar_width))
        pbar = "[%s%s]" % ("=" * block, " " * (bar_width-block))
        pbar_line = ' '.join((left, pbar, right))
        sys.stdout.write(pbar_line)
        sys.stdout.flush()

    def finish(self):
        sys.stdout.write("\n[ %s ] Done\n" % u'\u2713')


class ISC2NLLoc(object):
    """
    .. todo:: determine indices of block start/end.
    """
    # class attributes
    __isc2gfn_alias_dic = {"GRF":"GR_GRA1"  , "SJI":"IA_SWJI", "CTA":"IU_CTAO",
        "DEIG":"MX_DHIG", "KNMB":"TW_KMNB" , "MZBI":"GE_MSBI", "FLTG":"GE_FLT1",
        "HMBC":"CX_HMBCX", "SPITS":"NO_SPA0", "GEC2A":"GR_GEC2", "KRKI":'IA_KRK',
        "MYLDM":"MY_LDM", "SIMRM":"RM_SIM" , "SLVN":"RM_SLV"}

    __isc2gfn_duplicate_dic = {"IVI":"G_IVI" , "PTK":"KO_PTK", "PSI":"PS_PSI",
        "KWP":"GE_KWP", "SUW":"GE_SUW", "LAST":"GE_LAST", "SIVA":"GE_SIVA"}


    def __init__(self, events, stations):
        self.events = events
        self.stations = stations

    @staticmethod
    def __read_isc_stations(isc_stafile):
        isc_alter2prime_dic = {}
        with open(isc_stafile, "r") as f:
            data = f.readlines()
            for line in data:
                items = [x.strip() for x in line.split(',')]

                first_code, second_code = items[:2]
                lat, lon, alt = [float(x) for x in items[2:]]

                if first_code != second_code:
                    isc_alter2prime_dic[first_code] = second_code
        return isc_alter2prime_dic

    @staticmethod
    def __read_gfn_stations(gfn_stafile):
        gfn_sta2net_dic = {}
        with open(gfn_stafile, 'r') as f:
            for line in f:
                items = line.split()
                net, sta = items[:2]
                gfn_sta2net_dic[sta] = "_".join((net, sta))
        return gfn_sta2net_dic

    @staticmethod
    def _qual2err(phase, onset):
        """
        Quality to error mapping.
        The mapping of the quality of the phase picks in observation file
        onto time uncertainties (time uncertainties are set according to
        Lomax & Husen, 2003)

        :param phase: seismic phase type
        :type phase: str
        :param onset: onset quality of the pick
        :type onset: str
        :return: time uncertainty in seconds
        :rtype: float
        """
        qual2err_Ptype = {"i":0.2, "e":0.5, "_":1.0, "q":1.0}
        qual2err_nonP = {"i":0.5, "e":1.0, "_":2.0, "q":2.0}

        if phase.startswith("P") or phase=="p":
            uncertainty = qual2err_Ptype[onset]
        else:
            uncertainty = qual2err_nonP[onset]

        return uncertainty

    @staticmethod
    def __average_pick(odate, otime, pick_list):
        """
        This function calculates the average of a number of phase picks read by
        different ISC analysts for a given arrival time.

        :param odate: the origin date of the earthquake event
        :type odate: `datetime.date` object
        :param otime: the origin time of the earthquake event
        :type otime: `datetime.time` object
        :param pick_list: list of tuples of (onsetQual, arrDate, arrTime, pickErr, ttRes)
        :returns: time, date, uncertainty and residual for average pick
        """
        time_list = [x[2] for x in pick_list]
        total = sum(t.hour*36e8 + t.minute*6e7 + t.second*1e6 + t.msecond for t in time_list)
        average =  total / len(time_list)
        sec, microsec = [int(x) for x in divmod(average, 1e6)]
        mn, sec = [int(x) for x in divmod(sec, 60)]
        hr, mn = [int(x) for x in divmod(mn, 60)]
        arrtime = dt.time(hr, mn, sec, microsec)
        if arrtime < otime:
            arrdate = odate + dt.timedelta(days=1)
        else:
            arrdate = odate + dt.timedelta(days=0)

        onset = '?'
        uncertainty = np.mean([x[-2] for x in pick_list])

        r = [x[-1] for x in pick_list if type(x[-1])==float]
        if any(r):
            tt_res = round(np.mean(r), 2)
        else:
            tt_res = np.nan

        return (onset, arrdate, arrtime, uncertainty, tt_res)

    @classmethod
    def bulletin_parser(cls, bulletin_file, isc_stafile, gfn_stafile, Phases,
                        outdir=None):
        stations = []

        for f in (bulletin_file, isc_stafile, gfn_stafile):
            if not isinstance(f, basestring):
                raise InputError(f, "Need string or buffer")
            if not os.path.exists(f):
                raise InputError(f, "No such file or directory")

        if not outdir:
            outdir = "./isc_data_nlloc_format"
            os.mkdir(outdir)
        elif not isinstance(outdir, basestring):
            raise InputError(outdir, "Need string or buffer")
        elif not os.path.exists(outdir):
            raise InputError(outdir, "No such file or directory")

        if not isinstance(Phases, list):
            Phases = list(Phases)
        for ph in Phases:
            if not isinstance(ph, basestring):
                raise InputError(ph, "Need a string or buffer")

        isc_alter2prime_dic = cls.__read_isc_stations(isc_stafile)
        gfn_sta2net_dic = cls.__read_gfn_stations(gfn_stafile)

        with open(bulletin_file, "r") as f:
            textdata = f.read()
            split_bulletin = re.split(r'\s+STOP\s+', textdata)[0]
            split_bulletin = re.split(r'\s+Event\s+', split_bulletin)[1:]

        nEvents = len(split_bulletin)
        pbar = ProgressBar(nEvents)
        pbar.start()

        eindex = range(len(split_bulletin))
        ecolumns = ['Origin-Time', 'Lat', 'Lon', 'Depth']
        events = pd.DataFrame(index=eindex, columns=ecolumns)
        events.index.names = ['Event-ID']
        for i, event in enumerate(split_bulletin):
            lines = event.splitlines()
            # remove empty lines
            lines = filter(None, lines)
            eventID = lines[0].split()[0]

            ### READ ORIGIN BLOCK ###
            origin_block = lines[2]

            odate = dt.datetime.strptime(origin_block[0:10].strip(), "%Y/%m/%d")
            otime = dt.datetime.strptime(origin_block[11:22].strip(), "%H:%M:%S.%f")
            origin_time = dt.datetime.combine(odate, otime.time())
            otime_fixflag = origin_block[22].strip()
            otime_err = origin_block[24:29].strip()
            if any(otime_err):
                otime_err = float(otime_err)

            residual_rms = origin_block[30:35].strip()
            if any(residual_rms):
                residual_rms = float(residual_rms)

            elat = float(origin_block[36:44])
            elon = float(origin_block[45:54])
            epicenter_fixflag = origin_block[54].strip()
            if not any(epicenter_fixflag):
                try:
                    # the axes of the 90% error ellipse of the epicneter [km]
                    err_ellipse_smaj = float(origin_block[55:60])
                    err_ellipse_smin = float(origin_block[61:66])
                    # the strike (0-360) of the error ellipse clock-wise from North [deg]
                    err_ellipse_azi = float(origin_block[67:70])
                except:
                    pass

            edepth = float(origin_block[71:76])
            depth_fixflag = origin_block[76].strip()
            if not any(depth_fixflag):
                try:
                    # depth error for a 90% confidence level
                    depth_error = float(origin_block[78:82])
                except:
                    pass

            events.ix[i, ecolumns] = origin_time, elat, elon, edepth
            events.rename(index={i:eventID}, inplace=True)

            ### READ PHASE BLOCK ###
            phase_block = lines[4:]
            index = range(len(phase_block))
            columns = ['On', 'Phase', 'Time', 'ErrMag', 'Residual']
            arrData = pd.DataFrame(index=index, columns=columns)
            for j,line in enumerate(phase_block):
                staCode = line[0:5].strip()
                phase = line[19:27].strip()
                res = line[41:46].strip()
                onset = line[101]

                if staCode.isalnum() and phase.isalnum() and phase in Phases:
                    try:
                        try:
                            atime = dt.datetime.strptime(line[28:40].strip(), "%H:%M:%S.%f")
                        except:
                            atime = dt.datetime.strptime(line[28:40].strip(), "%H:%M:%S")
                        # check whether a one-day jump in date (24 hours) is needed
                        # for those phases arriving after midnight (00:00:00 am).
                        if atime.time() < origin_time.time():
                            adate = origin_time.date() + dt.timedelta(days=1)
                        else:
                            adate = origin_time.date()
                        arrival_time = dt.datetime.combine(adate, atime.time())

                        try:
                            res = float(res)
                        except ValueError:
                            res = np.nan

                        uncertainty = cls._qual2err(phase, onset)

                        # To check if any station renaming should be done.
                        if staCode in isc_alter2prime_dic.keys():
                            staCode = isc_alter2prime_dic[staCode]

                        if staCode in cls.__isc2gfn_alias_dic.keys():
                            staCode = cls.__isc2gfn_alias_dic[staCode]
                        elif staCode in cls.__isc2gfn_duplicate_dic.keys():
                            staCode = cls.__isc2gfn_duplicate_dic[staCode]
                        elif staCode in gfn_sta2net_dic.keys():
                            staCode = gfn_sta2net_dic[staCode]

                        if staCode not in stations:
                            stations.append(staCode)

                        arrData.ix[j, columns] = onset, phase, arrival_time, uncertainty, res
                        arrData.Time = pd.to_datetime(arrData.Time)
                        arrData.rename(index={j:staCode.ljust(8)}, inplace=True)
                    except:
                        continue

            arrData.dropna(axis=0, how='all', inplace=True)
            arrData.Time = pd.to_datetime(arrData.Time)
            arrData['Err'] = 'GAU'
            arrData['Ins'], arrData['Cmp'], arrData['FM'] = ['?']*3
            arrData['Coda'], arrData['Amp'], arrData['Per'] = [-1]*3

            # final step -- write arrival data to ascii file
            outfile = ''.join(('isc', eventID, '.nll'))
            outfile = os.path.join(outdir, outfile)
            with open(outfile, 'w') as f:
                # header
                for line in lines[0:3]:
                    f.write(line + '\n')

            arrData.to_csv(outfile, mode='a', sep='\t', float_format='%6.2f',
                           index_label='PHASE ID', date_format="%Y%m%d %H%M %S.%f",
                           columns=['Ins','Cmp','On','Phase','FM','Time','Err','ErrMag','Coda','Amp','Per'])

            pbar.update(i+1)
        pbar.finish()

        return cls(events, stations)