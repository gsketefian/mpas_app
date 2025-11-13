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

from get_crontab_contents import add_crontab_line
from pprint import pprint
from textwrap import dedent
from datetime import datetime

def create_grid_files(expt_dir: Path, mesh_file_path: Path, nprocs: int) -> None:
    """
    Stage the mesh file in the experiment directory and decompose them for the current experiment.
    """
    copy(src=mesh_file_path, dst=expt_dir)
    mesh_file = expt_dir / mesh_file_path.name
    cmd = f"gpmetis -minconn -contig -niter=200 {mesh_file} {nprocs}"
    try:
        output = check_output(
            cmd, encoding="utf=8", shell=True, stderr=STDOUT, text=True
        )
    except CalledProcessError as e:
        output = e.output
        print("Error running command:")
        print(f"  {cmd}")
        for line in output.split("\n"):
            print(line)
        print(f"Failed with status: {e.returncode}")
        sys.exit(1)


def main(user_config_files: list[Path, str]) -> None:
    """
    Stage the Rocoto XML and experiment YAML in the desired experiment
    directory.
    """

    # Set up the experiment
    # mpas_app is the base directory of the MPAS App clone on the local
    # platform.
    mpas_app = Path(os.path.dirname(__file__)).parent.absolute()
    experiment_config = uwconfig.get_yaml_config(Path("./default_config.yaml"))
    user_config = None
    for cfg_file in user_config_files:
        cfg = uwconfig.get_yaml_config(cfg_file)
        if not user_config:
            user_config = cfg
            continue
        user_config.update_values(cfg)

    machine = user_config["user"]["platform"]
    platform_config = uwconfig.get_yaml_config(mpas_app / "parm" / "machines" / f"{machine}.yaml")

    for supp_config in (platform_config, user_config):
        experiment_config.update_values(supp_config)

    experiment_config["user"]["mpas_app"] = mpas_app.as_posix()



    # Get the specified experiment directory and convert it to a PosixPath
    # object.
    experiment_dir = experiment_config["user"]["experiment_dir"]
    if not experiment_dir: experiment_dir = ''
    experiment_dir = Path(experiment_dir)

    # If experiment_dir is a relative path, prepend to it the default base
    # directory in which experiment directories are created. 
    if not os.path.isabs(experiment_dir):
        experiment_dir = Path(mpas_app) / '..' / 'expt_dirs' / experiment_dir

    # Resolve the path to get rid of '.', '..', symlinks, etc.
    experiment_dir = experiment_dir.resolve()

    print(f'{experiment_dir = }')


    # If create_expt_name in the config file is set to True, form a name
    # for the experiment from the names of the config files passed on the
    # command line.
    create_expt_name = experiment_config["user"]["create_expt_name"]
    if not create_expt_name:
        expt_name = ''
    else:
        # Get the name of the experiment from the name of the last user config file
        # specified on the command line.
        last_config_file = str(user_config_files[-1])
