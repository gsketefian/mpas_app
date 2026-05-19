#!/bin/bash -eu

if [[ ${ICS_or_LBCS} == "ICS" ]] ; then
  fcst_hours=$TIME_OFFSET_HRS
  if [[ ${TIME_OFFSET_HRS} -eq 0 ]] ; then
    file_set=anl
  fi
else
  first_time=$((TIME_OFFSET_HRS + LBC_INTVL_HRS))
  last_time=$((TIME_OFFSET_HRS + FCST_LEN))
  fcst_hours="${first_time} ${last_time} ${LBC_INTVL_HRS}"
fi

# In order to avoid a possible race condition between the get_ics_data
# and get_lbcs_data tasks in the mpas_app workflow (e.g. both these tasks
# trying to remove the same temporary directory during the cleanup stage),
# first create a task-specific work directory (i.e. a work directory whose
# name depends on whether ICs or LBCs are being retrieved) and then change
# location to it before calling the python script.
# 
work_dir=${OUTPUT_PATH}.work_${ICS_or_LBCS}
mkdir -p ${work_dir}
cd ${work_dir}

set -x
python -u ${MPAS_APP}/ush/retrieve_data.py \
    --debug \
    --file_set ${file_set:-fcst} \
    --config ${MPAS_APP}/parm/data_locations.yml \
    --cycle_date ${YYYYMMDDHH} \
    --data_stores ${DATA_STORES} \
    --data_type ${EXTERNAL_MODEL} \
    --fcst_hrs $fcst_hours \
    --file_fmt grib2 \
    --ics_or_lbcs ${ICS_or_LBCS} \
    --output_path ${OUTPUT_PATH}

# Remove work directory.
cd ${OUTPUT_PATH}
rmdir ${work_dir}

