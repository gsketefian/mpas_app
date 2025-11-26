#!/bin/bash

#usage instructions
usage () {
cat << EOF_USAGE
Usage: $0 --platform=PLATFORM [OPTIONS] 

OPTIONS
  -h, --help
      show this help guide
  -p, --platform=PLATFORM
      name of machine you are building on
      (e.g. hera | jet | hercules)
  -c, --compiler=COMPILER
      compiler to use; default depends on platform
      (e.g. intel | gnu | cray | gccgfortran)
  --continue
      continue with existing build
  --pre-clean
      does a "make clean" before building each core
  --post-clean
      does a "make clean" after building each core
  --clean
      does a "make clean"
  --exec-dir=EXEC_DIR
      installation binary directory name ("exec" by default; any name is available)
  --conda-dir=CONDA_DIR
      installation location for miniconda (SRW clone conda subdirectory by default)
  --conda-only
      install conda only without building MPAS
  --build-jobs=BUILD_JOBS
      number of build jobs; defaults to 4
  -v, --verbose
      build with verbose output
  --atmos-only
      build the MPAS atmosphere core only, this option assumes you have already built the init_atmosphere_model to create the necessary initial conditions and executables.
  --no-mp-tables
      do not generate micrphysics tables
  --debug
      build MPAS with debug mode
  --use-papi
      builds version of MPAS using PAPI for timers
  --tau
      builds version of MPAS using TAU hooks for profiling
  --autoclean
      forces a clean of MPAS infrastructure prior to build new core
  --gen-f90
      generates intermediate .f90 files through CPP, and builds with them
  --timer-lib=TIMER_LIB
      selects the timer library interface to be used for profiling the model, options are native, gptl, and tau
  --openmp
      builds and links with OpenMP flags
  --single-precision
      builds with default single-precision real kind.  Default is to use double-precision
EOF_USAGE
}

install_miniforge () {

  set -x
  os=$(uname)
  test $os == Darwin && os=MacOSX
  hardware=$(uname -m)
  installer=Miniforge3-${os}-${hardware}.sh
  curl -L -O "https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/${installer}"
  bash ./${installer} -bfp "${CONDA_BUILD_DIR}"
  rm ${installer}
}

install_conda_envs () {

  source ${CONDA_BUILD_DIR}/etc/profile.d/conda.sh
  conda activate
  if ! conda env list | grep -q "^mpas_app\s" ; then
    mamba env create -n mpas_app --file environment.yml
  fi
  APPLICATION=$(echo ${APPLICATION} | tr '[a-z]' '[A-Z]')
  if ! conda env list | grep -q "^ungrib\s" ; then
    mamba create -y -n ungrib -c maddenp ungrib
  fi
}

function check_generate_microphys_files() {
  # This function checks for the existence of the MP files (tables) for the
  # given microphysics (MP) scheme and generates them if necessary.
  local mp_name="${1}"
  local mp_tables=("${@:2}")

  echo
  echo "The following files are needed by the ${mp_name} microphysics (MP) scheme"
  echo "and must exist in the current directory if MPAS is to be run with this"
  echo "scheme:"
  printf "    %s\n" "${mp_tables[@]}"
  echo "Checking for the existence of these files in the current directory."
  echo "Current directory is:"
  echo "    $(pwd)"

  local all_files_exist=true
  local f=""
  echo
  for f in "${mp_tables[@]}"; do
    if [ "${VERBOSE}" = true ] ; then
      echo "Checking for existence of file \"${f}\" in directory:"
      echo "    $(pwd)"
    fi
    if [[ ! -f "${f}" ]]; then
      if [ "${VERBOSE}" = true ] ; then
        echo "File \"${f}\" does not exist.  Setting \"all_files_exist\" to \"false\"."
      fi
      all_files_exist=false
      break
    fi
  done

  if "${all_files_exist}"; then
    echo "All ${mp_name} MP files already exist in the current directory."
    echo "No need to generate ${mp_name} MP files (tables)."
  else
    #
    # Note that the build_tables or build_tables_tempo command called below
    # places the files it creates in the top-level directory of the MPAS-Model
    # clone.  It will fail if these files already exist (or if symlinks with
    # the same names already exist).  That is why we must first delete any
    # such existing files/symlinks before attempting to (re)generate them.
    #
    echo "At least some of the ${mp_name} MP files do not exist in the current directory."
    echo "Deleting any existing ${mp_name} MP files (tables) and generating new ones to"
    echo "obtain an updated and complete set..."
    rm -f "${mp_tables[@]}"

    local exec_name=""
    if [ ${mp_name,,} == "thompson" ]; then
      exec_name="build_tables"
    elif [ ${mp_name,,} == "tempo" ]; then
      exec_name="build_tables_tempo"
    fi
    ./${exec_name}
  fi

}

