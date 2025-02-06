#!/bin/bash -l
# Note:
# The -l above is needed to make the shell a login shell, which is needed
# for the "module" command to work.

set -u
set -e

scrfunc_fp=$( readlink -f "${BASH_SOURCE[0]}" )
scrfunc_dir=$( dirname "${scrfunc_fp}" )

experiment_config_fn="experiment.yaml"
echo
echo "========================================================================="
echo
echo "Retrieving experiment information from configuration file \"${experiment_config_fn}\"..." 

platform=$(sed -n -r 's/^[ ]*PLATFORM:[ ]*(.*)$/\1/p' ${experiment_config_fn})
mpas_app_dir=$(sed -n -r 's/^[ ]*MPAS_APP:[ ]*([^&]*)$/\1/p' ${experiment_config_fn})
expt_dir=${scrfunc_dir}
wflow_launch_script_fn=$(sed -n -r 's/^[ ]*launch_script_fn:[ ]*([^&]*)$/\1/p' ${experiment_config_fn})
 
echo
echo "platform = \"${platform}\""
echo "mpas_app_dir = \"${mpas_app_dir}\""
echo "expt_dir = \"${expt_dir}\""
echo "wflow_launch_script_fn = \"${wflow_launch_script_fn}\""

echo
echo "Loading modules and conda environment..."

module use ${mpas_app_dir}/modulefiles
cwd=$(pwd)
cd ${mpas_app_dir}/modulefiles
module load wflow_${platform}.lua > /dev/null 2>&1
cd $cwd
conda activate mpas_app

echo
echo "Calling workflow launch script \"${wflow_launch_script_fn}\"..."
python ./${wflow_launch_script_fn}
