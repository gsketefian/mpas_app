#!/bin/bash -l
# Note:
# The -l above is needed to make the shell a login shell, which is needed
# for the "module" and "conda" commands to be found.

set -u
set -e

scrfunc_fp=$( readlink -f "${BASH_SOURCE[0]}" )
scrfunc_dir=$( dirname "${scrfunc_fp}" )
expt_dir=${scrfunc_dir}

platform=$(sed -n -r 's/^[ ]*PLATFORM:[ ]*(.*)$/\1/p' experiment.yaml)
mpas_app_dir=$(sed -n -r 's/^[ ]*MPAS_APP:[ ]*([^&]*)$/\1/p' experiment.yaml)
#platform="$1"
#mpas_app_dir="$2"

echo
#echo "AAAAAAAAAAAAAAAAAAAA"
echo "platform = |${platform}|"
echo "mpas_app_dir = |${mpas_app_dir}|"
#ijijijijiji
#echo
#echo "BBBBBBBBBBBBBBBBBBBB"
#module list

module use ${mpas_app_dir}/modulefiles
cwd=$(pwd)
cd ${mpas_app_dir}/modulefiles
module load wflow_${platform}.lua > /dev/null 2>&1
cd $cwd

#echo
#echo "CCCCCCCCCCCCCCCCCCCC"
#module list

conda activate mpas_app

python ./launch_wflow.py