install_mpas_init () {

  echo "Building executable 'init_atmosphere_model' (CORE='init_atmosphere')..."
  pushd ${MPAS_APP_DIR}/src/MPAS-Model
  if [ "${PRECLEAN}" = true ]; then
    echo "Pre-cleaning 'atmosphere' core..."
#
# Note that the "clean" target of the Makefile in the directory
# 
#   MPAS-Model/src/core_atmosphere
#
# will remove all files and symlinks in the top-level directory (MPAS-Model)
# that end with TBL and/or that contain the string "DATA" since the recipe
# for the "clean" target contains the lines
#
#   ( cd ../..; rm -f *TBL )
#   ( cd ../..; rm -f *DATA* )
#
# This of course includes the MP_THOMPSON_*_DATA.DBL files for Thompson
# microphysics.
#
    make clean CORE=atmosphere
    echo "Pre-cleaning 'init_atmosphere' core..."
    make clean CORE=init_atmosphere
  fi
  make intel-mpi CORE=init_atmosphere ${MPAS_MAKE_OPTIONS} && \
  echo "Finished building executable 'init_atmosphere_model' (CORE='init_atmosphere')."
  cp -v init_atmosphere_model ${EXEC_DIR}
#  make clean CORE=init_atmosphere
  popd
}

install_mpas_model () {

  echo "Building executable 'atmosphere_model' (CORE='atmosphere')..."
  pushd ${MPAS_APP_DIR}/src/MPAS-Model
  if [ "${PRECLEAN}" = true ]; then
    echo "Pre-cleaning 'atmosphere' core..."
#
# Note that the "clean" target of the Makefile in the directory
# 
#   src/core_atmosphere
#
# will remove all files and symlinks in the top-level directory (usually
# named "MPAS-Model") that end with TBL and/or that contain the string
# "DATA" because the recipe for the "clean" target contains the lines
#
#   ( cd ../..; rm -f *TBL )
#   ( cd ../..; rm -f *DATA* )
#
# This of course includes the MP_THOMPSON_*_DATA.DBL files for Thompson
# microphysics.  New symlinks in the top-level directory to *TBL files
# in the directories
#
#   src/core_atmosphere/physics/physics_wrf/files
#
# and
#
#   core_atmosphere/physics/physics_noahmp/parameters
#
# and to *DATA* files in the directory
#
#   src/core_atmosphere/physics/physics_wrf/files
#
# are created later during the build of the model below (e.g. when make
# is called below with target "intel-mpi" and CORE=atmosphere).
#
# Note that the "clean" target in src/core_atmosphere/Makefile does NOT
# remove the "files" directory that the make command below creates and
# populates with files.  Strictly speaking it should, but it doesn't
# matter since that directory and its contents get overwritten by the
# make below.
#
    make clean CORE=atmosphere
  fi
#
# The following "make" command will create the directory
#
#   src/core_atmosphere/physics/physics_wrf/files
#
# and will populate it with various tables (text files) and other data
# to be used by the physics schemes, but it will NOT create the tables
# for Thompson or TEMPO microphysics.  That is done by the build_tables
# (for Thompson) or build_tables_tempo (for TEMPO) command below.
#
# It will also create symlinks in the top-level MPAS-Model directory to
# the physics tables and related files in subdirectories.  This is done
# by the recipe for the physcore target in the Makefile in the directory
#
#   src/core_atmosphere
#
# That recipe includes these lines:
#
#   ( cd ../..; ln -sf ./src/core_atmosphere/physics/physics_wrf/files/*TBL .)
#   ( cd ../..; ln -sf ./src/core_atmosphere/physics/physics_wrf/files/*DATA* .)
#   ( cd ../..; ln -sf ./src/core_atmosphere/physics/physics_noahmp/parameters/*TBL .)
#
# Note that these will not create symlinks to Thompson or TEMPO microphysics
# tables/files because the latter will not yet exist if a pre-clean has been
# performed (and the "*"s in the ln commands above will only create symlinks
# to *TBL and *DATA* files that already exist in the directories).
#
  make intel-mpi CORE=atmosphere ${MPAS_MAKE_OPTIONS}
  cp -v atmosphere_model ${EXEC_DIR}
#
# Generate microphysics tables.
#
  if [ "${GENERATE_MP_TABLES}" = true ] ; then
#
# Set the names of the files needed for Thompson and TEMPO micorphysics (MP).
# Then generate these files if they don't already exist.
#
    thompson_mp_tables=( "MP_THOMPSON_QIautQS_DATA.DBL"
                         "MP_THOMPSON_QRacrQG_DATA.DBL"
                         "MP_THOMPSON_QRacrQS_DATA.DBL"
                         "MP_THOMPSON_freezeH2O_DATA.DBL" )

    tempo_mp_tables=( "MP_TEMPO_HAILAWARE_QRacrQG_DATA.DBL"
                      "MP_TEMPO_QIautQS_DATA.DBL"
                      "MP_TEMPO_QRacrQS_DATA.DBL"
                      "MP_TEMPO_freezeH2O_DATA.DBL" )

    if [ "${PRECLEAN}" = true ]; then
      echo
      echo "Since \"PRECLEAN\" is set to \"true\", will remove any existing microphysics tables..."
      rm -f "${thompson_mp_tables[@]}"
      rm -f "${tempo_mp_tables[@]}"
      echo "Done removing any existing microphysics tables."
    fi

    check_generate_microphys_files "Thompson" ${thompson_mp_tables[@]}

    check_generate_microphys_files "TEMPO" ${tempo_mp_tables[@]}
  fi

  popd
  echo "Finished building executable 'atmosphere_model' (CORE='atmosphere')."
}

