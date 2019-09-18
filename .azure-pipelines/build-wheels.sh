#!/bin/bash

set -e -x

yum install -y zlib-devel pcre-devel dbus-devel dbus-libs cmake

cd /io/mpdecimal-2.4.2
./configure
CFLAGS=-fPIC make -j2
make install

cd /io/konga
mkdir -p out
cd out
cmake .. -DOPT_USE_CPP11=1 -DOPT_NO_SSL=1 -DOPT_KONGALIB_WHEEL=1
make -j2 kongalib_wheel

cd /io
rm -fr build dist *.egg-info


PYTHONS=(/opt/python/*/bin)

for PYBIN in "${PYTHONS[@]}"; do
    "${PYBIN}/pip" wheel /io/ -w wheelhouse/
done

for whl in wheelhouse/kongalib-*.whl; do
    auditwheel repair "$whl" -w /io/wheelhouse/
done

for PYBIN in "${PYTHONS[@]}"; do
    "${PYBIN}/python" -m pip install kongalib --no-index -f /io/wheelhouse
done

