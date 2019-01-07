Alignak NSCA receiver Module
============================

*Alignak NSCA module for the Alignak Receiver*

.. image:: https://landscape.io/github/Alignak-monitoring-contrib/alignak-module-glpi/develop/landscape.svg?style=flat
    :target: https://landscape.io/github/Alignak-monitoring-contrib/alignak-module-glpi/develop
    :alt: Development code static analysis

.. image:: https://coveralls.io/repos/Alignak-monitoring-contrib/alignak-module-glpi/badge.svg?branch=develop
    :target: https://coveralls.io/r/Alignak-monitoring-contrib/alignak-module-glpi
    :alt: Development code tests coverage

.. image:: https://badge.fury.io/py/alignak_module_glpi.svg
    :target: https://badge.fury.io/py/alignak-module-nsca
    :alt: Most recent PyPi version

.. image:: https://img.shields.io/badge/IRC-%23alignak-1e72ff.svg?style=flat
    :target: http://webchat.freenode.net/?channels=%23alignak
    :alt: Join the chat #alignak on freenode.net

.. image:: https://img.shields.io/badge/License-AGPL%20v3-blue.svg
    :target: http://www.gnu.org/licenses/agpl-3.0
    :alt: License AGPL v3

Installation
------------

The installation of this module will copy some configuration files in the Alignak default configuration directory (eg. */usr/local/share/alignak*). The copied files are located in the default sub-directory used for the modules (eg. *arbiter/modules*).

From Alignak packages repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

More information in the `online Alignak documentation <http://docs.alignak.net>`_. Here is only an abstract...

Debian::

    # Alignak DEB stable packages
    sudo echo deb https://dl.bintray.com/alignak/alignak-deb-stable xenial main | sudo tee -a /etc/apt/sources.list.d/alignak.list
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv D401AB61

    sudo apt-get update
    sudo apt install python-alignak-module-glpi

CentOS::

glpiFrom PyPI
~~~~~~~~~
To install the module from PyPI::

    sudo pip install alignak-module-glpi


From source files
~~~~~~~~~~~~~~~~~
To install the module from the source files (for developing purpose)::

    git clone https://github.com/Alignak-monitoring-contrib/alignak-module-glpi
    cd alignak-module-nsglpica
    sudo pip install . -e

**Note:** *using `sudo python setup.py install` will not correctly manage the package configuration files! The recommended way is really to use `pip`;)*


Short description
-----------------

This module for Alignak receiver reads and decodes NSCA passive notifications to dispatch them into the Alignak framework.


Features / Known limitations
----------------------------

Handles NSCA version 3 protocol

Check the NSCA packet timestamp for staled data (older than a certain amount of time) or 'future' data (future timestamp).

Consider the `host_check` service received data as a passive host check. Useful if your NSCA client does not handle correctly the passive host check syntax ;)

The NSCA module implementation is currently limited to the "xor" obfuscation/encryption.

.. note:: To make the module add some information in the daemon log file, define the ``ALIGNAK_LOG_ACTIONS`` environment variable. It will dump a part of the received NSCA packets...

Configuration
-------------

Once installed, this module has its own configuration file in the */usr/local/share/alignak/etc/alignak.d* directory.
The default configuration file is *alignak-module-glpi.ini*. This file is commented to help configure all the parameters.

The default configuration is convenient for 'recent' NSCA client implementing NSCA version 3.

This configuration has been tested with Linux send_nsca 2.9.1 and Windows NSClient most recent versions (from 0.4.1).

.. note:: received NSCA packets which are not containing version 3 information are dropped by the module!

To configure Alignak broker to use this module:

- edit the borker daemon configuration file
- add the `modules` parameter value (`glpi`) to the `modules` parameter of the daemon



Bugs, issues and contributing
-----------------------------

Contributions to this project are welcome and encouraged ... `issues in the project repository <https://github.com/alignak-monitoring-contrib/alignak-module-glpi/issues>`_ are the common way to raise an information.
