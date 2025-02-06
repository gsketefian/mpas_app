"""
Creates the experiment directory and populates it with necessary configuration and workflow files.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from shutil import copy
from subprocess import STDOUT, CalledProcessError, check_output
from typing import Optional

import uwtools.api.config as uwconfig
import uwtools.api.rocoto as uwrocoto
from uwtools.api.logging import use_uwtools_logger
from uwtools.config.formats.base import Config

from pprint import pprint


#def main(user_config_files: list[Path, str]) -> None:
def main():
    """
    Stage the Rocoto XML and experiment YAML in the desired experiment
    directory.
    """

    # Set up the experiment
    # mpas_app is the base directory of the MPAS App clone on the local
    # platform.
    mpas_app = Path(os.path.dirname(__file__)).parent.absolute()
    experiment_config = uwconfig.get_yaml_config(Path("./experiment.yaml"))

#    print(f'')
#    print(f'AAAAAAAAAA')

    mpas_app = Path(os.path.dirname(__file__)).parent.absolute()

    experiment_dir = experiment_config["user"]["experiment_dir"]
    launch_log_fn = experiment_config["cron"]["wflow_launch_log_fn"]
    launch_log_fp = os.path.join(experiment_dir, launch_log_fn)
    launch_log_fp = os.path.abspath(launch_log_fp)

    # Initialize the workflow status.
    wflow_status = "IN PROGRESS"

    # Issue the rocotorun command to (re)launch the next task in the workflow.
    #cmd = f"rocotorun -w rocoto.xml -d rocoto.db -v 10 >> {launch_log_fp} 2>&1"
    cmd = f"rocotorun -w rocoto.xml -d rocoto.db -v 10"
    print(f'')
    print(f'Running command:')
    print(f'  {cmd}')
    try:
        output_rocotorun = check_output([cmd], shell=True, stderr=STDOUT, encoding='utf-8')
    except CalledProcessError as e:
        output_rocotorun = e.output
        print("Error running command:")
        print(f"  {cmd}")
        for line in output_rocotorun.split("\n"):
            print(line)
        print(f"Failed with status: {e.returncode}")
        sys.exit(1)

    print(f'')
    print(f'Output:')
    if output_rocotorun:
        print(output_rocotorun)
    else:
        print(f'    [No output]')

    # Check for error messages in the output of rocotorun.  If any are found,
    # it means the end-to-end run of the workflow failed.  In that case, set
    # the workflow status to "FAILURE".
    error_msgs = ['sbatch: error: Batch job submission failed:']
    for error_msg in error_msgs:
        if error_msg in output_rocotorun:
            wflow_status = "FAILURE"
            break

#    print(f'')
#    print(f'PPPPPPPPPPPPPPPPPPP')
#    print(f'{wflow_status = }')

    # Issue the rocotostat command to obtain a table specifying the status
    # of each task.
#    cmd = f"rocotostat -w rocoto.xml -d rocoto.db -v 10 >> {launch_log_fp} 2>&1"
    cmd = f"rocotostat -w rocoto.xml -d rocoto.db -v 10"
    print(f'')
    print(f'Running command:')
    print(f'  {cmd}')
    try:
        output_rocotostat = check_output([cmd], shell=True, stderr=STDOUT, encoding='utf-8')
    except CalledProcessError as e:
        output_rocotostat = e.output
        print("Error running command:")
        print(f"  {cmd}")
        for line in output_rocotostat.split("\n"):
            print(line)
        print(f"Failed with status: {e.returncode}")
        sys.exit(1)

    print(f'')
    print(f'Output:')
    if output_rocotostat:
        print(output_rocotostat)
    else:
        print(f'    [No output]')

    # Check for dead tasks in the output of rocotostat. If any are found, it
    # means the end-to-end run of the workflow failed.  In that case, set the
    # workflow status to "FAILURE".
    error_msgs = ['DEAD']
    #error_msgs = ['DEAD', 'TASK']
    for error_msg in error_msgs:
#        print(f'')
#        print(f'{error_msg = }')
#        print(f'{output_rocotostat = }')
        if error_msg in output_rocotostat:
            wflow_status = "FAILURE"
            break

#    print(f'')
#    print(f'QQQQQQQQQQQQQQQQQ')
#    print(f'{wflow_status = }')

    #
    #-----------------------------------------------------------------------
    #
    # Use the rocotostat command with the "-s" flag to obtain a summary of
    # the status of each cycle in the workflow.  The output of this command
    # has the following format:
    #
    #   CYCLE         STATE           ACTIVATED              DEACTIVATED
    # 201905200000      Active    Nov 07 2019 00:23:30             -
    # ...
    #
    # Thus, the first row is a header line containing the column titles, and
    # the remaining rows each correspond to one cycle in the workflow.  Below,
    # we are interested in the first and second columns of each row.  The
    # first column is a string containing the start time of the cycle (in the
    # format YYYYMMDDHHmm, where YYYY is the 4-digit year, MM is the 2-digit
    # month, DD is the 2-digit day of the month, HH is the 2-digit hour of
    # the day, and mm is the 2-digit minute of the hour).  The second column
    # is a string containing the state of the cycle.  This can be "Active"
    # or "Done".  Below, we read in and store these two columns in (1-D)
    # arrays.
    #
    #-----------------------------------------------------------------------
    #
    cmd = f"rocotostat -w rocoto.xml -d rocoto.db -v 10 -s"
    print(f'')
    print(f'Running command:')
    print(f'  {cmd}')
    try:
        output_rocotostat = check_output([cmd], shell=True, stderr=STDOUT, encoding='utf-8')
    except CalledProcessError as e:
        output_rocotostat = e.output
        print("Error running command:")
        print(f"  {cmd}")
        for line in output_rocotostat.split("\n"):
            print(line)
        print(f"Failed with status: {e.returncode}")
        sys.exit(1)

    print(f'')
    print(f'Output:')
    if output_rocotostat:
        print(output_rocotostat)
    else:
        print(f'    [No output]')

    output_rocotostat = output_rocotostat.splitlines()
    # Drop the first line since it only contains headers.
    output_rocotostat.pop(0)
#    print(f'')
#    print(output_rocotostat)

    cycle_status = {}
    for line in output_rocotostat:
        result = line.split()
        cycle_status[result[0]] = result[1]

    num_cycles = len(cycle_status)
#    print(f'')
#    print(f'{num_cycles = }')
    num_cycles_completed = sum(1 for status in cycle_status.values() if status == 'Done')
#    print(f'{num_cycles_completed = }')

    # If the number of completed cycles is equal to the total number of cycles,
    # it means the end-to-end run of the workflow was successful.  In this
    # case, we reset the wflow_status to "SUCCESS".
    if num_cycles_completed == num_cycles:
        wflow_status = "SUCCESS"

    print(f'')
#    print(f'RRRRRRRRRRRRRRRRRRRRR')
    print(f'{wflow_status = }')




if __name__ == "__main__":

    use_uwtools_logger()

    parser = argparse.ArgumentParser(
        description="Launch an experiment."
    )

#    parser.add_argument(
#            "user_config_files",
#            nargs="+",
#            help="Paths to the user config files.")

#    args = parser.parse_args()
#    path_list = [Path(p) for p in args.user_config_files]
#    main(user_config_files=path_list)
    main()

