"""
Creates the experiment directory and populates it with necessary configuration and workflow files.
"""

import argparse
import logging
import os
import sys
import yaml
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

from copy import deepcopy
#from deepdiff import DeepDiff

def _fix_types(obj) -> None:
    """
    Recursively walk a config dict and fix string values that should be other
    types but were produced as strings by Jinja2 rendering:
      - 'true'/'false' (any case) -> Python bool (so f90nml writes .true./.false.)
      - '!remove'                  -> delete the key from its parent dict
      - integer strings            -> Python int
    """
    if isinstance(obj, dict):
        keys_to_remove = []
        for k, v in obj.items():
            if isinstance(v, str):
                if v.lower() == 'true':
                    obj[k] = True
                elif v.lower() == 'false':
                    obj[k] = False
                elif v == '!remove':
                    keys_to_remove.append(k)
                elif v.startswith('str:'):
                    obj[k] = v[4:]          # strip the prefix, keep as string
                # Remove any minus signs before checking if v consists of digits only.
                elif v.lstrip('-').isdigit():
                    obj[k] = int(v)
            else:
                _fix_types(v)
        for k in keys_to_remove:
            del obj[k]
    elif isinstance(obj, list):
        for item in obj:
            _fix_types(item)


def create_grid_files(expt_dir: Path, mesh_conn_fp: Path, nprocs: int) -> None:
    """
    Stage the mesh connectivity file in the experiment directory and use it 
    to create the mesh partitioning file for the specified number of MPI processes.
    """
    # If running in serial (nprocs set to 1), there is no need to create a mesh
    # partition file because MPAS doesn't read it.  In fact, gpmetis will return
    # with an error if the number of MPI processes passed to it is 1.  In this case,
    # to keep the mpas_app workflow's configuration file simple, we still generate
    # an empty partition file in the experiment's top-level directory.
    if nprocs == 1:
        mesh_part_fn = f"{mesh_conn_fp.name}.part.{nprocs}"
        mesh_part_fp = expt_dir / mesh_part_fn
        cmd = f"touch {mesh_part_fp}"
    else:
        copy(src=mesh_conn_fp, dst=expt_dir)
        mesh_file = expt_dir / mesh_conn_fp.name
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

    # Set mpas_app to the base directory of the MPAS App clone on the local
    # platform.  This is obtained from this file's path, which is in turn
    # assumed to be located one directory level below the MPAS App base
    # directory.
    mpas_app = Path(os.path.dirname(__file__)).parent.absolute()

    # Create a YAMLConfig object (which is pretty much a dictionary) containing
    # the user-specified configuration.  This is done using the set of user 
    # config files passed to this function.
    user_config = None
    for cfg_file in user_config_files:
        # Get the configuration in the current user config file.  Note that
        # get_yaml_config() creates and returns a YAMLConfig object containing
        # the raw config data in the specified file.  It just parses the YAML
        # without performing any Jinja2 rendering.  Note also that a YAMLConfig
        # object can be used like a regular dictionary.
        cfg = uwconfig.get_yaml_config(cfg_file)
        if not user_config:
            user_config = cfg
            continue
        # Update the values in user_config with the ones in cfg.  Note that
        # the update_values() method performs a deep (recursive) merge of one
        # config into another, modifying the target in place (but it does not
        # perform any Jinja2 rendering).
        user_config.update_values(cfg)

    # Use the realize_to_dict() function to resolve any Jinja2 variables in the
    # "user:" section of the user_config dictionary (really a YAMLConfig object.
    # This is necessary because in the "user:" section, the experiment_dir key
    # may have a dependency on the mesh_label key, and experiment_dir is needed
    # right away before the rest of user_config is rendered further below.
    tmp = deepcopy(user_config)
    rendered = uwconfig.realize_to_dict(input_config=tmp, update_config={})
#    user_section = rendered["user"]
#    user_config["user"] = user_section
    user_config["user"] = rendered["user"]

    # Get the name of the platform (machine) from the user_config dictionary.
    # From that, form the path to the platform config file.
    machine = user_config["user"]["platform"]
    platform_config = uwconfig.get_yaml_config(mpas_app / "parm" / "machines" / f"{machine}.yaml")

    # Get the default experiment configuration from the default config file.
    experiment_config = uwconfig.get_yaml_config(Path("./default_config.yaml"))

    # Update the default experiment config first with the platform config and
    # then with the user config.  Thus, the user config has highest priority.
    # The iteration variable "supp_config" probably stands for "supplemental
    # configuration".
    for supp_config in (platform_config, user_config):
        experiment_config.update_values(supp_config)

