# compile vendored omconvert C sources into a static library
# exclude main.c and mmap-win32.c on non-Windows platforms
file(GLOB OMCONVERT_SOURCES CONFIGURE_DEPENDS "vendored/omconvert/*.c")
list(FILTER OMCONVERT_SOURCES EXCLUDE REGEX "main\\.c$")

if(NOT WIN32)
    list(FILTER OMCONVERT_SOURCES EXCLUDE REGEX "mmap-win32\\.c$")
endif()

add_library(omconvert STATIC ${OMCONVERT_SOURCES})

# omconvert includes stay PRIVATE on the C target
# bridge gets its own include path
# never place a file named VERSION on include dirs
# macOS APFS shadows C++ <version> header - use OMCONVERT_VERSION instead
target_include_directories(omconvert PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/vendored/omconvert")
target_compile_options(omconvert PRIVATE -O3 -Wall)
set_property(TARGET omconvert PROPERTY C_STANDARD 99)
set_property(TARGET omconvert PROPERTY C_STANDARD_REQUIRED ON)

if(UNIX AND NOT APPLE)
    target_compile_definitions(omconvert PRIVATE _BSD_SOURCE)
endif()

if(UNIX)
    target_link_libraries(omconvert PUBLIC m pthread)
endif()

pybind11_add_module(_native bridge.cpp)

# bridge includes omconvert headers
target_include_directories(_native PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/vendored/omconvert")
target_link_libraries(_native PRIVATE omconvert)
target_compile_options(_native PRIVATE -O3 -Wall)

if(UNIX)
    target_link_libraries(_native PRIVATE m pthread)
endif()

install(TARGETS _native DESTINATION omcwa)
