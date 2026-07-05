# ReefVolt CAN cluster message catalog — shared library.
# SPDX-License-Identifier: Apache-2.0
#
# Usage from a board firmware:
#   add_subdirectory(${CMAKE_SOURCE_DIR}/../shared/reefvolt_can reefvolt_can)
#   target_link_libraries(<board> PRIVATE reefvolt_can)

cmake_minimum_required(VERSION 3.16)

add_library(reefvolt_can STATIC
    src/reefvolt_can.c
)

target_include_directories(reefvolt_can PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(reefvolt_can PUBLIC c_std_11)
