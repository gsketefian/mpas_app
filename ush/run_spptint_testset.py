import os
import shutil
import experiment_gen
import uwtools.api.config as uwconfig

def run_spptint_testset(mesh_label, lscale_1, dosppt_vals, spptint_vals, num_runs):
    """
    Put some comments here.
    """
#
# Launch a new mpas_app experiment for each value of spptint and run number.
#
# For the case of spptint >= 0, the steps to run an mpas_app experiment 
# for the current value of spptint and run number are as follows:
#
# 1) Create a base name for the current experiment, i.e. one that includes
#    the current value of spptint.  There should be a yaml configuration
#    file in the directory of this script corresponding to this basename.
#
# 2) Create a name for the current experiment that includes the run number.
#    This is just the base experiment name with a suffix containing the
#    run number.  This is just a way to have different experiments with
#    the same spptint value and other configuration parameters.
#
# 3) Copy the yaml config file with the base experiment name to a new file
#    with the actual experiment name and use that as the configuration file
#    (in addition to a base configuration file for the conus_15km grid).  
#    This new file is a temporary one that is needed so that mpas_app names
#    the experiment directory correctly (i.e. so that it includes the run
#    number in the experiment name.  This new config file will be deleted
#    once the experiment is launched.
#
# 4) Call the script that launches an mpas_app experiment, passing to it
#    the names of the base configuration file for the conus_15km grid and
#    the (temporary) configuration file for the current value of spptint
#    and run number.
#
# 5) Delete the temporary configuration file.
#
# For the case of spptint = -1, we want to disable SPPT completely in MPAS.
# This implies that we do not need to pass a second configuraton file
# (that enables SPPT and specifies its parameters) to the script that
# launches an mpas_app experiment because the base config file for the 
# conus_15km grid already has SPPT disabled.
# 

    # Set names of configuration files that will be needed.
    base_cfg_fn = ''.join(['config.', mesh_label, '.forecast_only.yaml'])
    stochy_nml_defaults_fn = 'config.modify_nml.nam_stochy.sppt_with_defaults.yaml'
    custom_cfg_tmpl_fn = 'config.template.sppt_pat1_only.yaml'

    # Get the number of cores and the time step from the mpas_app base config
    # file for this mesh so they can be included in the name of one of the
    # subdirectories in each experiment's base directory.  This requires reading
    # in the base config file.
    base_cfg = uwconfig.get_yaml_config(base_cfg_fn)
    num_cores = base_cfg['forecast']['mpas']['execution']['batchargs']['cores']
    dt = base_cfg['forecast']['mpas']['namelist']['update_values']['nhyd_model']['config_dt']

    num_repeat_chars = 56
    print(f'')
    print(f'*' * num_repeat_chars)
    print(f'{mesh_label = }')
    print(f'{num_cores = }')
    print(f'{dt = } sec')

    # Convert lscale_1 to meters and then to a string with the appropriate
    # format to use in forming a file or directory name.
    lscale1_km_int = int(lscale_1/1000)
    lscale1_km_str = f'l1_{lscale1_km_int:04d}km'

    # Create a string for the time step that is appropriate to use in 
    # forming a file or directory name.
    dt_sec_str = f'dt_{dt:05.1f}s'.replace('.', 'p')

    # Read in the template custom configuration file.
    custom_cfg_tmpl = uwconfig.get_yaml_config(custom_cfg_tmpl_fn)

    for dosppt, spptint in zip(dosppt_vals, spptint_vals):
        print(f'')
        print(f'=' * num_repeat_chars)
        print(f'{dosppt = }')
        print(f'{spptint = } sec')
        print(f'{lscale_1 = } km')

        for nrun in range(1,num_runs+1):
            print(f'')
            print('  ' + f'-' * num_repeat_chars)
            print(f'{  nrun = }')

            # Copy the template custom config dictionary and modify it as needed.
            custom_cfg = custom_cfg_tmpl

            # In the custom configuration dictionary, modify the experiment base
            # name so that it is a relative path with a subdirectory that includes
            # the mesh name, lscale_1, and the number of cores used for the forecast.
            custom_cfg['user']['expt_basedir'] \
                 = os.path.join('sppt_timing_tests',
                                '_'.join([mesh_label, dt_sec_str, lscale1_km_str, 'ncores', f'{num_cores:04d}']))
   
            # In the custom configuration dictionary, set do_sppt, spptint, and
            # lscale_1 that are needed in the MPAS namelist.
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['do_sppt'] = dosppt
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['config_spptint'] = spptint
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['config_sppt_lscale_1'] = lscale_1

            if dosppt:
                expt_basename = ''.join(['sppt_pat1_only_l1_', lscale1_km_str, '_spptint_', f'{spptint:04d}', 'sec'])
            else:
                expt_basename = ''.join(['no_sppt'])

            expt_name = ''.join([expt_basename, f'_run{nrun:02d}'])
            custom_cfg_fn = ''.join(['config.', expt_name, '.yaml'])

            print(f'{    expt_basename = }')
            print(f'{    expt_name = }')
            print(f'{    custom_cfg_fn = }')
#            print(f'    custom_cfg =\n{custom_cfg}')

            # Create the yaml file containing the sppt customizations in the namelist.
            # This is a temporary file that will be deleted once the experiment is
            # launched.
            # Note that realize() performs jinja2 rendering where it can.
            uwconfig.realize(
                input_config=custom_cfg,
                output_file=custom_cfg_fn,
                update_config={},
            )

            # Call the script that launches an mpas_app experiment using the arguments
            # list created above.
            args_list = [base_cfg_fn, stochy_nml_defaults_fn, custom_cfg_fn]
            print(f'{    args_list = }')
            experiment_gen.main(args_list)

            # Delete the temporary mpas_app configuration file.
            if custom_cfg_fn and os.path.isfile(custom_cfg_fn):
                print(f'    Removing temporary configuration file: {custom_cfg_fn} ...')
                os.remove(custom_cfg_fn)

        print(f'')
        print('  ' + f'-' * num_repeat_chars)
        print(f'')
        print(f'=' * num_repeat_chars)

    print(f'')
    print(f'Done.')
    print(f'*' * num_repeat_chars)
    print(f'')


if __name__ == "__main__":

    # Set the name of the mesh on which to run MPAS.
    mesh_label = 'conus_15km'
#    mesh_label = 'conus_03km'

    # Set the value of the scale parameter for the first SPPT pattern.
    # This is in meters.
    lscale_1 = 50000
#    lscale_1 = 150000

    # Set the spptint values for which to run the MPAS model.  A value of
    # -1 means SPPT is turned off completely (so that the value of spptint
    # is irrelevant).
    spptint_vals = [-1, 0, 60, 120, 600, 7200]
#    spptint_vals = [-2]
    spptint_vals = [-1, 60]

    # Set number of identical runs to make for each value of spptint.  This is
    # to get a statistically significant sample.
    num_runs = 10
    num_runs = 1
    num_runs = 2

#    spptint_vals = [60]
#    spptint_vals = [-1]

    dosppt_vals = [spptint >= 0 for spptint in spptint_vals]
    run_spptint_testset(mesh_label, lscale_1, dosppt_vals, spptint_vals, num_runs)

