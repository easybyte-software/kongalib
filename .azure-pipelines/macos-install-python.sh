PYTHON_VERSION="$1"

case $PYTHON_VERSION in
2.7)
  FULL_VERSION=2.7.16
  INSTALLER_NAME=python-$FULL_VERSION-macosx10.9.pkg
  ;;
3.7)
  FULL_VERSION=3.7.6
  INSTALLER_NAME=python-$FULL_VERSION-macosx10.9.pkg
  ;;
3.8)
  FULL_VERSION=3.8.7
  INSTALLER_NAME=python-$FULL_VERSION-macosx10.9.pkg
  ;;
3.9)
  FULL_VERSION=3.9.7
  INSTALLER_NAME=python-$FULL_VERSION-macos11.pkg
  ;;
3.10)
  FULL_VERSION=3.10.0
  INSTALLER_NAME=python-$FULL_VERSIONpost2-macos11.pkg
  ;;
esac

URL=https://www.python.org/ftp/python/$FULL_VERSION/$INSTALLER_NAME

PY_PREFIX=/Library/Frameworks/Python.framework/Versions

set -e -x

curl $URL > $INSTALLER_NAME

sudo installer -pkg $INSTALLER_NAME -target /

sudo rm /usr/local/bin/python
sudo ln -s $PY_PREFIX/$PYTHON_VERSION/bin/python$PYTHON_VERSION /usr/local/bin/python

which python
python --version
if [ "$PYTHON_VERSION" == "2.7" ]; then
	python -m ensurepip
fi

python -m pip install setuptools twine wheel
