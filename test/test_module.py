#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016: Alignak team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak.
#
# Alignak is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alignak is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Alignak.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Test the module
"""

import re
import os
import time
import pytest

from .alignak_test import AlignakTest
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule
from alignak.brok import Brok

# Set environment variable to ask code Coverage collection
os.environ['COVERAGE_PROCESS_START'] = '.coveragerc'

import alignak_module_glpi


class TestModules(AlignakTest):
    """
    This class contains the tests for the module
    """

    def test_module_loading(self):
        """
        Test module loading

        Alignak module loading

        :return:
        """
        self.setup_with_file('./cfg/alignak.cfg')
        self.assertTrue(self.conf_is_correct)
        self.show_configuration_logs()

        # No arbiter modules created
        modules = [m.module_alias for m in self._arbiter.link_to_myself.modules]
        self.assertListEqual(modules, [])

        # A broker module
        modules = [m.module_alias for m in self._broker_daemon.modules]
        self.assertListEqual(modules, ['glpi'])

        # No scheduler modules, except the default ones
        modules = [m.module_alias for m in self._scheduler_daemon.modules]
        self.assertListEqual(modules, ['inner-retention'])

        # No receiver modules
        modules = [m.module_alias for m in self._receiver.modules]
        self.assertListEqual(modules, [])

    def test_module_manager(self):
        """
        Test if the module manager manages correctly all the modules
        :return:
        """
        self.setup_with_file('./cfg/alignak.cfg')
        self.assertTrue(self.conf_is_correct)
        self.clear_logs()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'glpi',
            'module_types': 'DB',
            'python_name': 'alignak_module_glpi'
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager(self._broker_daemon)

        # Load an initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Loading module Glpi
        print("Load and init")
        self.show_logs()
        i=0
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_glpi' for glpi..."
        ), i)
        i += 1
        # Dict order is problematic :/
        # self.assert_log_match(re.escape(
        #     "Module properties: {'daemons': ['broker'], 'phases': ['running'], "
        #     "'type': 'glpi', 'external': True}"
        # ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_glpi' for glpi"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_glpi' (glpi)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Alignak starting module 'glpi'"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "using 'glpidb' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating availability: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating Shinken state: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating acknowledges states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1

        time.sleep(1)
        # Reload the module
        print("Reload")
        self.modulemanager.load([mod])
        self.modulemanager.get_instances()
        #
        # Loading module glpi
        self.show_logs()
        i = 0
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_glpi' for glpi..."
        ), i)
        i += 1
        # self.assert_log_match(re.escape(
        #     "Module properties: {'daemons': ['broker'], 'phases': ['running'], "
        #     "'type': 'glpi', 'external': True}"
        # ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_glpi' for glpi"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_glpi' (glpi)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Alignak starting module 'glpi'"
        ), i)
        i += 1
        # self.assert_log_match(re.escape(
        #     "Give an instance of alignak_module_glpi for alias: glpi"
        # ), i)
        # i += 1
        self.assert_log_match(re.escape(
            "using 'glpidb' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating availability: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating Shinken state: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating acknowledges states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_glpi' for glpi..."
        ), i)
        i += 1
        # self.assert_log_match(re.escape(
        #     "Module properties: {'daemons': ['broker'], 'phases': ['running'], "
        #     "'type': 'glpi', 'external': True}"
        # ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_glpi' for glpi"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_glpi' (glpi)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Request external process to stop for glpi"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "External process stopped."
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "Alignak starting module 'glpi'"
        ), i)
        i += 1
        # self.assert_log_match(re.escape(
        #     "Give an instance of alignak_module_glpi for alias: glpi"
        # ), i)
        # i += 1
        # self.assert_log_match(re.escape(
        #     "Give an instance of alignak_module_glpi for alias: glpi"
        # ), i)
        # i += 1
        self.assert_log_match(re.escape(
            "using 'glpidb' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating availability: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating Shinken state: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating acknowledges states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1

        my_module = self.modulemanager.instances[0]

        # Get list of not external modules
        self.assertListEqual([], self.modulemanager.get_internal_instances())
        for phase in ['configuration', 'late_configuration', 'running', 'retention']:
            self.assertListEqual([], self.modulemanager.get_internal_instances(phase))

        # Get list of external modules
        self.assertListEqual([my_module], self.modulemanager.get_external_instances())
        for phase in ['configuration', 'late_configuration', 'retention']:
            self.assertListEqual([], self.modulemanager.get_external_instances(phase))
        for phase in ['running']:
            self.assertListEqual([my_module], self.modulemanager.get_external_instances(phase))

        # Clear logs
        self.clear_logs()

        # Start external modules
        self.modulemanager.start_external_instances()

        # Starting external module glpi
        self.assert_log_match("Trying to initialize module: glpi", 0)
        self.assert_log_match("initialized", 1)
        self.assert_log_match("Module glpi is initialized.", 2)
        self.assert_log_match("Starting external module glpi", 3)
        self.assert_log_match("Starting external process for module glpi", 4)
        self.assert_log_match("glpi is now started", 5)

        # Check alive
        self.assertIsNotNone(my_module.process)
        self.assertTrue(my_module.process.is_alive())

        # Clear logs
        self.clear_logs()

        # Kill the external module (normal stop is .stop_process)
        my_module.kill()
        time.sleep(0.1)
        index = 0
        self.assert_log_match("Killing external module", index)
        index = index + 1
        # todo: This log is not expected! But it is probably because of the py.test ...
        # Indeed the receiver daemon that the module is attached to is receiving a SIGTERM !!!
        # self.assert_log_match(re.escape("glpi is still living 10 seconds after a normal kill, I help it to die"), index)
        # index = index + 1
        self.assert_log_match("External module killed", index)
        index = index + 1

        # Should be dead (not normally stopped...) but we still know a process for this module!
        self.assertIsNotNone(my_module.process)

        # Nothing special ...
        self.modulemanager.check_alive_instances()
        self.assert_log_match("The external module glpi died unexpectedly!", index)
        index = index + 1
        self.assert_log_match("Setting the module glpi to restart", index)
        index = index + 1

        # # Try to restart the dead modules
        # self.modulemanager.try_to_restart_deads()
        # self.assert_log_match("Trying to restart module: glpi", index)
        # index = index +1
        # self.assert_log_match("Too early to retry initialization, retry period is 5 seconds", index)
        # index = index +1
        #
        # # In fact it's too early, so it won't do it
        # # The module instance is still dead
        # self.assertFalse(my_module.process.is_alive())

        # So we lie, on the restart tries ...
        my_module.last_init_try = -5
        self.modulemanager.check_alive_instances()
        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to restart module: glpi", index)
        index = index + 1
        self.assert_log_match("Trying to initialize module: glpi", index)
        index = index + 1
        self.assert_log_match("initialized", index)
        index = index + 1
        self.assert_log_match("Module glpi is initialized.", index)
        index = index + 1
        self.assert_log_match("Restarting glpi...", index)
        index = index + 1

        # The module instance is now alive again
        self.assertTrue(my_module.process.is_alive())
        self.assert_log_match("Starting external process for module glpi", index)
        index = index + 1
        self.assert_log_match("glpi is now started", index)
        index = index + 1

        # There is nothing else to restart in the module manager
        self.assertEqual([], self.modulemanager.to_restart)

        # Clear logs
        self.clear_logs()

        # Let the module start and then kill it again
        time.sleep(3.0)
        my_module.kill()
        # time.sleep(5.0)
        self.show_logs()
        print("My module PID 2: %s" % my_module.process.pid)
        time.sleep(0.2)
        self.assertFalse(my_module.process.is_alive())
        index = 0
        self.assert_log_match("Killing external module", index)
        index = index +1
        # # todo: This log is not expected! But it is probably because of the py.test ...
        # # Indeed the receiver daemon that the module is attached to is receiving a SIGTERM !!!
        # self.assert_log_match(re.escape("'web-services' is still living 10 seconds after a normal kill, I help it to die"), index)
        # index = index +1
        self.assert_log_match("External module killed", index)
        index = index +1

        # The module is dead but the modules manager do not know yet!
        self.modulemanager.check_alive_instances()
        self.assert_log_match("The external module glpi died unexpectedly!", index)
        index = index +1
        self.assert_log_match("Setting the module glpi to restart", index)
        index = index +1

        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to restart module: glpi", index)
        index = index +1
        self.assert_log_match("Too early to retry initialization, retry period is 5 seconds", index)
        index = index +1

        # In fact it's too early, so it won't do it
        # The module instance is still dead
        self.assertFalse(my_module.process.is_alive())

        # So we lie, on the restart tries ...
        my_module.last_init_try = -5
        self.modulemanager.check_alive_instances()
        self.modulemanager.try_to_restart_deads()
        self.assert_log_match("Trying to restart module: glpi", index)
        index = index +1
        self.assert_log_match("Trying to initialize module: glpi", index)
        index = index +1
        self.assert_log_match("initialized", index)
        index = index + 1
        self.assert_log_match("Module glpi is initialized.", index)
        index = index + 1
        self.assert_log_match("Restarting glpi...", index)
        index = index +1

        # The module instance is now alive again
        self.assertTrue(my_module.process.is_alive())
        self.assert_log_match("Starting external process for module glpi", index)
        index = index +1
        self.assert_log_match("glpi is now started", index)
        index = index +1
        time.sleep(1.0)
        print("My module PID: %s" % my_module.process.pid)

        # Clear logs
        self.clear_logs()

        # And we clear all now
        self.modulemanager.stop_all()
        # Stopping module glpi

        index = 0
        self.assert_log_match("Shutting down modules...", index)
        index = index +1
        self.assert_log_match("Request external process to stop for glpi", index)
        index = index +1
        self.assert_log_match(re.escape("I'm stopping module 'glpi' (pid="), index)
        index = index +1
        # self.assert_log_match(re.escape("'glpi' is still living after a normal kill, I help it to die"), index)
        # index = index +1
        self.assert_log_match(re.escape("Killing external module (pid"), index)
        index = index +1
        self.assert_log_match(re.escape("External module killed"), index)
        index = index +1
        self.assert_log_match("External process stopped.", index)
        index = index +1

    def test_module_start_default(self):
        """Test the module initialization function, no parameters, using default
        :return:
        """
        # Obliged to call to get a self.logger...
        self.setup_with_file('./cfg/alignak.cfg')
        self.assertTrue(self.conf_is_correct)

        # Clear logs
        self.clear_logs()

        # -----
        # Default initialization
        # -----
        # Create an Alignak module
        mod = Module({
            'module_alias': 'glpi',
            'module_types': 'DB',
            'python_name': 'alignak_module_glpi'
        })

        instance = alignak_module_glpi.get_instance(mod)
        self.assertIsInstance(instance, BaseModule)
        self.show_logs()

        i = 0
        self.assert_log_match(re.escape(
            "using 'glpidb' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating availability: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating Shinken state: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating acknowledges states: False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1

    def test_module_db_fails(self):
        """Test the module initialization - DB connection fails

        :return:
        """
        # Obliged to call to get a self.logger...
        self.set_unit_tests_logger_level()
        self.setup_with_file('./cfg/alignak.cfg')
        self.assertTrue(self.conf_is_correct)

        # Clear logs
        self.clear_logs()

        # -----
        # Default initialization
        # -----
        # Create an Alignak module
        mod = Module({
            'module_alias': 'glpi',
            'module_types': 'DB',
            'python_name': 'alignak_module_glpi'
        })

        instance = alignak_module_glpi.get_instance(mod)
        self.assertIsInstance(instance, BaseModule)
        self.show_logs()

        i = 0
        self.assert_log_match(re.escape(
            "using 'glpi' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states (glpi_plugin_monitoring_hosts): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states (glpi_plugin_monitoring_services): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events (glpi_plugin_monitoring_serviceevents): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1

        # Initialize the module - DB connection
        self.clear_logs()

        # For test, update the module configuration
        instance.host = '192.168.1.1'
        instance.database = 'glpi-9.3'
        instance.user = 'glpi'
        instance.password = 'glpi'
        instance.update_hosts = True
        instance.update_services = True
        instance.update_services_events = True
        instance.init()

        i = 0
        self.assert_log_match(re.escape(
            "connecting to database glpi-9.3 on %s..." % instance.host), i)
        i += 1
        self.assert_log_match(re.escape(
            "database connection error: 2003: Can't connect to MySQL server on '%s:3306' "
            "(110 Connection timed out)" % instance.hosts_table), i)
        i += 1
        self.assert_log_match(re.escape("initialized"), i)

    def _db_connection(self, fake=True):
        """Test the module initialization with the DB connection

        Note that this test is executing correctly on a local test environment where a
        MariaDB is present with a configured DB!

        Using the kake_db parameter allows to skip the DB connection of the module
        :return:
        """
        # Obliged to call to get a self.logger...
        self.set_unit_tests_logger_level()
        self.setup_with_file('./cfg/alignak.cfg')
        self.assertTrue(self.conf_is_correct)

        # Clear logs
        self.clear_logs()

        # -----
        # Default initialization
        # -----
        # Create an Alignak module
        mod = Module({
            'module_alias': 'glpi',
            'module_types': 'DB',
            'python_name': 'alignak_module_glpi'
        })

        instance = alignak_module_glpi.get_instance(mod)
        self.assertIsInstance(instance, BaseModule)
        self.show_logs()

        i = 0
        self.assert_log_match(re.escape(
            "using 'glpi' database on 127.0.0.1:3306 (user = alignak)"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating hosts states (glpi_plugin_monitoring_hosts): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services states (glpi_plugin_monitoring_services): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "updating services events (glpi_plugin_monitoring_serviceevents): False"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit period: 60s"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical commit volume: 1000 lines"
        ), i)
        i += 1
        self.assert_log_match(re.escape(
            "periodical DB connection test period: 0s"
        ), i)
        i += 1
        self.clear_logs()

        # For test, update the module configuration
        instance.fake_db = fake

        instance.host = '192.168.43.177'
        instance.database = 'glpi-9.3'
        instance.user = 'glpi'
        instance.password = 'glpi'
        instance.update_hosts = True
        instance.update_services = True
        instance.update_services_events = True
        instance.init()

        # instance.check_database()

        i = 0
        self.assert_log_match(re.escape("connecting to database glpi-9.3 on %s..."
                                        % instance.host), i)
        if not fake:
            i += 1
            self.assert_log_match(re.escape("server information"), i)
        i += 1
        self.assert_log_match(re.escape("connected"), i)
        i += 1
        self.assert_log_match(re.escape("updating hosts states is enabled"), i)
        i += 1
        self.assert_log_match(re.escape("updating services states is enabled"), i)
        i += 1
        self.assert_log_match(re.escape("updating services events is enabled"), i)
        i += 1
        self.assert_log_match(re.escape("initialized"), i)
        i += 1

        return instance

    def test_module_db_connection(self):
        """Test the module initialization

        Note that this test is executing correctly on a local test environment where a
        MariaDB is present with a configured DB!

        :return:
        """
        # Fake the DB connection for tests!
        instance = self._db_connection(fake=True)

        # Initial host status
        # -----
        self.clear_logs()
        hcr = {
            "host_name": "srv001",
            "customs": {
                "_ENTITIESID": "3",
                "_HOSTSID": "4",
                "_ITEMTYPE": "Computer",
                "_ITEMSID": "6"
            },
            "last_chk": 1444427104,
            "state": "UP",
            "state_type": "HARD",
            "state_id": 0,
            "state_type_id": 1,
            "last_state_id": 0,
            "last_hard_state_id": 0,
            "output": "OK - host is up and running",
            "long_output": "",
            "perf_data": "uptime=1200 rta=0.049000ms;2.000000;3.000000;0.000000 pl=0%;50;80;0",
            "latency": 0.0,
            "execution_time": 2.14,
            'problem_has_been_acknowledged': False
        }
        b = Brok({'data': hcr, 'type': 'initial_host_status'}, False)
        b.prepare()
        instance.manage_brok(b)
        self.show_logs()
        # The module inner cache stored the host
        assert 'srv001' in instance.hosts_cache
        # items_id is not yet set!
        assert instance.hosts_cache['srv001'] == {
            'realm_name': 'All',
            'items_id': '6',
            'itemtype': 'Computer',
            'hostsid': '4',
        }
        assert instance.services_cache == {}

        # Initial service status
        # -----
        self.clear_logs()
        scr = {
            "host_name": "srv001",
            "service_description": "disks",
            "customs": {
                "_ENTITIESID": "3",
                "_HOSTITEMSID": "1",
                "_HOSTITEMTYPE": "Computer",
                "_ITEMTYPE": "Service",
                "_ITEMSID": "1"
            },
            "last_chk": 1444427104,
            "state": "OK",
            "state_type": "HARD",
            "state_id": 0,
            "state_type_id": 1,
            "last_state_id": 0,
            "last_hard_state_id": 0,
            "output": "OK - all is ok!",
            "long_output": "",
            "perf_data": "uptime=1200 rta=0.049000ms;2.000000;3.000000;0.000000 pl=0%;50;80;0",
            "latency": 0.2317881584,
            "execution_time": 3.1496069431000002,
            'problem_has_been_acknowledged': False
        }
        b = Brok({'data': scr, 'type': 'initial_service_status'}, False)
        b.prepare()
        instance.manage_brok(b)
        self.show_logs()
        # The module inner cache stored the host
        assert 'srv001' in instance.hosts_cache
        # items_id is not yet set!
        assert instance.hosts_cache['srv001'] == {
            'realm_name': 'All',
            'items_id': '6',
            'itemtype': 'Computer',
            'hostsid': '4',
        }
        # The module inner cache stored the service
        assert 'srv001/disks' in instance.services_cache
        # items_id is not yet set!
        assert instance.services_cache['srv001/disks'] == {
            'items_id': '1'
        }

        # Host check result
        # -----
        hcr = {
            "host_name": "srv001",

            "last_time_unreachable": 0,
            "last_problem_id": 0,
            "passive_check": False,
            "retry_interval": 1,
            "last_event_id": 0,
            "problem_has_been_acknowledged": False,
            "command_name": "pm-check_linux_host_alive",
            "last_state": "UP",
            "latency": 0.2317881584,
            "last_state_type": "HARD",
            "last_hard_state_change": 1444427108,
            "last_time_up": 0,
            "percent_state_change": 0.0,
            "state": "DOWN",
            "last_chk": 1444427104,
            "last_state_id": 0,
            "end_time": 0,
            "timeout": 0,
            "current_event_id": 10,
            "execution_time": 3.1496069431000002,
            "start_time": 0,
            "return_code": 2,
            "state_type": "SOFT",
            "output": "CRITICAL - Plugin timed out after 10 seconds",
            "in_checking": True,
            "early_timeout": 0,
            "in_scheduled_downtime": False,
            "attempt": 0,
            "state_type_id": 1,
            "acknowledgement_type": 1,
            "last_state_change": 1444427108.040841,
            "last_time_down": 1444427108,
            "instance_id": 0,
            "long_output": "",
            "current_problem_id": 0,
            "check_interval": 5,
            "state_id": 2,
            "has_been_checked": 1,
            "perf_data": "uptime=1200 rta=0.049000ms;2.000000;3.000000;0.000000 pl=0%;50;80;0"
        }
        b = Brok({'data': hcr, 'type': 'host_check_result'}, False)
        b.prepare()
        instance.manage_brok(b)
        self.show_logs()