#    print(f'')
#    print(f'AAAAAAAAAAAAA')
#    print(f'{experiment_config = }')
#    lkasdfljasldkfjalsdkfjas

    experiment_config["user"]["mpas_app"] = mpas_app.as_posix()

    # Get the specified experiment base directory and convert it to a PosixPath
    # object.
    expt_basedir = experiment_config["user"]["expt_basedir"]
    if not expt_basedir: expt_basedir = ''
    # Convert string path to path object.
    expt_basedir = Path(expt_basedir)

    # If expt_basedir is a relative path or is an empty string, append it to 
    # the default base directory in which experiment directories are created
    # and save the result as the new value of expt_basedir.
    if not os.path.isabs(expt_basedir):
        expt_basedir = Path(mpas_app) / '..' / 'expt_dirs' / expt_basedir
    # Resolve the path to get rid of '.', '..', symlinks, etc.
    expt_basedir = expt_basedir.resolve()

    print(f'{expt_basedir = }')

    # Get the experiment name as specified in the config dictionary.  Also,
    # get the value of the create_expt_name_flag, which plays a role in 
    # setting the experiment name.
    expt_name = experiment_config["user"]["expt_name"]
    create_expt_name = experiment_config["user"]["create_expt_name"]

    # If expt_name is not specified (or is set to an empty string) or if
    # create_expt_name is True, construct an experiment name from the names
    # of the config file(s) passed to this script.  Otherwise, use the
    # expt_name from the config file set above.
    if not expt_name or create_expt_name:

        last_config_file = str(user_config_files[-1])

        sepstr = '.'
        sepstr_count = last_config_file.count(sepstr)
        if sepstr_count < 2:
            msg = dedent(f"""
                There must be at least two occurrences of the substring '{sepstr}' in the name
                of the last configuration file specified on the command line (last_config_file),
                but this is not the case:
                    {last_config_file = }
                    {sepstr_count = }
                Stopping.
                """)
            logging.error(msg)
            raise ValueError(msg)

        first_indx = last_config_file.find(sepstr)
        last_indx = last_config_file.rfind(sepstr)   # "r" in rfind stands for "rightmost" occurrence
        next_to_last_indx = last_config_file.rfind(sepstr, 0, last_indx)

        indx_end = last_indx
        if create_expt_name:
            indx_start = next_to_last_indx 
        else:
            indx_start = first_indx
        expt_name = last_config_file[indx_start+1:indx_end]

        # If create_expt_name set to True, make custom modifications to expt_name.
        if create_expt_name:
            # Add the mesh name (label) to the start of the experiment name.
            mesh_label = experiment_config["user"]["mesh_label"]
            expt_name = '.'.join([mesh_label, expt_name])