# print settings
settings () {
cat << EOF_SETTINGS
Settings:

  MPAS_APP_DIR=${MPAS_APP_DIR}
  EXEC_DIR=${EXEC_DIR}
  PLATFORM=${PLATFORM}
  COMPILER=${COMPILER}
  CONTINUE=${CONTINUE}
  BUILD_JOBS=${BUILD_JOBS}
  VERBOSE=${VERBOSE}
  
EOF_SETTINGS
}

# print usage error and exit
usage_error () {
  printf "ERROR: $1\n" >&2
  usage >&2
  exit 1
}

# default settings
LCL_PID=$$
CONDA_BUILD_DIR="./conda"
COMPILER=""
BUILD_JOBS=1
CONTINUE=false
VERBOSE=false
ATMOS_ONLY=false
DEBUG=false
USE_PAPI=false
TAU=false
AUTOCLEAN=false
GEN_F90=false
OPENMP=false
SINGLE_PRECISION=false
GENERATE_MP_TABLES=true

# Make options
CLEAN=false
PRECLEAN=false
CONDA_ONLY=false
INSTALL_CONDA=true

# process required arguments
if [[ ("$1" == "--help") || ("$1" == "-h") ]]; then
  usage
  exit 0
fi

# process optional arguments
while :; do
  case $1 in
    --help|-h) usage; exit 0 ;;
    --platform=?*|-p=?*) PLATFORM=${1#*=} ;;
    --platform|--platform=|-p|-p=) usage_error "$1 requires argument." ;;
    --compiler=?*|-c=?*) COMPILER=${1#*=} ;;
    --compiler|--compiler=|-c|-c=) usage_error "$1 requires argument." ;;
    --continue) CONTINUE=true ;;
    --continue=?*|--continue=) usage_error "$1 argument ignored." ;;
    --clean) CLEAN=true ;;
    --pre-clean) PRECLEAN=true ;;
    --build) BUILD=true ;;
    --exec-dir=?*) EXEC_DIR=${1#*=} ;;
    --exec-dir|--exec-dir=) usage_error "$1 requires argument." ;;
    --conda-dir=?*) CONDA_BUILD_DIR=${1#*=} ;;
    --conda-dir|--conda-dir=) usage_error "$1 requires argument." ;;
    --conda-only) CONDA_ONLY=true ;;
    --no-conda) INSTALL_CONDA=false ;;
    --build-jobs=?*) BUILD_JOBS=$((${1#*=})) ;;
    --build-jobs|--build-jobs=) usage_error "$1 requires argument." ;;
    --verbose|-v) VERBOSE=true ;;
    --verbose=?*|--verbose=) usage_error "$1 argument ignored." ;;
    --atmos-only ) ATMOS_ONLY=true ;;
    --no-mp-tables) GENERATE_MP_TABLES=false ;;
    --debug) DEBUG=true ;;
    --use-papi) USE_PAPI=true ;;
    --tau ) TAU=true ;;
    --autoclean ) AUTOCLEAN=true ;;
    --gen-f90 ) GEN_F90=true ;;
    --timer-lib=?*) TIMER_LIB=${1#*=} ;;
    --timer-lib| --timer-lib= ) usage_error "$1 requires argument." ;;
    --openmp ) OPENMP=true ;;
    --single-precision ) SINGLE_PRECISION=true ;;
   # unknown
    -?*|?*) usage_error "Unknown option $1" ;;
    *) break
  esac
  shift
