cmake_minimum_required(VERSION 3.15...3.26)
project(omcwa LANGUAGES C CXX)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)

if(NOT pybind11_DIR)
  execute_process(
    COMMAND "${Python_EXECUTABLE}" -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
endif()

find_package(pybind11 CONFIG REQUIRED)

add_subdirectory(native)
