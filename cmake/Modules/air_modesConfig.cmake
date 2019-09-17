INCLUDE(FindPkgConfig)
PKG_CHECK_MODULES(PC_AIR_MODES air_modes)

FIND_PATH(
    AIR_MODES_INCLUDE_DIRS
    NAMES air_modes/api.h
    HINTS $ENV{AIR_MODES_DIR}/include
    ${PC_AIR_MODES_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    AIR_MODES_LIBRARIES
    NAMES gnuradio-air-modes
    HINTS $ENV{AIR_MODES_DIR}/lib
    ${PC_AIR_MODES_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/air_modesTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(AIR_MODES DEFAULT_MSG AIR_MODES_LIBRARIES AIR_MODES_INCLUDE_DIRS)
MARK_AS_ADVANCED(AIR_MODES_LIBRARIES AIR_MODES_INCLUDE_DIRS)
