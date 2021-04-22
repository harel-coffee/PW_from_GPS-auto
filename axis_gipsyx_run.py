#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 20 16:56:59 2021
dataRecordDump -rnx Ohad103D.21d.gz -drFileNmOut Ohad103D.21d.dr.gz
drMerge.py -i *.dr.gz -o merged.dr.gz
gd2e.py -drEditedFile merged.dr.gz -GNSSproducts ultra -staDb ~/Python_Projects/PW_from_GPS/AXIS.staDb -treeS ~/Python_Projects/PW_from_GPS/my_trees/AXISOcnld/ -recList RAMO OHAD
create folders in axis/2021/103 like final, rapid and ultra with solutions and extra files every hour for all stations
first do datarecorddump for all hourly files and then merge them together
use this func to do it seperately from main gipsyx run
@author: ziskin
"""

def move_files(path_orig, path_dest, files, out_files=None, verbose=False):
    """move files (a list containing the file names) and move them from
    path_orig to path_dest"""
    import shutil
    import logging
    logger = logging.getLogger('gipsyx')
    if isinstance(files, str):
        files = [files]
    if out_files is not None:
        if isinstance(out_files, str):
            out_files = [out_files]
    orig_filenames_paths = [path_orig / x for x in files]
    if out_files is None:
        out_files = files
    dest_filenames_paths = [path_dest / x for x in out_files]
    # delete files if size =0:
    for file, orig, dest in zip(
            files, orig_filenames_paths, dest_filenames_paths):
        # check for file existance in orig:
        if not orig.is_file():
            if verbose:
                logger.warning('{} does not exist in {}'.format(file, orig))
            continue
        # check if its size is 0:
        if orig.stat().st_size == 0:
            orig.resolve().unlink()
        else:
            shutil.move(orig.resolve(), dest.resolve())
    return


def check_year(year):
    import datetime
    now = datetime.datetime.now()
    year = int(year)
    if year < 1980 or year > now.year:
        raise argparse.ArgumentTypeError('{} is not a valid year'.format(year))
    return year


def check_path(path):
    import os
    path = str(path)
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(path + ' does not exist...')
    return Path(path)


def check_file_in_cwd(filename):
    cwd = Path().cwd()
    file_and_path = cwd / filename
    if not file_and_path.is_file():
        raise argparse.ArgumentTypeError(
            '{} does not exist at {}'.format(
                filename, cwd))
    return file_and_path


def record_dump_and_merge(args):
    # import os
    import logging
    from aux_gps import path_glob
    logger = logging.getLogger('axis-gipsyx')
    if args.mode is None:
        mode = 'whole'
    else:
        mode = args.mode
    if args.year is None:
        year = 2021
    else:
        year = args.year
    if mode == 'last_doy':
        # check for doy folders in args.rinexpath and flag last_doy:
        doys = sorted(path_glob(args.rinexpath / str(year), '*/'))
        doys = sorted([x for x in doys if x.is_dir()])
        last_doy = doys[-1].as_posix().split('/')[-1]
        logger.info('drRecordDump on year {}, doy {}, using last_doy'.format(year, last_doy))
        record_dump_and_merge_at_single_folder(doys[0], args.drmerger, args.staDb)
    elif mode == 'whole':
        doys = sorted(path_glob(args.rinexpath / str(year), '*/'))
        doys = sorted([x for x in doys if x.is_dir()])
        for doy in doys:
            current_doy = doy.as_posix().split('/')[-1]
            logger.info('drRecordDump on year {}, doy {},using whole data'.format(year, current_doy))
            record_dump_and_merge_at_single_folder(doy, args.drmerger, args.staDb)
    return


def record_dump_and_merge_at_single_folder(rinexpath, drmerger, staDb):
    """search for hourly rinex in folder for all stations and convert them to dr.gz
    then merge them together"""
    import subprocess
    import os
    import logging
    from aux_gps import path_glob
    import string
    from subprocess import CalledProcessError
    # from subprocess import TimeoutExpired
    logger = logging.getLogger('axis-gipsyx')
    # cnt = {'succ': 0, 'failed': 0}
    # first check for rinexpath / dr, if doesn't exist create it:
    dr_path = rinexpath / 'dr'
    if not (dr_path).is_dir():
        os.mkdir(dr_path)
    # next check if performing hourly all stations, or daily one/all stations:
    logger.info('performing {} drmerger for all rinex files.'.format(drmerger))
    if drmerger == 'hourly':
        hours = [x.upper() for x in string.ascii_letters][:24]
        for hour in hours:
            try:
                files = path_glob(rinexpath, '*{}.*.gz'.format(hour))
            except FileNotFoundError:
                logger.warning('hour {} not found in rinex files.'.format(hour))
                continue
            dr_files = []
            stations = []
            doy = files[0].as_posix().split('/')[-1][0:12][4:7]
            merged_file = dr_path / 'merged_{}_{}.dr.gz'.format(doy, hour)
            if (merged_file).is_file():
                logger.warning('{} already exists in {}, skipping...'.format(merged_file, dr_path))
                continue
            for file in files:
                # rinex 2.11 filename:
                filename = file.as_posix().split('/')[-1][0:12]
                stn = filename[0:4].upper()
                dr_file = dr_path / (filename + '.dr.gz')
                dr_filename = dr_path / filename
                command = 'dataRecordDump -rnx {} -drFileNmOut {} > {}.log 2>{}.err'.format(
                    file.as_posix(), dr_file.as_posix(), dr_filename, dr_filename)
                try:
                    subprocess.run(command, shell=True, check=True)
                    dr_files.append(dr_file)
                    # keep station names that were succesufully dred:
                    stations.append(filename[0:4])
                    # cnt['succ'] += 1
                except CalledProcessError:
                    logger.error(
                        'dataRecordDump failed on {}, deleting file.'.format(filename))
                    dr_file.unlink()
                # now rnxedit:
                dr_edited_file = dr_path / (filename + '.dr_edited.gz')
                command = 'rnxEditGde.py -type datarecord -recNm {} -data {} -out {} -staDb {} > {}.log 2>{}.err'.format(
                    stn, dr_file.as_posix(), dr_edited_file.as_posix(),
                    staDb.as_posix(), filename, filename)
                try:
                    subprocess.run(command, shell=True, check=True)
    #                next(succ)
                # cnt['succ'] += 1
                except CalledProcessError:
    #                next(failed)
                    # cnt['failed'] += 1
                    logger.error('rnxEditGde.py failed on {}...'.format(filename))
                    dr_edited_file.unlink()
                    # cnt['failed'] += 1
            # now merge all dr files :
            logger.info(
                'merging dr files in doy {}, hour {}.'.format(doy, hour))
            merged_glob = dr_path / '*{}{}.*.dr_edited.gz'.format(doy, hour)
            merged_filename = dr_path / 'merged_{}_{}'.format(doy, hour)
            command = 'drMerge.py -i {} -o {} > {}.log 2>{}.err'.format(
                merged_glob.as_posix(), merged_file.as_posix(), merged_filename,
                merged_filename)
            try:
                subprocess.run(command, shell=True, check=True)
                # also create txt file with station names inside merged file:
                with open('{}.txt'.format(merged_filename.as_posix()), "w") as outfile:
                    outfile.write("\n".join(stations))
            except CalledProcessError:
                logger.error('drMerge.py failed on {}...'.format(
                    merged_glob.as_posix()))
                return
            # now delete all single dr (whom i already merged):
            [x.unlink() for x in dr_files]
    elif drmerger == 'daily':
        files = path_glob(rinexpath, '*.gz')
        dr_files = []
        stations = []
        for file in files:
            # rinex 2.11 filename:
            filename = file.as_posix().split('/')[-1][0:12]
            doy = filename[4:7]
            merged_file = dr_path / 'merged_{}.dr.gz'.format(doy)
            if (merged_file).is_file():
                logger.warning('{} already exists in {}, skipping...'.format(merged_file, dr_path))
                continue
            dr_file = dr_path / (filename + '.dr.gz')
            dr_filename = dr_path / filename
            command = 'dataRecordDump -rnx {} -drFileNmOut {} > {}.log 2>{}.err'.format(
                file.as_posix(), dr_file.as_posix(), dr_filename, dr_filename)
            try:
                subprocess.run(command, shell=True, check=True)
                dr_files.append(dr_file)
                stations.append(filename[0:4])
                # cnt['succ'] += 1
            except CalledProcessError:
                logger.error('dataRecordDump failed on {}, deleting file.'.format(filename))
                dr_file.unlink()
                # cnt['failed'] += 1
        # now merge all dr files :
        logger.info('merging dr files in doy {}.'.format(doy))
        merged_file = dr_path / 'merged_{}.dr.gz'.format(doy)
        merged_filename = dr_path / 'merged_{}'.format(doy)
        merged_glob = dr_path / '*{}*.*.dr.gz'.format(doy)
        command = 'drMerge.py -i {} -o {} > {}.log 2>{}.err'.format(
            merged_glob.as_posix(), merged_file.as_posix(), merged_filename, merged_filename)
        try:
            subprocess.run(command, shell=True, check=True)
            with open('{}.txt'.format(merged_filename.as_posix()), "w") as outfile:
                outfile.write("\n".join(stations))
        except CalledProcessError:
            logger.error('drMerge.py failed on {}...'.format(
                merged_glob.as_posix()))
        # now delete all single dr (whom i already merged):
        [x.unlink() for x in dr_files]
    # now delete all log and err files if empty:
    log_files = path_glob(dr_path, '*.log')
    for lfile in log_files:
        if lfile.stat().st_size == 0:
            lfile.unlink()
    err_files = path_glob(dr_path, '*.err')
    for efile in err_files:
        if efile.stat().st_size == 0:
            efile.unlink()
    return


def run_gd2e(args):
    import subprocess
    import logging
    logger = logging.getLogger('axis-gipsyx')
    return


def run_gd2e_single_dr_path(dr_path, staDb, tree, acc='ultra', n_proc=4, network_name='axis'):
    """runs gd2e.py for all datarecodrs in one folder(dr_path) with staDb.
    """
    from pathlib import Path
    import subprocess
    # from itertools import count
    from subprocess import CalledProcessError
    from subprocess import TimeoutExpired
    import logging
    # from aux_gps import get_timedate_and_station_code_from_rinex
    from aux_gps import path_glob
    # from aux_gps import slice_task_date_range
    import pandas as pd
    from axis_process import read_multi_station_tdp_file
    logger = logging.getLogger('axis-gipsyx')
    logger.info(
        'starting gd2e.py main gipsyX run.')
    logger.info('working with {} station database'.format(staDb))
    results_path = dr_path / acc
    if tree.as_posix().strip():
        logger.info('working with {} tree'.format(tree))
    try:
        results_path.mkdir()
    except FileExistsError:
        logger.info(
            '{} already exists, using that folder.'.format(results_path))
#    succ = count(1)
#    failed = count(1)
    # cnt = {'succ': 0, 'failed': 0}
    files = path_glob(dr_path, 'merged_*.dr.gz')
    tot = len(files)
    logger.info('found {} merged dr.gz files in {} to run.'.format(tot, dr_path))
    tot_final = len(path_glob(results_path, '*_smoothFinal.tdp', True))
    # logger.info('found {} _smoothFinal.tdp files in {}'.format(tot_final,
                # results_path))
    # tot_to_run = tot - tot_final
    # est_time_per_single_run = 22.0  # seconds
    # dtt = pd.to_timedelta(est_time_per_single_run, unit='s') * tot_to_run
    # logger.info('estimated time to completion of run: {}'.format(dtt))
    # logger.info('check again in {}'.format(pd.Timestamp.now() + dtt))
    for file_and_path in sorted(files):
        merged = file_and_path.as_posix().split('/')[-1][0:12].split('_')
        doy = merged[1]
        try:
            hour = merged[2]
            out_name = '{}_{}_{}'.format(network_name, doy, hour)
            # final_tdp = '{}_{}_{}_smoothFinal.tdp'.format(network_name, doy, hour)
            logger.info('running gd2e on merged dr file, doy {}, hour {}'.format(doy, hour))
        except IndexError:
            # final_tdp = '{}_{}_smoothFinal.tdp'.format(network_name, doy)
            out_name = '{}_{}'.format(network_name, doy)
            logger.info('running gd2e on merged dr file, doy {}'.format(doy))
        # read stations merged txt file:
        stns_path = Path(str(file_and_path).replace('.dr.gz', '.txt'))
        df = pd.read_csv(stns_path, names=['station'])
        stns = [x.upper() for x in df['station'].unique()]
        rec_list = '{}'.format(' '.join(stns))
        # dt, station = get_timedate_and_station_code_from_rinex(rfn)
        
        # logger.info(
        #     'processing {} ({}, {}/{})'.format(
        #         rfn,
        #         dt.strftime('%Y-%m-%d'), cnt['succ'] + cnt['failed'], tot))
        # if not rewrite:
        #     if (results_path / final_tdp).is_file():
        #         logger.warning(
        #             '{} already exists in {}, skipping...'.format(
        #                 final_tdp, results_path))
        #         cnt['succ'] += 1
        #         continue
        command = 'gd2e.py -drEditedFile {} -recList {} -staDb {} -treeS {} -GNSSproducts {} -nProcessors {} > {}.log 2>{}.err'.format(
            file_and_path.as_posix(), rec_list, staDb.as_posix(), tree, acc,
            n_proc, out_name, out_name)
        files_to_move = ['{}{}'.format(out_name, x)
                         for x in ['.log', '.err']]
        more_files = ['finalResiduals.out', 'smoothFinal.tdp']
        more_files_new_name = ['{}_{}'.format(out_name, x) for x in more_files]
        try:
            subprocess.run(command, shell=True, check=True, timeout=300)
            ds = read_multi_station_tdp_file(dr_path/'smoothFinal.tdp',
                                             stns, savepath=dr_path)
            move_files(Path().cwd(), results_path, 'smoothFinal.nc',
                       '{}_smoothFinal.nc'.format(out_name))

            move_files(Path().cwd(), results_path, more_files,
                       more_files_new_name)
            move_files(Path().cwd(), results_path, 'Summary',
                       '{}_Summary.txt'.format(out_name))
            # next(succ)
            # cnt['succ'] += 1
        except CalledProcessError:
            logger.error('gipsyx failed on {}, copying log files.'.format(out_name))
            # next(failed)
            # cnt['failed'] += 1
        except TimeoutExpired:
            logger.error('gipsyx timed out on {}, copying log files.'.format(out_name))
            # next(failed)
            # cnt['failed'] += 1
            # with open(Path().cwd() / files_to_move[1], 'a') as f:
            #     f.write('GipsyX run has Timed out !')
        move_files(Path().cwd(), results_path, files_to_move)
        move_files(Path().cwd(), results_path, 'debug.tree', '{}_debug.tree'.format(out_name))
    logger.info('Done!')
    # total = next(failed) + next(succ) - 2
    # total = cnt['succ'] + cnt['failed']
#    succses = next(succ) - 2
#    failure = next(failed) - 2
    # logger.info('Total files: {}, success: {}, failed: {}'.format(
            # total, cnt['succ'], cnt['failed']))
    return

if __name__ == '__main__':
    """"""
    import argparse
    import sys
    from aux_gps import configure_logger
    from aux_gps import get_var
    from pathlib import Path
    # first check for GCORE path:
    if get_var('GCORE') is None:
        raise ValueError('Run source ~/GipsyX-1.1/rc_GipsyX.sh first !')
    logger = configure_logger(name='axis-gipsyx')
    parser = argparse.ArgumentParser(
        description='a command line tool for preparing and running rinex files with gipsyX software.')
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
#    required.add_argument(
#        '--savepath',
#        help="a full path to save the raw output files, e.g., /home/ziskin/Work_Files/PW_yuval/gipsyx_resolved/TELA",
#        type=check_path)
    required.add_argument(
        '--rinexpath',
        help="a full path to the rinex path of the station, /home/ziskin/Work_Files/PW_yuval/rinex/TELA",
        type=check_path)
    optional.add_argument(
        '--staDb',
        help='add a station DB file for antennas and receivers in rinexpath',
        type=check_file_in_cwd)
    optional.add_argument(
        '--accuracy',
        help='the orbit and clock accuracy products',
        type=str, choices=['final', 'ql', 'ultra'])
    optional.add_argument(
        '--drmerger',
        help='use this to just drRecordump to dr folder and merge all hourly files for all available stations or daily of one station',
        type=str, choices=['daily', 'hourly'])
    optional.add_argument('--tree', help='gipsyX tree directory.',
                          type=check_path)
    optional.add_argument('--mode', help='which mode to run', type=str,
                          choices=['last_doy', 'whole'])
    optional.add_argument('--year', help='year of rinex files', type=check_year)
    optional.add_argument('--n_proc', help='number of processors to solve rtgx', type=int)
    parser._action_groups.append(optional)  # added this line
    parser.set_defaults(rewrite=False)
    args = parser.parse_args()
    if args.accuracy is None:
        args.accuracy = 'ultra'
    if args.rinexpath is None:
        print('rinexpath is a required argument, run with -h...')
        sys.exit()
    if args.staDb is None:
        args.staDb = '$GOA_VAR/sta_info/sta_db_qlflinn'
    if args.drmerger is None:
        run_gd2e_single_dr_path(args.rinexpath, args.staDb, args.tree,
                                args.accuracy, n_proc=4, network_name='axis')
        # run_gd2e(args)
    else:
        record_dump_and_merge(args)