#            # Add the build type ("debug" or "optimized") as a suffix to the experiment
#            # name.
#            build_type = experiment_config["user"]["build_type"]
#            expt_name = '.'.join([expt_name, build_type])

    print(f"{expt_name = }")

    # Append the experiment name to expt_dir to get the final experiment
    # path.  Then resolve the path.
    expt_dir = expt_basedir / expt_name
    expt_dir = expt_dir.resolve()

    print(f'{expt_dir = }')

    # (Re)set experiment_dir in the config dictionary to the final path created
    # above.  experiment_dir should be removed in the default config dictionary
    # since it is not needed now that there are expt_basedir and expt_name
    # (which should be added to the default dictionary).
    experiment_config["user"]["experiment_dir"] = str(expt_dir)

    # If the experiment directory already exists, rename it by appending the
    # current date and time to its name.
    if expt_dir.exists():
        crnt_datetime = datetime.now()
        crnt_datetime_str = crnt_datetime.strftime("%Y%m%d_%H%M%S")
        expt_name_old = '.'.join([expt_name, crnt_datetime_str])
        expt_dir_renamed = expt_dir / '..'/ expt_name_old
        expt_dir_renamed = expt_dir_renamed.resolve()
        msg = dedent(f"""
            The experiment directory (expt_dir) already exists:
                {expt_dir = }
            Moving (renaming) existing directory to:
                {expt_dir_renamed = }
            """)
        logging.info(msg)
        expt_dir.rename(expt_dir_renamed)

    # Create the experiment directory.
    print("Experiment will be set up here: {}".format(expt_dir))
    os.makedirs(expt_dir, exist_ok=True)

    # Get configuration parameters associated with launching the workflow.
    wflow_launch_config = experiment_config["wflow_launch"]
    wflow_launch_script_fn = wflow_launch_config["launch_script_fn"]
    wflow_launch_wrapper_fn = wflow_launch_config["launch_wrapper_fn"]

    # Copy the workflow launch script and wrapper script that runs it from
    # the MPAS App clone into the experiment directory.    
    wflow_launch_script_fp = mpas_app / 'ush' / wflow_launch_script_fn
    copy(wflow_launch_script_fp, expt_dir / wflow_launch_script_fn)
    wflow_launch_wrapper_fp = mpas_app / 'ush' / wflow_launch_wrapper_fn
    copy(wflow_launch_wrapper_fp, expt_dir / wflow_launch_wrapper_fn)
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
            f"""cd {expt_dir} && """
            f"""./{wflow_launch_wrapper_fn} >> ./{wflow_launch_log_fn} 2>&1"""
        )

        experiment_config["cron"]["crontab_line"] = crontab_line

        print(f'')
        print(f"Will include the following cron job in the user's cron table:")
        print(f'{crontab_line = }')

        add_crontab_line(called_from_cron=False, machine=platform,
                         crontab_line=crontab_line,
                         exptdir=expt_dir, debug=False)

    # Load the workflow definition
    workflow_blocks = experiment_config["user"]["workflow_blocks"]
    workflow_blocks = [mpas_app / "parm" / "wflow" / b for b in workflow_blocks]

    # Create a new dictionary, workflow_config, containing the settings in
    # the yaml config files listed under the workflow_blocks key in the
    # experiment_config dictionary.
    workflow_config = None
    for workflow_block in workflow_blocks:
        if workflow_config is None:
            workflow_config = uwconfig.get_yaml_config(workflow_block)
        else:
            workflow_config.update_values(uwconfig.get_yaml_config(workflow_block))
    # Update the values in workflow_config with the values in the YAMLConfig 
    # object experiment_config set above.
    workflow_config.update_values(experiment_config)

    experiment_file = expt_dir / Path("experiment.yaml")

    # Create the yaml file containing the complete experiment configuration.
    # Note that realize() performs jinja2 rendering.
    uwconfig.realize(
        input_config=workflow_config,
        output_file=experiment_file,
        update_config={},
    )

    # Post-process experiment.yaml to fix types that Jinja2 rendering produced
    # as strings (e.g. 'True'/'False' instead of YAML booleans, '!remove'
    # instead of key deletion).
    with open(experiment_file) as f:
        expt_data = yaml.safe_load(f)
    _fix_types(expt_data)
    with open(experiment_file, 'w') as f:
        yaml.dump(expt_data, f, default_flow_style=False)

    # Create the workflow files
    rocoto_xml = expt_dir / Path("rocoto.xml")
    rocoto_valid = uwrocoto.realize(config=experiment_file, output_file=rocoto_xml)
    if not rocoto_valid:
        sys.exit(1)

    # Create grid file.
    mesh_conn_fn = f"{experiment_config['user']['mesh_label']}.graph.info"
    mesh_conn_fp = Path(experiment_config["data"]["mesh_files"]) / mesh_conn_fn

    # Reload experiment_config from the rendered experiment.yaml so that Jinja2
    # template strings referencing other config fields are resolved.  Note that
    # cycle-dependent templates (e.g. {{ cycle.strftime(...) }}) remain unresolved
    # since cycle is only known at Rocoto runtime.
    experiment_config = uwconfig.get_yaml_config(config=experiment_file)

    all_nprocs = []
    for sect, driver in (
        ("create_ics", "mpas_init"),
        ("create_lbcs", "mpas_init"),
        ("forecast", "mpas"),
        ):
        if sect in experiment_config and isinstance(experiment_config[sect], dict):
            resources = experiment_config[sect][driver]["execution"]["batchargs"]
            if (cores := resources.get("cores")) is None:
                cores = resources["nodes"] * resources["tasks_per_node"]
            all_nprocs.append(cores)
    for nprocs in all_nprocs:
        dummy_or_null = 'dummy ' if nprocs == 1 else ''
        if not (expt_dir / f"{mesh_conn_fp.name}.part.{nprocs}").is_file():
            print(f"Creating {dummy_or_null}grid partitioning file for nprocs = {nprocs} MPI processes...")
            if nprocs == 1:
                print(f"Note: When nprocs = {nprocs} (i.e. MPAS is running in serial), MPAS does not read in a grid partitioning file.")
                print(f"      However, for consistency with the nprocs > 1 case, an empty grid partitioning file will still be created.")
            create_grid_files(expt_dir, mesh_conn_fp, nprocs)


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