#        start_str = 'config.'
#        end_str = '.yaml'
#        start_index = last_config_file.find(start_str) + len(start_str)
#        end_index = last_config_file.find(end_str, start_index)
#        expt_name = last_config_file[start_index:end_index]
        # Set the experiment name to the substring between the last two dots in the
        # name of the config file specified on the command line.  For example, if
        # the name of that config file is config.abc.def.yaml, then the name of the
        # experiment (thus far) will be "def".
        substr = '.'
        substr_count = last_config_file.count(substr)
        if substr_count < 2:
            msg = dedent(f"""
                There must be at least two occurrences of the substring '{substr}' in the name
                of the last configuration file specified on the command line (last_config_file),
                but this is not the case:
                    {last_config_file = }
                    {substr_count = }
                Stopping.
                """)
            logging.error(msg)
            raise ValueError(msg)
        else:
            last_index = last_config_file.rfind(substr)
            next_to_last_index = last_config_file.rfind(substr, 0, last_index)
            expt_name = last_config_file[next_to_last_index+1:last_index]

        # Add the mesh name (label) to the start of the experiment name.
        mesh_label = experiment_config["user"]["mesh_label"]
        expt_name = '.'.join([mesh_label, expt_name])

    print(f"{expt_name = }")

    # Append the experiment name to experiment_dir to get the final experiment
    # path.  Then resolve the path.
    experiment_path = experiment_dir / expt_name
    experiment_path = experiment_path.resolve()
    print(f'{experiment_path = }')

    # Reset experiment_dir in the config dictionary to the final path created above.
    experiment_config["user"]["experiment_dir"] = str(experiment_path)


    if experiment_path.exists():
        # If the experiment directory already exists, rename it by appending the
        # current date and time to its name.
        crnt_datetime = datetime.now()
        crnt_datetime_str = crnt_datetime.strftime("%Y%m%d_%H%M%S")
        expt_name_old = '.'.join([expt_name, crnt_datetime_str])
        experiment_path_renamed = experiment_path / '..'/ expt_name_old
        experiment_path_renamed = experiment_path_renamed.resolve()
        msg = dedent(f"""
            The experiment directory (experiment_path) already exists:
                {experiment_path = }
            Moving (renaming) existing directory to:
                {experiment_path_renamed = }
            """)
        logging.info(msg)
        experiment_path.rename(experiment_path_renamed)

    # Build the experiment directory
    experiment_path = Path(experiment_config["user"]["experiment_dir"])
    print("Experiment will be set up here: {}".format(experiment_path))
    os.makedirs(experiment_path, exist_ok=True)

    # Get configuration parameters associated with launching the workflow.
    wflow_launch_config = experiment_config["wflow_launch"]
    wflow_launch_script_fn = wflow_launch_config["launch_script_fn"]
    wflow_launch_wrapper_fn = wflow_launch_config["launch_wrapper_fn"]

    # Copy the workflow launch script and wrapper script that runs it from
    # the MPAS App clone into the experiment directory.    
    wflow_launch_script_fp = mpas_app / 'ush' / wflow_launch_script_fn
    copy(wflow_launch_script_fp, experiment_path / wflow_launch_script_fn)
    wflow_launch_wrapper_fp = mpas_app / 'ush' / wflow_launch_wrapper_fn
    copy(wflow_launch_wrapper_fp, experiment_path / wflow_launch_wrapper_fn)
    #
    # -----------------------------------------------------------------------
    #
    # If use_cron_to_relaunch is set to True, add a line to the user's cron
    # table to call the (re)launch script every cron_relaunch_intvl_mnts
    # minutes.
    #
    # -----------------------------------------------------------------------
    #
    # Get cron configuration.
    cron_config = experiment_config["cron"]
    use_cron_to_relaunch = cron_config["use_cron_to_relaunch"]

    if use_cron_to_relaunch:

        cron_relaunch_intvl_mnts = cron_config["cron_relaunch_intvl_mnts"]
        wflow_launch_log_fn = wflow_launch_config["launch_log_fn"]
        platform = experiment_config["user"]["platform"]

        crontab_line = (
            f"""*/{cron_relaunch_intvl_mnts} * * * * """
            f"""cd {experiment_path} && """
            f"""./{wflow_launch_wrapper_fn} >> ./{wflow_launch_log_fn} 2>&1"""
        )

        experiment_config["cron"]["crontab_line"] = crontab_line

        print(f'')
        print(f"Will include the following cron job in the user's cron table:")
        print(f'{crontab_line = }')

        add_crontab_line(called_from_cron=False, machine=platform,
                         crontab_line=crontab_line,
                         exptdir=experiment_path, debug=False)



    # Load the workflow definition
    workflow_blocks = experiment_config["user"]["workflow_blocks"]
    workflow_blocks = [mpas_app / "parm" / "wflow" / b for b in workflow_blocks]

    workflow_config = None
    for workflow_block in workflow_blocks:
        if workflow_config is None:
            workflow_config = uwconfig.get_yaml_config(workflow_block)
        else:
            workflow_config.update_values(uwconfig.get_yaml_config(workflow_block))
    workflow_config.update_values(experiment_config)

    experiment_file = experiment_path / Path("experiment.yaml")
    uwconfig.realize(
        input_config=workflow_config,
        output_file=experiment_file,
        update_config={},
    )

    # Create the workflow files
    rocoto_xml = experiment_path / Path("rocoto.xml")
    rocoto_valid = uwrocoto.realize(config=experiment_file, output_file=rocoto_xml)
    if not rocoto_valid:
        sys.exit(1)

    # Create grid files
    mesh_file_name = f"{experiment_config['user']['mesh_label']}.graph.info"
    mesh_file_path = Path(experiment_config["data"]["mesh_files"]) / mesh_file_name

    experiment_config = uwconfig.get_yaml_config(config=experiment_file)
    all_nprocs = []
    for sect, driver in (
        ("create_ics", "mpas_init"),
        ("create_lbcs", "mpas_init"),
        ("forecast", "mpas"),
        ):
        if sect in experiment_config:
            resources = experiment_config[sect][driver]["execution"]["batchargs"]
            if (cores := resources.get("cores")) is None:
                cores = resources["nodes"] * resources["tasks_per_node"]
            all_nprocs.append(cores)
    for nprocs in all_nprocs:
        if not (experiment_path / f"{mesh_file_path.name}.part.{nprocs}").is_file():
            print(f"Creating grid partitioning file for {nprocs} procs")
            create_grid_files(experiment_path, mesh_file_path, nprocs)


if __name__ == "__main__":

    use_uwtools_logger()

    parser = argparse.ArgumentParser(
        description="Configure an experiment with the following input:"
    )
    parser.add_argument(
            "user_config_files",
            nargs="+",
            help="Paths to the user config files.")

    args = parser.parse_args()
    path_list = [Path(p) for p in args.user_config_files]
    main(user_config_files=path_list)
