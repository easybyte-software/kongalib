@setlocal enableextensions enabledelayedexpansion
@echo off

if "%PYTHON_VERSION%"=="2.7" (
    echo Calling VS 2008 vcvarsall for Python 2.7 %PYTHON_ARCHITECTURE%
    call "C:\Program Files (x86)\Common Files\Microsoft\Visual C++ for Python\9.0\vcvarsall.bat" %PYTHON_ARCHITECTURE%
) else (
	echo Calling VS 2019 vcvarsall for Python %PYTHON_VERSION% %PYTHON_ARCHITECTURE%
	call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" %PYTHON_ARCHITECTURE%
)

echo Installing winflexbison
choco install winflexbison

echo Preparing third_party
cd %BUILD_SOURCESDIRECTORY%
md third_party
cd third_party
md include
md bin
md lib

echo Compiling libmpdec
cd "%BUILD_SOURCESDIRECTORY%\mpdecimal-2.4.2\vcbuild"
if "%PYTHON_ARCHITECTURE%"=="x86" (
	set "MPDEC_BITS=32"
) else (
	set "MPDEC_BITS=64"
)
call "vcbuild%MPDEC_BITS%"
copy /Y "dist%MPDEC_BITS%\libmpdec-2.4.2.lib" "%BUILD_SOURCESDIRECTORY%\third_party\lib\mpdec.lib"
copy /Y dist%MPDEC_BITS%\*.h "%BUILD_SOURCESDIRECTORY%\third_party\include"
copy /Y ..\libmpdec\vc*.h "%BUILD_SOURCESDIRECTORY%\third_party\include"
dir /s "%BUILD_SOURCESDIRECTORY%\third_party"

echo Compiling zlib
cd "%BUILD_SOURCESDIRECTORY%\zlib-1.2.11"
nmake -f win32\Makefile.msc zlib.lib
copy /Y zlib.lib "%BUILD_SOURCESDIRECTORY%\third_party\lib"
copy /Y zlib.h "%BUILD_SOURCESDIRECTORY%\third_party\include"
copy /Y zconf.h "%BUILD_SOURCESDIRECTORY%\third_party\include"

echo Compiling pcre
cd "%BUILD_SOURCESDIRECTORY%\pcre-8.31"
md out
cd out
cmake -G "NMake Makefiles" -DPCRE_SUPPORT_UTF=ON -DPCRE_BUILD_PCREGREP=OFF -DPCRE_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=%BUILD_SOURCESDIRECTORY%\third_party -DCMAKE_INSTALL_PREFIX=%BUILD_SOURCESDIRECTORY%\third_party ..
nmake
nmake install

echo Compiling ebpr and konga_client
cd "%BUILD_SOURCESDIRECTORY%\konga"
md out
cd out
cmake .. -DOPT_USE_CPP11=1 -DOPT_NO_SSL=1 -DOPT_KONGALIB_WHEEL=1 -DOPT_KONGALIB_ROOT="%BUILD_SOURCESDIRECTORY%" -DCMAKE_PREFIX_PATH="%BUILD_SOURCESDIRECTORY%\third_party" -DCMAKE_INSTALL_PREFIX=%BUILD_SOURCESDIRECTORY%\third_party -G "NMake Makefiles"
nmake
nmake install