done

# Ensure uppercase / lowercase ============================================
PLATFORM=$(echo ${PLATFORM} | tr '[A-Z]' '[a-z]')
COMPILER=$(echo ${COMPILER} | tr '[A-Z]' '[a-z]')

# check if PLATFORM is set
if [ -z $PLATFORM ] ; then
  printf "\nERROR: Please set PLATFORM.\n\n"
  usage
  exit 0
fi
# set PLATFORM (MACHINE)
MACHINE="${PLATFORM}"
printf "PLATFORM(MACHINE)=${PLATFORM}\n" >&2

MPAS_APP_DIR=$(cd "$(dirname "$(readlink -f -n "${BASH_SOURCE[0]}" )" )" && pwd -P)

# The installation process for conda cannot handle absolute paths to the
# mpas_app root directory that contain more than the maximimum number of
# characters specified below (MPAS_APP_DIR_MAX_LEN).  It's not clear where
# this restriction comes from (possibly in mamba).  Check for this.
MPAS_APP_DIR_MAX_LEN=108
if [ ${#MPAS_APP_DIR} -gt ${MPAS_APP_DIR_MAX_LEN} ]; then
  echo
  echo "The number of characters in the absolute path to the mpas_app root"
  echo "directory (MPAS_APP_DIR) cannot be more than ${MPAS_APP_DIR_MAX_LEN} (but is):"
  echo "  MPAS_APP_DIR = \"${MPAS_APP_DIR}\"" 
  echo "  \${#MPAS_APP_DIR} = ${#MPAS_APP_DIR}" 
  echo "Please clone mpas_app in a location with an absolue path that is within"
  echo "this limit and retry the build.  Stopping."
  exit
fi

if [ "${INSTALL_CONDA}" = true ]; then

  if [ ! -d "${CONDA_BUILD_DIR}" ]; then
    install_miniforge
    install_conda_envs

    CONDA_BUILD_DIR="$(readlink -f "${CONDA_BUILD_DIR}")"
#    echo ${CONDA_BUILD_DIR} > ${MPAS_APP_DIR}/conda_loc
    echo ${CONDA_BUILD_DIR} > ./conda_loc

    echo
    echo "Done with conda installation."
  else
    echo
    echo "Conda build directory already exists:"
    echo "  CONDA_BUILD_DIR = \"${CONDA_BUILD_DIR}\""
    echo "  current directory: \"$(pwd)\""
    echo "Please rename or remove before attempting a new conda build."
    echo "Stopping."
    exit
  fi

else
  echo
  echo "Not installing conda because \"INSTALL_CONDA\" is not set to \"true\":"
  echo "  INSTALL_CONDA = \"${INSTALL_CONDA}\""
fi

# Conda environment should have linux utilities to perform these tasks on macos.
MPAS_APP_DIR=$(cd "$(dirname "$(readlink -f -n "${BASH_SOURCE[0]}" )" )" && pwd -P)
EXEC_DIR=${EXEC_DIR:-${MPAS_APP_DIR}/exec}

# Stop if --conda-only was specified on the command line.
if [ "${CONDA_ONLY}" = true ]; then
  echo
  echo "Since \"CONDA_ONLY\" is set to \"${CONDA_ONLY}\", will not build MPAS-Model."
  echo "Exiting."
  exit
fi

if [ -z "${COMPILER}" ] ; then
  case ${PLATFORM} in
    jet|hera|hercules) COMPILER=intel ;;
    *)
    COMPILER=intel
    printf "WARNING: Setting default COMPILER=intel for new platform ${PLATFORM}\n" >&2;
    ;;
  esac
