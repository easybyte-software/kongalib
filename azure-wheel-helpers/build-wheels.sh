# Copyright (c) 2019, Henry Schreiner.
#
# Distributed under the 3-clause BSD license, see accompanying file LICENSE
# or https://github.com/scikit-hep/azure-wheel-helpers for details.

# Based on https://github.com/pypa/python-manylinux-demo/blob/master/travis/build-wheels.sh
# with CC0 license here: https://github.com/pypa/python-manylinux-demo/blob/master/LICENSE

#!/bin/bash

set -e -x

yum install -y zlib-devel pcre-devel dbus-devel dbus-libs cmake

wget https://www.bytereef.org/software/mpdecimal/releases/mpdecimal-2.4.2.tar.gz
tar -zxvf mpdecimal-2.4.2.tar.gz
cd mpdecimal-2.4.2
./configure
CFLAGS=-fPIC make -j2
sudo make install

git clone https://${GH_USER}:${GH_PASSWORD}@github.com/easybyte-software/konga.git
cd konga
mkdir -p out
cd out
cmake .. -DOPT_USE_CPP11=1 -DOPT_NO_SSL=1 -DOPT_KONGALIB_WHEEL=1
make -j2
sudo make install

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

