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

from textwrap import dedent
from pprint import pprint

#from get_crontab_contents import add_crontab_line

#def main(user_config_files: list[Path, str]) -> None:
def main():
    """
    Description.
    """

#    # mpas_app is the base directory of the MPAS App clone on the local
#    # platform.
#    mpas_app = Path(os.path.dirname(__file__)).parent.absolute()

    # Get experiment configuration and set various parameters.
    experiment_config = uwconfig.get_yaml_config(Path("./experiment.yaml"))
    mpas_app = experiment_config["user"]["mpas_app"]
    expt_dir = experiment_config["user"]["experiment_dir"]
    expt_name = os.path.basename(os.path.normpath(expt_dir))

    wflow_launch_log_fn = experiment_config["wflow_launch"]["launch_log_fn"]
    wflow_launch_log_fp = os.path.join(expt_dir, wflow_launch_log_fn)
    wflow_launch_log_fp = os.path.abspath(wflow_launch_log_fp)

    # Initialize the workflow status.
    wflow_status = "IN PROGRESS"

    # Issue the rocotorun command to (re)launch the next task in the workflow.
    #cmd = f"rocotorun -w rocoto.xml -d rocoto.db -v 10 >> {launch_log_fp} 2>&1"
    cmd = f"rocotorun -w rocoto.xml -d rocoto.db -v 10"
    print(f'')
    print(f'Running command:')
    print(f'    {cmd}')
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

    # Issue the rocotostat command to obtain a table specifying the status
    # of each task.
#    cmd = f"rocotostat -w rocoto.xml -d rocoto.db -v 10 >> {launch_log_fp} 2>&1"
    cmd = f"rocotostat -w rocoto.xml -d rocoto.db -v 10"
    print(f'')
    print(f'Running command:')
    print(f'    {cmd}')
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
    for error_msg in error_msgs:
        if error_msg in output_rocotostat:
            wflow_status = "FAILURE"
            break
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
    print(f'    {cmd}')
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

    cycle_status = {}
    for line in output_rocotostat:
        result = line.split()
        cycle_status[result[0]] = result[1]

    num_cycles = len(cycle_status)
    num_cycles_completed = sum(1 for status in cycle_status.values() if status == 'Done')

    # If the number of completed cycles is equal to the total number of cycles,
    # it means the end-to-end run of the workflow was successful.  In this
    # case, we reset the wflow_status to "SUCCESS".
    if num_cycles_completed == num_cycles:
        wflow_status = "SUCCESS"

    print(f'')
    print(f'{wflow_status = }')
    #
    #-----------------------------------------------------------------------
    #
    # If the workflow status (wflow_status) has been set to either "SUCCESS"
    # or "FAILURE", indicate this by appending an appropriate workflow
    # completion message to the end of the launch log file.
    #
    #-----------------------------------------------------------------------
    #
    # For debugging:
    wflow_status = 'SUCCESS'
    if wflow_status in ['SUCCESS', 'FAILURE']:

        msg = dedent(f"""
            The end-to-end run of the workflow for the forecast experiment specified
            by expt_name has completed with the following workflow status (wflow_status):
                {expt_name = }
                {wflow_status = }
            """)

        # If a cron job was being used to periodically relaunch the workflow, we
        # now remove the entry in the crontab corresponding to the workflow
        # because the end-to-end run of the workflow has now either succeeded or
        # failed and will remain in that state without manual user intervention.
        # Thus, there is no need to try to relaunch it.  We also append a message
        # to the completion message above to indicate this.
        use_cron_to_relaunch = experiment_config["cron"]["use_cron_to_relaunch"]

        if use_cron_to_relaunch:
  
            crontab_line = experiment_config["cron"]["crontab_line"]
            msg = msg + dedent(f"""
                Removing from the crontab the line (crontab_line) that calls the workflow
                launch script for this experiment:
                    crontab_line = "{crontab_line}"
                """).lstrip()
#            print(f"")
#            print(f"EEEEEEEEEEEEEEEEE")
#            print(f"msg = {msg}")
            print(msg)

            # Remove crontab_line from cron table.
            ushdir = os.path.join(mpas_app, 'ush')
            platform = experiment_config["user"]["platform"]
            called_from_cron = False
            if called_from_cron:
                cmd = f"python3 {ushdir}/get_crontab_contents.py --remove -m=${platform} -l='{crontab_line}' -c -d"
            else:
                cmd = f"python3 {ushdir}/get_crontab_contents.py --remove -m=${platform} -l='{crontab_line}' -d"

            print(f'')
            print(f'Running command:')
            print(f'    {cmd}')
            try:
                output = check_output([cmd], shell=True, stderr=STDOUT, encoding='utf-8')
            except CalledProcessError as e:
                output = e.output
                print("Error running command:")
                print(f"  {cmd}")
                for line in output_rocotostat.split("\n"):
                    print(line)
                print(f"Failed with status: {e.returncode}")
                sys.exit(1)
    #
    # Print the workflow completion message to the launch log file.
    #
        with open(wflow_launch_log_fp, "a") as file:
            file.write(msg)
    #
    # If the stdout from this script is being sent to the screen (e.g. it is
    # not being redirected to a file), then also print out the workflow
    # completion message to the screen.
    #
#        if [ -t 1 ]; then
#            printf "%s" "$msg"





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

