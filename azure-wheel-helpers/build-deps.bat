@setlocal enableextensions enabledelayedexpansion
@echo off

if "%2" neq "" (
	echo "Calling vcvarsall at %2"
    call %2 %3
)

echo Preparing third_party
set "ROOT=%~dp0\.."
cd %ROOT%
md third_party
cd third_party
md include
md bin
md lib


echo Compiling libmpdec
cd "%ROOT%\mpdecimal-2.4.2\vcbuild"
call "vcbuild%1"
copy /Y "dist%1\libmpdec-2.4.2.lib" "%ROOT%\third_party\lib\mpdec.lib"
copy /Y dist%1\*.h "%ROOT%\third_party\include"
copy /Y ..\libmpdec\vc*.h "%ROOT%\third_party\include"
dir /s "%ROOT%\third_party"

echo Compiling zlib
cd "%ROOT%\zlib-1.2.11"
nmake -f win32\Makefile.msc zlib.lib
copy /Y zlib.lib "%ROOT%\third_party\lib"',
copy /Y zlib.h "%ROOT%\third_party\include"',
copy /Y zconf.h "%ROOT%\third_party\include"',

echo Compiling pcre
cd "%ROOT%\pcre-8.43"
md out
cd out
cmake -G "NMake Makefiles" -DPCRE_SUPPORT_UTF=On -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=%ROOT%\third_party ..
nmake
nmake install

echo Compiling ebpr and konga_client
cd "%ROOT%\konga"
md out
cd out
cmake .. -DOPT_USE_CPP11=1 -DOPT_NO_SSL=1 -DOPT_KONGALIB_WHEEL=1 -DTHIRD_PARTY="%ROOT%\third_party" -G "NMake Makefiles"
nmake
nmake install
