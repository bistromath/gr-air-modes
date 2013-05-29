# - Find zeromq libraries
# This module finds zeromq if it is installed and determines where the
# include files and libraries are. It also determines what the name of
# the library is. This code sets the following variables:
#
#  ZEROMQ_FOUND               - have the zeromq libs been found
#  ZEROMQ_LIBRARIES           - path to the zeromq library
#  ZEROMQ_INCLUDE_DIRS        - path to where zmq.h is found
#  ZEROMQ_DEBUG_LIBRARIES     - path to the debug library

#INCLUDE(CMakeFindFrameworks)
# Search for the zeromq framework on Apple.
#CMAKE_FIND_FRAMEWORKS(ZeroMQ)

IF(WIN32)
	FIND_LIBRARY(ZEROMQ_DEBUG_LIBRARY
		NAMES libzmq_d zmq_d
		PATHS
			${ZEROMQ_LIBRARIES}
	)
ENDIF(WIN32)

FIND_LIBRARY(ZEROMQ_LIBRARY
	NAMES libzmq zmq 
	PATHS
		${ZEROMQ_LIBRARIES}
		${NSCP_LIBRARYDIR}
)

#  IF(ZeroMQ_FRAMEWORKS AND NOT ZEROMQ_INCLUDE_DIR)
#    FOREACH(dir ${ZeroMQ_FRAMEWORKS})
#      SET(ZEROMQ_FRAMEWORK_INCLUDES ${ZEROMQ_FRAMEWORK_INCLUDES}
#        ${dir}/Versions/${_CURRENT_VERSION}/include/zeromq${_CURRENT_VERSION})
#    ENDFOREACH(dir)
#  ENDIF(ZeroMQ_FRAMEWORKS AND NOT ZEROMQ_INCLUDE_DIR)

FIND_PATH(ZEROMQ_INCLUDE_DIR
	NAMES zmq.hpp
	PATHS
#		${ZEROMQ_FRAMEWORK_INCLUDES}
		${ZEROMQ_INCLUDE_DIRS}
		${NSCP_INCLUDEDIR}
		${ZEROMQ_INCLUDE_DIR}
)

MARK_AS_ADVANCED(
  ZEROMQ_DEBUG_LIBRARY
  ZEROMQ_LIBRARY
  ZEROMQ_INCLUDE_DIR
)
SET(ZEROMQ_INCLUDE_DIRS "${ZEROMQ_INCLUDE_DIR}")
SET(ZEROMQ_LIBRARIES "${ZEROMQ_LIBRARY}")
SET(ZEROMQ_DEBUG_LIBRARIES "${ZEROMQ_DEBUG_LIBRARY}")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(ZeroMQ DEFAULT_MSG ZEROMQ_LIBRARIES ZEROMQ_INCLUDE_DIRS)
