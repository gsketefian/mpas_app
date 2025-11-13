import os
import shutil
import experiment_gen

def run_spptint_testset(num_runs, spptint_vals):
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
    for spptint in spptint_vals:
        print(f'')
        print(f'========================================================')
        print(f'{spptint = }')

        if spptint <= -2:
            raise ValueError(f'spptint must be greater than or equal to -1: {spptint = }')

        for nrun in range(1,num_runs+1):
            print(f'')
            print(f'  --------------------------------------------------------')
            print(f'{  nrun = }')

            # Create a list of arguments to pass to the script that launches an mpas_app
            # experiment.
            nrun_str = ''.join(['_run', f'{nrun:02d}'])
            if spptint >= 0:
                expt_basename = ''.join(['sppt_pat1_only_l1_50km_spptint_', f'{spptint:04d}', 'sec'])
                expt_name = ''.join([expt_basename, nrun_str])
                src_fn = ''.join(['config.modify_nml.nam_stochy.', expt_basename, '.yaml'])
                dst_fn = ''.join(['config.modify_nml.nam_stochy.', expt_name, '.yaml'])
                print(f'{    expt_basename = }')
                print(f'{    expt_name = }')
                print(f'{    src_fn = }')
                print(f'{    dst_fn = }')
                print(f'    Copying "src_fn" to "dst_fn"...')
                shutil.copy(src_fn, dst_fn)
                args_list = ['config.conus_15km.forecast_only.yaml', dst_fn]
            elif spptint == -1:
                expt_basename = ''.join(['conus_15km.forecast_only'])
                expt_name = ''.join([expt_basename, nrun_str])
                src_fn = ''.join(['config.', expt_basename, '.yaml'])
                dst_fn = ''.join(['config.', expt_name, '.yaml'])
                print(f'{    expt_basename = }')
                print(f'{    expt_name = }')
                print(f'{    src_fn = }')
                print(f'{    dst_fn = }')
                print(f'    Copying "src_fn" to "dst_fn"...')
                shutil.copy(src_fn, dst_fn)
                args_list = [dst_fn]

            # Call the script that launches an mpas_app experiment using the arguments
            # list created above.
            print(f'{    args_list = }')
            experiment_gen.main(args_list)

            # Delete the temporary mpas_app configuration file.
            if dst_fn and os.path.isfile(dst_fn):
                print(f'    Removing "dst_fn"...')
                os.remove(dst_fn)

        print(f'  --------------------------------------------------------')
        print(f'========================================================')


if __name__ == "__main__":

    # Set the spptint values for which to run the MPAS model.  A value of
    # -1 means SPPT is turned off completely (so that the value of spptint
    # is irrelevant).
    spptint_vals = [-1, 0, 60, 120, 600, 7200]
    spptint_vals = [-2]
    spptint_vals = [-1, 60]

    # Set number of identical runs to make for each value of spptint.  This is
    # to get a statistically significant sample.
    num_runs = 10
    num_runs = 3

    spptint_vals = [60]

    run_spptint_testset(num_runs, spptint_vals)

