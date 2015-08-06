"""
Read and parse ISC bulletin of event data (in ISF format), and write a phase
data file (in NLLOC_OBS format) per event listed in the bulletin.

@created: May 2015; Potsdam, Germany
"""

import os
import re
import warnings
import datetime as dt
import numpy as np
from pandas import DataFrame
import sys


def check_file(filename):
    if not isinstance(filename, basestring):
        msg = "%s is not a file name." % filename
        warnings.warn(msg)
    if not os.path.exists(filename):
        msg = "Warning: File %s does not exist." % filename
        warnings.warn(msg)
    print "File %s was imported." % filename


def check_phase(phases):
    if (not isinstance(phases, str) and
        not isinstance(phases, list)):
        msg = "The type of input phase is neither str nor list."
        warnings.warn(msg)
    print "The list of desired phases was imported."


class ISCBull2NLLocObs(object):
    """
    .. todo:: determine indices of block start/end.
    """

    # class attributes
    isc2gfn_alias_dic = {"GRF":"GR_GRA1"  , "SJI":"IA_SWJI",
                         "CTA":"IU_CTAO"  , "DEIG":"MX_DHIG",
                         "KNMB":"TW_KMNB" , "MZBI":"GE_MSBI",
                         "FLTG":"GE_FLT1" , "HMBC":"CX_HMBCX",
                         "SPITS":"NO_SPA0", "GEC2A":"GR_GEC2",
                         "KRKI":'IA_KRK'  , "MYLDM":"MY_LDM",
                         "SIMRM":"RM_SIM" , "SLVN":"RM_SLV"}

    isc2gfn_duplicate_dic = {"IVI":"G_IVI" , "PTK":"KO_PTK",
                             "PSI":"PS_PSI", "KWP":"GE_KWP",
                             "SUW":"GE_SUW", "LAST":"GE_LAST",
                             "SIVA":"GE_SIVA"}


    def __init__(self, events, stations):
        self.events = events
        self.stations = stations


    @staticmethod
    def read_isc_staFile(isc_staFile):
        isc_alter2prime_dic = {}
        with open(isc_staFile, "r") as f:
            data = f.readlines()
            for line in data:
                items = [x.strip() for x in line.split(',')]

                first_code, second_code = items[:2]
                lat, lon, alt = [float(x) for x in items[2:]]

                if first_code != second_code:
                    isc_alter2prime_dic[first_code] = second_code
        return isc_alter2prime_dic


    @staticmethod
    def read_gfn_staFile(gfn_staFile):
        gfn_sta2net_dic = {}
        with open(gfn_staFile, 'r') as f:
            for line in f:
                items = line.split()
                network, station = items[:2]
                gfn_sta2net_dic[station] = "_".join((network, station))
        return gfn_sta2net_dic


    @staticmethod
    def qual2err(phase, onset_quality):
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
            pick_uncertainty = qual2err_Ptype[onset_quality]
        else:
            pick_uncertainty = qual2err_nonP[onset_quality]

        return pick_uncertainty


    @staticmethod
    def average_pick(origin_date, origin_time, pick_list):
        """
        This function calculates the average of a number of phase picks read by
        different ISC analysts for a given arrival time.

        :param origin_date: the origin date of the earthquake event
        :type origin_date: `datetime.date` object
        :param origin_time: the origin time of the earthquake event
        :type origin_time: `datetime.time` object
        :param pick_list: list of tuples of (onsetQual, arrDate, arrTime, pickErr, ttRes)
        :returns: time, date, uncertainty and residual for average pick
        """
        time_list = [x[2] for x in pick_list]
        total = sum(t.hour*36e8 + t.minute*6e7 + t.second*1e6 + t.microsecond for t in time_list)
        average =  total / len(time_list)
        sec, microsec = [int(x) for x in divmod(average, 1e6)]
        mn, sec = [int(x) for x in divmod(sec, 60)]
        hr, mn = [int(x) for x in divmod(mn, 60)]
        arrival_time = dt.time(hr, mn, sec, microsec)
        if arrival_time < origin_time:
            arrival_date = origin_date + dt.timedelta(days=1)
        else:
            arrival_date = origin_date + dt.timedelta(days=0)

        onset_quality = '?'
        pick_uncertainty = np.mean([x[-2] for x in pick_list])

        r = [x[-1] for x in pick_list if type(x[-1])==float]
        if any(r):
            tt_residual = round(np.mean(r), 2)
        else:
            tt_residual = 'N/A'

        return (onset_quality, arrival_date, arrival_time, pick_uncertainty, tt_residual)


    @classmethod
    def bulletin_parser(cls, bulletin_file, isc_staFile, gfn_staFile, Phases, output_dir):
        events_dic = {}
        stations = []

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print "\n[...] Reading ISC station file..."
        isc_alter2prime_dic = cls.read_isc_staFile(isc_staFile)
        print "[ %s ] Done" % u'\u2713'

        print "[...] Reading GEOFON station file..."
        gfn_sta2net_dic = cls.read_gfn_staFile(gfn_staFile)
        print "[ %s ] Done" % u'\u2713'

        with open(bulletin_file, "r") as f:
            print "[...] Parsing the bulletin file..."
            bulletin = f.read()
            split_bulletin = re.split(r'\s+STOP\s+', bulletin)[0]
            split_bulletin = re.split(r'\s+Event\s+', split_bulletin)[1:]

        nEvents = len(split_bulletin)
        sys.stdout.write("Number of saved phase/arrival data files = ")
        last_lenght = 0
        for i, event in enumerate(split_bulletin):
            # Display a progress bar on the screen
            # ('\b' generally moves the cursor back by one space)
            if (i+1)%50 == 0 or (i+1)==nEvents:
                sys.stdout.write('\b' * last_lenght)    # go back
                sys.stdout.write(' ' * last_lenght)     # clear last name
                sys.stdout.write('\b' * last_lenght)    # reposition
                stdout_line = "/".join((str(i+1), str(nEvents)))
                sys.stdout.write(stdout_line)
                sys.stdout.flush()
                last_lenght = len(stdout_line)


            lines = event.splitlines()
            lines = filter(None, lines)    # remove the empty lines

            eventID = lines[0].split()[0]

            ### READ ORIGIN BLOCK ###
            origin_block = lines[2]

            origin_date = dt.datetime.strptime(origin_block[0:10].strip(), "%Y/%m/%d")
            origin_time = dt.datetime.strptime(origin_block[11:22].strip(), "%H:%M:%S.%f")
            origin_time = origin_time.time()
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

            events_dic[eventID] = (origin_date, origin_time, elat, elon, edepth)
            events = DataFrame.from_dict(events_dic, orient='index')
            events.columns = ["Date", "Time", "Latitude", "Longitude", "Depth"]
            events.index.names = ["Event"]

            ### READ PHASE BLOCK ###
            phase_block = lines[4:]
            phase_block_dic = {}
            for line in phase_block:
                station = line[0:5].strip()
                phase = line[19:27].strip()
                tt_residual = line[41:46].strip()
                onset_quality = line[101]

                if station.isalnum() and phase.isalnum() and phase in Phases:
                    try:
                        try:
                            arrival_time = dt.datetime.strptime(line[28:40].strip(), "%H:%M:%S.%f")
                        except:
                            arrival_time = dt.datetime.strptime(line[28:40].strip(), "%H:%M:%S")
                        arrival_time = arrival_time.time()
                        # To compare the arrival times in order to check
                        # whether a one-day jump in date (24 hours) is needed
                        # for those phases arriving after midnight (00:00:00 am).
                        if arrival_time < origin_time:
                            arrival_date = origin_date + dt.timedelta(days=1)
                        else:
                            arrival_date = origin_date + dt.timedelta(days=0)

                        if any(tt_residual):
                            tt_residual = float(tt_residual)
                        else:
                            tt_residual = "N/A"

                        pick_uncertainty = cls.qual2err(phase, onset_quality)

                        # To check if any station renaming must be done.
                        if station in isc_alter2prime_dic.keys():
                            station = isc_alter2prime_dic[station]
                        if station in cls.isc2gfn_alias_dic.keys():
                            station = cls.isc2gfn_alias_dic[station]
                        elif station in cls.isc2gfn_duplicate_dic.keys():
                            station = cls.isc2gfn_duplicate_dic[station]
                        elif station in gfn_sta2net_dic.keys():
                            station = gfn_sta2net_dic[station]

                        if station not in stations:
                            stations.append(station)
                        if (station, phase) not in phase_block_dic.keys():
                            phase_block_dic[station, phase] = []
                        phase_block_dic[station, phase].append((onset_quality,
                                                                arrival_date,
                                                                arrival_time,
                                                                pick_uncertainty,
                                                                tt_residual))
                    except:
                        continue

            ### WRITE NLLOC OBSERVATION FILE ###
            outFile = open(os.path.join(output_dir, ''.join(('isc', eventID, '.nll'))), "w")
            # write origin block and phase header
            for line in lines[:3]:
                outFile.write(line + "\n")
            outFile.write("PHASE ID Ins Cmp On Pha  FM  Date      HrMn   Sec   " +\
                          "Err   ErrMag  Coda Amp Per  >  Res\n")
            # write phase block
            for k in sorted(phase_block_dic.keys(),
                            key=lambda x: (phase_block_dic[x][0][1], phase_block_dic[x][0][2])):
                station, phase = k[:]
                if len(phase_block_dic[k]) > 1:
                    pick_list = phase_block_dic[k]
                    dummy = cls.average_pick(origin_date, origin_time, pick_list)
                else:
                    dummy = phase_block_dic[k][0]

                # ID, Ins, Cmp, On, Pha, FM, Date, HrMn, Sec, Err, ErrMag, Coda, Amp, Per > Res
                dummy_line = "%s  ?  ?  %s  %s  ?  %4d%02d%02d  %02d%02d  %5.2f  GAU  %7.1f  -1  -1  -1  >  %s" \
                             % (station.ljust(8), dummy[0], phase.ljust(5),
                                dummy[1].year,dummy[1].month,dummy[1].day,
                                dummy[2].hour,dummy[2].minute,
                                dummy[2].second+(dummy[2].microsecond/1.0e6),
                                dummy[3], str(dummy[4]).rjust(6))
                outFile.write(dummy_line + '\n')
            outFile.close()

        print "[ %s ] Done\n" % u'\u2713'
        return cls(events, stations)