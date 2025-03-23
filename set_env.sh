###intel####
source ${INTEL_PATH}/setvars.sh
export CC=${CC}

###dep#####
export PATH=${DEP_DIR}/bin:$PATH
export LD_LIBRARY_PATH=${DEP_DIR}/lib:$LD_LIBRARY_PATH
export CPATH=${DEP_DIR}/include:$CPATH

###netcdf
export NETCDF=${DEP_DIR}
export JASPERLIB=${DEP_DIR}/lib
export JASPERINC=${DEP_DIR}/include


###wrf-wps
export WRF_DIR=${INSTALL_PATH}/src/${WRF_V}