fi

printf "COMPILER=${COMPILER}\n" >&2

# print settings
if [ "${VERBOSE}" = true ] ; then
  settings
fi

# set MODULE_FILE for this platform/compiler combination
MODULE_FILE="build_${PLATFORM}_${COMPILER}"
if [ ! -f "${MPAS_APP_DIR}/modulefiles/${MODULE_FILE}.lua" ]; then
  printf "ERROR: module file does not exist for platform/compiler\n" >&2
  printf "  MODULE_FILE=${MODULE_FILE}\n" >&2
  printf "  PLATFORM=${PLATFORM}\n" >&2
  printf "  COMPILER=${COMPILER}\n\n" >&2
  printf "Please make sure PLATFORM and COMPILER are set correctly\n" >&2
  usage >&2
  exit 64
fi

printf "MODULE_FILE=${MODULE_FILE}\n" >&2

echo "BUILD_JOBS = ${BUILD_JOBS}"
# make settings
MAKE_SETTINGS="-j ${BUILD_JOBS}"
if [ "${VERBOSE}" = true ]; then
  MAKE_SETTINGS="${MAKE_SETTINGS} VERBOSE=1"
fi
echo "MAKE_SETTINGS = ${MAKE_SETTINGS}"

# Before we go on load modules, we first need to activate Lmod for some systems
source ${MPAS_APP_DIR}/etc/lmod-setup.sh $MACHINE

# source the module file for this platform/compiler combination, then build the code
printf "... Load MODULE_FILE ...\n"
module use ${MPAS_APP_DIR}/modulefiles
module load ${MODULE_FILE}
module list

# build MPAS
printf "...Building MPAS-Model..."

# process MPAS flags
MPAS_MAKE_OPTIONS="${MAKE_SETTINGS}"

if [ "${DEBUG}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} DEBUG=true"
fi

if [ "${USE_PAPI}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} USE_PAPI=true"
fi

if [ "${TAU}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} TAU=true"
fi

if [ "${AUTOCLEAN}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} AUTOCLEAN=true"
fi

if [ "${GEN_F90}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} GEN_F90=true"
fi

if [ ! -z "${TIMER_LIB}" ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} TIMER_LIB={$TIMER_LIB}"
fi

if [ "${OPENMP}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} OPENMP=true"
fi

if [ "${SINGLE_PRECISION}" = true ]; then
  MPAS_MAKE_OPTIONS="${MPAS_MAKE_OPTIONS} PRECISION=single"
fi

echo "MPAS_MAKE_OPTIONS = ${MPAS_MAKE_OPTIONS}"

EXEC_DIR="${MPAS_APP_DIR}/exec"
if [ ! -d "$EXEC_DIR" ]; then
  mkdir "$EXEC_DIR"
fi

printf "\nATMOS_ONLY: ${ATMOS_ONLY}\n"

if [ ${ATMOS_ONLY} = false ]; then
  install_mpas_init
fi

install_mpas_model

if [ "${CLEAN}" = true ]; then
    if [ -f $PWD/Makefile ]; then
       printf "... Clean executables ...\n"
       make ${MAKE_SETTINGS} clean 2>&1 | tee log.make
    fi
fi


