import os
import shutil
import experiment_gen

def run_spptint_testset(num_runs, spptint_vals):
    """
    Some comments here.
    """

    for nrun in range(1,num_runs+1):
        print(f'')
        print(f'========================================================')
        print(f'{nrun = }')
        for spptint in spptint_vals:
            print(f'  --------------------------------------------------------')
            print(f'{  spptint = }')
            expt_basename = ''.join(['sppt_pat1_only_l1_50km_spptint_', f'{spptint:03d}', 'sec'])
            print(f'{    expt_basename = }')
            expt_name = ''.join([expt_basename, '_run', f'{nrun:02d}'])
            print(f'{    expt_name = }')
            src_fn = ''.join(['config.modify_nml.nam_stochy.', expt_basename, '.yaml'])
            print(f'{    src_fn = }')
            dst_fn = ''.join(['config.modify_nml.nam_stochy.', expt_name, '.yaml'])
            print(f'{    dst_fn = }')
            shutil.copy(src_fn, dst_fn)
#            experiment_gen.main(['config.conus_15km.forecast_only.yaml', dst_fn])
            os.remove(dst_fn)
        print(f'  --------------------------------------------------------')
        print(f'========================================================')


if __name__ == "__main__":

    num_runs = 10
    spptint_vals = [60, 120, 600]

    num_runs = 3
#    spptint_vals = [60]
#    spptint_vals = [120]
    spptint_vals = [600]

    run_spptint_testset(num_runs, spptint_vals)

