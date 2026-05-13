import os
import shutil
import experiment_gen
import uwtools.api.config as uwconfig

def run_spptint_testset(mpas_config, spptint_vals, num_runs):
    """
    This function launches a new mpas_app experiment for each value of spptint
    and run number.
    """

    # Put values from the MPAS configuration dictionary into individual variables.
    mesh_label = mpas_config['mesh_label']
    dt = mpas_config['dt']
    fcst_len = mpas_config['fcst_len']
    num_cores = mpas_config['num_cores']
    lscale_1 = mpas_config['lscale_1']

    # The MPAS namelist flag do_sppt should be set to .true. for all
    # non-negative values of spptint.  Create a list containing this
    # flag for each value of spptint.
    dosppt_vals = [spptint >= 0 for spptint in spptint_vals]

    # Set names of configuration files that will be needed.
    base_cfg_fn = ''.join(['config.', mesh_label, '.forecast_only.yaml'])
    stochy_nml_defaults_fn = 'config.modify_nml.nam_stochy.sppt_with_defaults.yaml'
    custom_cfg_tmpl_fn = 'config.template.sppt_pat1_only.yaml'

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
   
            # Set various values in the custom configuration dictionary.
            custom_cfg['forecast']['mpas']['length'] = fcst_len 
            custom_cfg['forecast']['mpas']['execution']['batchargs']['cores'] = num_cores
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nhyd_model']['config_dt'] = dt
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['do_sppt'] = dosppt
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['config_spptint'] = spptint
            custom_cfg['forecast']['mpas']['namelist']['update_values']['nam_stochy']['config_sppt_lscale_1'] = lscale_1

            if dosppt:
                expt_basename = ''.join(['sppt_pat1_only_', lscale1_km_str, '_spptint_', f'{spptint:04d}', 'sec'])
            else:
                expt_basename = ''.join(['no_sppt'])

            expt_name = ''.join([expt_basename, f'_run{nrun:02d}'])
            custom_cfg_fn = ''.join(['config.', expt_name, '.yaml'])

            print(f'{    expt_basename = }')
            print(f'{    expt_name = }')
            print(f'{    custom_cfg_fn = }')
#            print(f'    custom_cfg =\n{custom_cfg}')

            # Create the yaml file containing the values in the custom configuration
            # dictionary above.  This is a temporary file that will be deleted once
            # the experiment is launched.
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

    # MPAS basic model configuration for the CONUS 120km mesh.
    mpas_config_conus120km \
        = {'mesh_label': 'conus_120km',
           'dt': 720.0,
           'fcst_len': 6,
           'num_cores': 1,
           #'num_cores': 2,
           #'num_cores': 32,
           'lscale_1': 450000,
          }

    # MPAS basic model configuration for the CONUS 15km mesh.
    mpas_config_conus15km \
        = {'mesh_label': 'conus_15km',
           'dt': 60.0,
           'fcst_len': 6,
           'num_cores': 80,
#           'lscale_1': 50000,
           'lscale_1': 150000,
          }

    # MPAS basic model configuration for the CONUS 3km mesh.
    mpas_config_conus03km \
        = {'mesh_label': 'conus_03km',
           'dt': 15.0,
           'fcst_len': 6,
           'num_cores': 2400,
           'lscale_1': 150000,
          }

    mpas_config = mpas_config_conus120km
#    mpas_config = mpas_config_conus15km
#    mpas_config = mpas_config_conus03km

    # Set the spptint values for which to run the MPAS model.  A negative
    # value of spptint means SPPT is turned off completely (so that the
    # value of spptint is irrelevant).
#    spptint_vals = [-1, 0, 60, 120, 600, 7200]
#    spptint_vals = [-1, 0, 120, 600, 7200]
#    spptint_vals = [-1, 60]
#    spptint_vals = [60]
    spptint_vals = [0]
#    spptint_vals = [-1]

    # Set number of identical runs to make for each value of spptint.  This is
    # to get a statistically significant sample.
    num_runs = 10
    num_runs = 1
#    num_runs = 2

    # Run the specified MPAS configuration for the given spptint values and number of runs.
    run_spptint_testset(mpas_config, spptint_vals, num_runs)

