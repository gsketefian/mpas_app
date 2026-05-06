help([[
This module loads the python environment for running the MPAS App on 
the NOAA RDHPC machine Gaea C6
]]) 
 
whatis([===[Loads libraries needed for running the MPAS App on Hera ]===]) 
prepend_path("MODULEPATH", "/ncrc/proj/epic/rocoto/modulefiles")

load("rocoto/1.3.6")
load("conda")

if mode() == "load" then
    LmodMsgRaw([===[Please do the following to activate conda:
	>conda activate mpas_app
]===])
end

