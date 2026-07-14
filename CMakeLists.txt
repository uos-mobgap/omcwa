cmake_minimum_required(VERSION 3.15...3.26)
project(omcwa LANGUAGES C CXX)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

add_subdirectory(native)
