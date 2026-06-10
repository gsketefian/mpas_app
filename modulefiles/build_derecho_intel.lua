help([[
This module loads libraries for building the MPAS App on
the NCAR machine Derecho.
]])

whatis([===[Loads libraries needed for building the MPAS App on Derecho ]===])
prepend_path("MODULEPATH", '/glade/work/epicufsrt/contrib/spack-stack/derecho/spack-stack-1.9.3/envs/ue-oneapi-2024.2.1/install/modulefiles/Core')

load("stack-oneapi/2024.2.1")
load("stack-cray-mpich/8.1.29")
load("intel-oneapi-mkl/2024.2.2")
load("cmake/3.27.9")
load("parallel-netcdf/1.12.3")
load("parallelio/2.6.2")

if mode() == "load" then
  setenv("PNETCDF", os.getenv("parallel_netcdf_ROOT"))
  setenv("NETCDF", os.getenv("netcdf_c_ROOT"))
  setenv("NETCDFF", os.getenv("netcdf_fortran_ROOT"))
end
if mode() == "unload" then
  unsetenv("PNETCDF")
  unsetenv("NETCDF")
  unsetenv("NETCDFF")
end

setenv("CMAKE_C_COMPILER", "mpicc")
setenv("CMAKE_CXX_COMPILER", "mpic++")
setenv("CMAKE_Fortran_COMPILER", "mpifort")
