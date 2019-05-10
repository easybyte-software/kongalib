file(GLOB KONGALIB_PY_SOURCES "src/*.py")
list(REMOVE_ITEM KONGALIB_PY_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/constants.py")
file(GLOB KONGALIB_C_SOURCES "src/_kongalib/*.cpp")
file(GLOB KONGALIB_C_HEADERS "src/_kongalib/*.h")

set(DEPS
	${KONGALIB_PY_SOURCES}
	${KONGALIB_C_SOURCES}
	${KONGALIB_C_HEADERS}
	${PROJECT_SOURCE_DIR}/data/cl_messages.xml
	${PROJECT_SOURCE_DIR}/data/mga/mga_messages.xml
	${PROJECT_SOURCE_DIR}/data/mga/commands.xml
	$<TARGET_FILE:ebpr_s>
	$<TARGET_FILE:konga_client_s>
)

if (BUILD_DEBUG)
	set(KONGALIB_SETUP_PARAMS "--debug")
endif()
if (APPLE)
	set(KONGALIB_SETUP_PARAMS ${KONGALIB_SETUP_PARAMS} --sdk ${OPT_SDK})
endif()

if (UNIX)
	set(KONGALIB_CFLAGS "-I${PROJECT_SOURCE_DIR}/include -I${PROJECT_SOURCE_DIR}/include/mga")
	set(KONGALIB_LDFLAGS "-L$<TARGET_FILE_DIR:ebpr_s> -L$<TARGET_FILE_DIR:konga_client_s>")
else()
	set(KONGALIB_CFLAGS "/I\"${PROJECT_SOURCE_DIR}\\include\" /I\"${PROJECT_SOURCE_DIR}\\include\\mga\"")
	set(KONGALIB_LDFLAGS "/LIBPATH:\"$<TARGET_FILE_DIR:ebpr_s>\" /LIBPATH:\"$<TARGET_FILE_DIR:konga_client_s>\"")
endif()

add_custom_command(OUTPUT kongalib_module
	COMMAND ${CMAKE_COMMAND} -E remove_directory build
	COMMAND ${CMAKE_COMMAND} -E remove_directory dist
	COMMAND ${CMAKE_COMMAND} -E env
	"KONGALIB_CFLAGS=${KONGALIB_CFLAGS}"
	"KONGALIB_LDFLAGS=${KONGALIB_LDFLAGS}"
	${PYTHON} setup.py -q build bdist_egg ${KONGALIB_SETUP_PARAMS}
	COMMAND ${CMAKE_COMMAND} -E touch ${CMAKE_CURRENT_BINARY_DIR}/kongalib_module
	DEPENDS ${DEPS}
	WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
	VERBATIM
)

add_custom_target(kongalib ALL DEPENDS kongalib_module ebpr_s konga_client_s)

install(CODE "execute_process(COMMAND ${PYTHON} ${PROJECT_SOURCE_DIR}/build/install_python_module.py kongalib WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})")
