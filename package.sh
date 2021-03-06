#!/bin/sh

# --------------------------------------------------------------------------------
# This script is building packages for Alignak NSCA module thanks to the fpm
# application (https://github.com/jordansissel/fpm).
# -----
# Using this script and fpm requires:
# sudo apt-get install ruby ruby-dev rubygems build-essential
#  sudo gem install --no-ri --no-rdoc fpm
# -----
# This script updates the .bintray-*.json file to update:
# - the target repo, replacing sed_version_repo with the appropriate
#  repository name: alignak-deb-testing or alignak-deb-stable
# - the version name, description and release date, replacing
#  sed_version_name, sed_version_desc and sed_version_released
# -----
# Command line parameters:
# - git branch name:
# - master will build a stable version (alignak_deb-stable repository)
#   -> python-alignak_x.x.x_all.deb
# - develop will build a develop version (alignak_deb-testing repository)
#   -> python-alignak_x.x.x-dev_all.deb
# - any other will build a develop named version (alignak_deb-testing repository)
#   -> python-alignak_x.x.x-mybranch_all.deb
#
# Note that it is not recommended to use anything else than alphabetic characters in the
# branch name according to the debian version name policy! Else, the package will not even
# install on the system!
#
# - python version:
#   2.7, 3.5 (when called from the Travis build, it is the most recent python 3 version)
#
# - package type:
#   deb (default), rpm, freebsd, apk, pacman, ...
# Indeed all the package types supported by fpm
# --------------------------------------------------------------------------------
#set -ev

# Parse command line arguments
# Default is branch develop, python 3.5
git_branch=$1
python_version=$2
input_type="python"
output_type=$3
if [ $# -eq 0 ]; then
   git_branch="develop"
   python_version="3.5"
   output_type="deb"
fi
if [ $# -eq 1 ]; then
   python_version="3.5"
   output_type="deb"
fi
if [ $# -eq 2 ]; then
   output_type="deb"
fi

echo "Installing fpm..."
gem install --no-ri --no-rdoc fpm

echo "Building ${output_type} package for branch ${git_branch}, python version ${python_version}"

# Python prefix - no more used but kept for compatibility
python_prefix="python3"
if [ "${python_version}" = "2.7" ]; then
   python_prefix="python"
#   python_version="2"
#else
#   python_version="3"
fi

# Package information - no more python-prefix but kept for compatibility
pkg_name="${python_prefix}-alignak-module-glpi"
pkg_description="Alignak Glpi module"
pkg_url="http://alignak.net"
pkg_team="Alignak Team (contact@alignak.net)"

version=`python -c "from version import __version__;print(__version__)"`
version_date=`date "+%Y-%m-%d"`

mkdir -p dist
cp .bintray-${output_type}.json dist/.bintray-${output_type}.json

if [ "${git_branch}" = "master" ]; then
   # Updating deploy script for Alignak stable version
   sed -i -e "s|\"sed_package_name\"|\"${pkg_name}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_name\"|\"${version}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_desc\"|\"Stable version\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_released\"|\"${version_date}\"|g" dist/.bintray-${output_type}.json

   # Stable repo
   sed -i -e "s/sed_version_repo/alignak-${output_type}-stable/g" dist/.bintray-${output_type}.json
elif [ "${git_branch}" = "develop" ]; then
   # Version is version number + develop
   version="${version}-develop"
#   version="-dev"

   # Updating deploy script for Alignak develop version
   sed -i -e "s|\"sed_package_name\"|\"${pkg_name}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_name\"|\"${version}-${version_date}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_desc\"|\"Development version\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_released\"|\"${version_date}\"|g" dist/.bintray-${output_type}.json

   # Testing repo
   sed -i -e "s/sed_version_repo/alignak-${output_type}-testing/g" dist/.bintray-${output_type}.json
else
   # Version
   if [ "${git_branch}" = "${version}" ]; then
      version="${git_branch}"
   else
      version="${version}-${git_branch}"
   fi

   # Updating deploy script for any other branch / tag
   sed -i -e "s|\"sed_package_name\"|\"${pkg_name}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_name\"|\"${version}-${version_date}\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_desc\"|\"Branch $1 version\"|g" dist/.bintray-${output_type}.json
   sed -i -e "s|\"sed_version_released\"|\"${version_date}\"|g" dist/.bintray-${output_type}.json

   # Testing repo
   sed -i -e "s/sed_version_repo/alignak-${output_type}-testing/g" dist/.bintray-${output_type}.json
fi

echo "----------"
echo "BinTray configuration file:"
echo "----------"
cat dist/.bintray-${output_type}.json
echo "----------"

# Run fpm:
# Add --verbose for a verbose (very...) mode to have more information
# - from python to deb packages, for all architectures
# Use python dependencies - all Alignak python packages
# are packaged in the main distros so it will use the
# distro packages rather than the python one
# Force python interpreter else Travis deployment will use its own venv interpreter!
echo "Running fpm..."
if [ "${output_type}" = "deb" ]; then
   fpm \
      --force \
      --input-type ${input_type} \
      --output-type ${output_type} \
      --package "./dist" \
      --architecture all \
      --license AGPL \
      --version ${version} \
      --name "${pkg_name}" \
      --description "${pkg_description}" \
      --url "${pkg_url}" \
      --vendor "${pkg_team}" \
      --maintainer "${pkg_team}" \
      --python-package-name-prefix "${python_prefix}" \
      --python-scripts-executable "/usr/bin/env python" \
      --python-install-lib "/usr/lib/python${python_version}/site-packages" \
      --python-install-data '/usr/local' \
      --python-install-bin '/usr/local/bin' \
      --no-python-dependencies \
      --deb-no-default-config-files \
      ./setup.py
elif [ "${output_type}" = "rpm" ]; then
   fpm \
      --force \
      --input-type ${input_type} \
      --output-type ${output_type} \
      --package "./dist" \
      --architecture all \
      --license AGPL \
      --version ${version} \
      --name "${pkg_name}" \
      --description "${pkg_description}" \
      --url "${pkg_url}" \
      --vendor "${pkg_team}" \
      --maintainer "${pkg_team}" \
      --python-package-name-prefix "${python_prefix}" \
      --python-scripts-executable "/usr/bin/env python" \
      --python-install-lib "/usr/lib/python${python_version}/site-packages" \
      --python-install-data '/usr/local' \
      --python-install-bin '/usr/local/bin' \
      --no-python-dependencies \
      ./setup.py
else
   fpm \
      --force \
      --input-type ${input_type} \
      --output-type ${output_type} \
      --package "./dist" \
      --architecture all \
      --license AGPL \
      --version ${version} \
      --name "${pkg_name}" \
      --description "${pkg_description}" \
      --url "${pkg_url}" \
      --vendor "${pkg_team}" \
      --maintainer "${pkg_team}" \
      --python-scripts-executable "/usr/bin/env python" \
      --python-install-lib "/usr/lib/python${python_version}/site-packages" \
      --python-install-data '/usr/local' \
      --python-install-bin '/usr/local/bin' \
      --no-python-dependencies \
      ./setup.py
fi