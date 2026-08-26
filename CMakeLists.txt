cmake_minimum_required(VERSION 3.14)
project(termux_llamacpp C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_BUILD_TYPE Release)

# ARM64 Optimization Flags
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    add_compile_options(-O3 -march=armv8-a+fp16+dotprod -fopenmp)
    add_link_options(-fopenmp)
endif()

message(STATUS "Configuring termux-llamacpp for ${CMAKE_SYSTEM_PROCESSOR}")
