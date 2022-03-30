@setlocal enableextensions enabledelayedexpansion
@echo off

echo Calling VS %VS_VERSION% vcvarsall for Python %PYTHON_VERSION% %PYTHON_ARCHITECTURE%
vswhere -version %VS_VERSION% -find VC\**\vcvarsall.bat > temp.txt
set /p VCVARSALL=<temp.txt
echo "%VCVARSALL%" %PYTHON_ARCHITECTURE%
call "%VCVARSALL%" %PYTHON_ARCHITECTURE%

set PATH=%PATH%;%BUILD_SOURCESDIRECTORY%\win_flex_bison

echo Preparing third_party
cd %BUILD_SOURCESDIRECTORY%
md third_party
cd third_party
md include
md bin
md lib

echo ------------------------------------------------------------------------------------------
echo Compiling libmpdec
echo ------------------------------------------------------------------------------------------
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

echo ------------------------------------------------------------------------------------------
echo Compiling zlib
echo ------------------------------------------------------------------------------------------
cd "%BUILD_SOURCESDIRECTORY%\zlib-1.2.12"
nmake -f win32\Makefile.msc zlib.lib
copy /Y zlib.lib "%BUILD_SOURCESDIRECTORY%\third_party\lib"
copy /Y zlib.h "%BUILD_SOURCESDIRECTORY%\third_party\include"
copy /Y zconf.h "%BUILD_SOURCESDIRECTORY%\third_party\include"

echo ------------------------------------------------------------------------------------------
echo Compiling pcre
echo ------------------------------------------------------------------------------------------
cd "%BUILD_SOURCESDIRECTORY%\pcre-8.45"
md out
cd out
cmake -G "NMake Makefiles" -DPCRE_SUPPORT_UTF=ON -DPCRE_BUILD_PCREGREP=OFF -DPCRE_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=%BUILD_SOURCESDIRECTORY%\third_party -DCMAKE_INSTALL_PREFIX=%BUILD_SOURCESDIRECTORY%\third_party ..
nmake
nmake install

echo ------------------------------------------------------------------------------------------
echo Compiling tidy-html5
echo ------------------------------------------------------------------------------------------
cd "%BUILD_SOURCESDIRECTORY%\tidy-html5-5.8.0"
md out
cd out
cmake -G "NMake Makefiles" -DBUILD_SHARED_LIB=OFF -DINCLUDE_INSTALL_DIR=include\tidy -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=%BUILD_SOURCESDIRECTORY%\third_party -DCMAKE_INSTALL_PREFIX=%BUILD_SOURCESDIRECTORY%\third_party ..
nmake
nmake install

echo ------------------------------------------------------------------------------------------
echo Compiling ebpr and konga_client
echo ------------------------------------------------------------------------------------------
cd "%BUILD_SOURCESDIRECTORY%\konga"
md out
cd out
cmake .. -DOPT_USE_CPP11=1 -DOPT_NO_SSL=1 -DOPT_KONGALIB_WHEEL=1 -DOPT_KONGALIB_ROOT="%BUILD_SOURCESDIRECTORY%" -DCMAKE_PREFIX_PATH="%BUILD_SOURCESDIRECTORY%\third_party" -DCMAKE_INSTALL_PREFIX=%BUILD_SOURCESDIRECTORY%\third_party -G "NMake Makefiles"
nmake
nmake install
