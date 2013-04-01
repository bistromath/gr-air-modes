# Copyright 2011,2013 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.

########################################################################
# Include python install macros
########################################################################
include(GrPython)
if(NOT PYTHONINTERP_FOUND)
    return()
endif()

find_package(PyQt4)
if(NOT PYQT4_FOUND)
    message(STATUS "PyQt4 not found, not installing GUI application")
    return()
endif()

if(NOT PYUIC4_FOUND)
    message(STATUS "pyuic4 not found, not installing GUI application")
    return()
endif()

find_package(Qwt)
if(NOT QWT_FOUND)
    message(STATUS "Qwt not found, not installing GUI application")
    return()
endif()

set(RX_UI_SRC ${CMAKE_CURRENT_SOURCE_DIR}/modes_rx.ui)
set(RX_UI_PY_PRE_MASSAGE ${CMAKE_CURRENT_BINARY_DIR}/modes_rx_ui_borked.py)
set(RX_UI_PY ${CMAKE_CURRENT_BINARY_DIR}/modes_rx_ui.py)
set(PYUIC_MASSAGER sed "s/from qwt.* import/from PyQt4.Qwt5.Qwt import/")

add_custom_target(rx_ui ALL
    DEPENDS ${RX_UI_PY}
)

add_custom_command(OUTPUT ${RX_UI_PY_PRE_MASSAGE}
    COMMAND ${PYUIC4_EXECUTABLE} ${RX_UI_SRC} > ${RX_UI_PY_PRE_MASSAGE}
    MAIN_DEPENDENCY ${RX_UI_SRC}
)

add_custom_command(OUTPUT ${RX_UI_PY}
    COMMAND ${PYUIC_MASSAGER} ${RX_UI_PY_PRE_MASSAGE} > ${RX_UI_PY}
    MAIN_DEPENDENCY ${RX_UI_PY_PRE_MASSAGE}
)

########################################################################
# Install python sources
########################################################################
GR_PYTHON_INSTALL(
    FILES
    ${RX_UI_PY}
    DESTINATION ${GR_PYTHON_DIR}/air_modes
)

########################################################################
# Handle the unit tests
########################################################################
#include(GrTest)

#set(GR_TEST_TARGET_DEPS gnuradio-gr-air-modes)
#set(GR_TEST_PYTHON_DIRS ${CMAKE_BINARY_DIR}/swig)
#GR_ADD_TEST(qa_gr-air-modes ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/qa_gr-air-modes.py)
