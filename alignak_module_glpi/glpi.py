#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    David Durieux, d.durieux@siprossii
#    Frederic Mohier, frederic.mohier@gmail.com
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.


# This Class is a plugin for the Shinken Broker. It is in charge
# to brok information into the glpi database. for the moment
# only Mysql is supported. This code is __imported__ from Broker.
# The managed_brok function is called by Broker for manage the broks. It calls
# the manage_*_brok functions that create queries, and then run queries.


"""
This Class is a plugin for the Shinken/Alignak Broker. It connects to a Glpi Mysql / MariaDB
database to update hosts and services status when broks are received
"""
import time
import queue
import datetime
import logging
import traceback

from collections import deque

import mysql.connector

from alignak.basemodule import BaseModule

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
for handler in logger.parent.handlers:
    if isinstance(handler, logging.StreamHandler):
        logger.parent.removeHandler(handler)

properties = {
    'daemons': ['broker'],
    'type': 'database',
    'phases': ['running'],

    'external': True
}


def get_instance(mod_conf):
    """
    Return a module instance for the modules manager

    :param mod_conf: the module properties as defined globally in this file
    :return:
    """
    # logger.info("Get a glpidb data module for plugin %s" % plugin.get_name())
    return Glpidb_broker(mod_conf)


class Glpidb_broker(BaseModule):
    """
    Class for the Glpi DB Broker module
    Get broks and puts them in the GLPI database
    """

    def __init__(self, mod_conf):
        """
        Module initialization

        mod_conf is a dictionary that contains:
        - all the variables declared in the module configuration file
        - a 'properties' value that is the module properties as defined globally in this file

        :param mod_conf: module configuration file as a dictionary
        """
        BaseModule.__init__(self, mod_conf)

        # pylint: disable=global-statement
        global logger
        logger = logging.getLogger('alignak.module.%s' % self.alias)
        if getattr(mod_conf, 'log_level', logging.INFO) in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            logger.setLevel(getattr(mod_conf, 'log_level'))

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)

        self.schedulers = {}
        self.hosts_cache = {}
        self.services_cache = {}

        # Database configuration
        self.fake_db = bool(getattr(mod_conf, 'fake_db', '0') == '1')
        self.host = getattr(mod_conf, 'host', '127.0.0.1')
        self.port = int(getattr(mod_conf, 'port', '3306'))
        self.user = getattr(mod_conf, 'user', 'alignak')
        self.password = getattr(mod_conf, 'password', 'alignak')
        self.database = getattr(mod_conf, 'database', 'glpi')
        self.character_set = getattr(mod_conf, 'character_set', 'utf8')
        logger.info("using '%s' database on %s:%d (user = %s)",
                    self.database, self.host, self.port, self.user)

        # Data update source information
        self.source = getattr(mod_conf, 'source', 'alignak')
        # Allow to create missing data rows in the Glpi database for hosts and services
        self.create_data = bool(getattr(mod_conf, 'create_data', '1') == '1')

        # service name to use for an host check result
        self.hostcheck = getattr(mod_conf, 'host_check', 'hostcheck')

        # Database tables update configuration
        self.hosts_table = getattr(mod_conf, 'hosts_table',
                                   'glpi_plugin_monitoring_hosts')
        self.update_hosts = bool(getattr(mod_conf, 'update_hosts', '0') == '1')
        logger.info("updating hosts states (%s): %s",
                    self.hosts_table, self.update_hosts)
        self.select_hosts_query = None
        self.update_hosts_query = None
        self.insert_hosts_query = None

        self.update_services = bool(getattr(mod_conf, 'update_services', '0') == '1')
        self.services_table = getattr(mod_conf, 'services_table',
                                      'glpi_plugin_monitoring_services')
        logger.info("updating services states (%s): %s",
                    self.services_table, self.update_services)
        self.select_services_query = None
        self.update_services_query = None
        self.insert_services_query = None

        self.update_services_events = bool(getattr(mod_conf, 'update_services_events', '0') == '1')
        self.serviceevents_table = getattr(mod_conf, 'serviceevents_table',
                                           'glpi_plugin_monitoring_serviceevents')
        logger.info("updating services events (%s): %s",
                    self.serviceevents_table, self.update_services_events)
        self.insert_services_events_query = None

        self.update_records = bool(getattr(mod_conf, 'update_records', '0') == '1')
        self.records_table = getattr(mod_conf, 'records_table', 'glpi_plugin_monitoring_records')
        self.records_services = getattr(mod_conf, 'records_services', '')
        self.records_services = self.records_services.split(',')
        if self.records_services and not self.records_services[0]:
            self.records_services = []
        logger.info("updating records (%s): %s, services: %s",
                    self.records_table, self.update_records, self.records_services)
        self.insert_records_query = None

        self.db = None
        self.db_cursor = None
        self.db_cursor_many = None
        self.is_connected = False

        self.events_cache = deque()

        self.commit_period = int(getattr(mod_conf, 'commit_period', '60'))
        self.commit_volume = int(getattr(mod_conf, 'commit_volume', '1000'))
        self.db_test_period = int(getattr(mod_conf, 'db_test_period', '0'))
        logger.info('periodical commit period: %ds', self.commit_period)
        logger.info('periodical commit volume: %d lines', self.commit_volume)
        logger.info('periodical DB connection test period: %ds', self.db_test_period)

    def init(self):
        """Module initialization
        Open database connection and check tables structure"""
        if self.open():
            self.check_database()
        logger.info("initialized")
        return True

    def do_loop_turn(self):
        """This function is called/used when you need a module with
        a loop function (and use the parameter 'external': True)
        """
        logger.info("In loop")
        time.sleep(1)

    def open(self, force=False):
        """
        Connect to the MySQL DB.
        """
        if self.is_connected and not force:
            logger.info("request to open but connection is still established")
            return self.is_connected

        try:
            logger.info("connecting to database %s on %s...", self.database, self.host)
            if not self.fake_db:
                self.db = mysql.connector.connect(host=self.host, port=self.port,
                                                  database=self.database,
                                                  user=self.user, passwd=self.password)

                self.db.set_charset_collation(self.character_set)
                self.db_cursor = self.db.cursor()
                self.db_cursor_many = self.db.cursor(prepared=True)
                logger.info('server information: %s, version: %s',
                            self.db.get_server_info(), self.db.get_server_version())

            logger.info("connected")
            self.is_connected = True
        except Exception as e:
            logger.error("database connection error: %s", str(e))
            self.is_connected = False

        return self.is_connected

    def close(self):
        """Close the DB connection and release the default cursor"""
        if self.is_connected:
            self.is_connected = False
            self.db_cursor.close()
            self.db_cursor_many.close()
            self.db.close()
            self.db = None
            logger.info('database connection closed')

    def check_database(self):
        """Check the connected database main tables structure to confirm that update is possible"""
        if self.fake_db:
            if self.update_hosts:
                logger.info("updating hosts states is enabled")
            if self.update_services:
                logger.info("updating services states is enabled")
            if self.update_services_events:
                logger.info("updating services events is enabled")
            return

        try:
            count = 0
            self.db_cursor.execute("SHOW COLUMNS FROM %s" % self.hosts_table)
            columns = self.db_cursor.fetchall()
            logger.debug("Hosts table, got: ")
            for column in columns:
                if column[0] in ['entities_id', 'itemtype', 'items_id', 'state', 'state_type',
                                 'last_check', 'output', 'perf_data', 'latency', 'execution_time',
                                 'is_acknowledged']:
                    count += 1
                logger.debug('-: %s', column)
            logger.debug("-> %d columns", count)
            if self.update_hosts and count < 11:
                self.update_hosts = False
                logger.warning("updating hosts state is not possible because of DB structure")
        except Exception as exp:
            logger.warning("Hosts table columns request, error: %s", exp)
            self.update_hosts = False
            logger.warning("updating hosts state is not possible because of DB structure")

        if self.update_hosts:
            logger.info("updating hosts states is enabled")

        try:
            count = 0
            self.db_cursor.execute('SHOW COLUMNS FROM %s' % self.services_table)
            columns = self.db_cursor.fetchall()
            logger.debug("Services table, got: ")
            for column in columns:
                if column[0] in ['id', 'entities_id', 'state', 'state_type', 'last_check', 'output',
                                 'perf_data', 'latency', 'execution_time', 'is_acknowledged']:
                    count += 1
                logger.debug('-: %s', column)
            logger.debug("-> %d columns", count)
            if self.update_services and count < 7:
                self.update_services = False
                logger.warning("updating services state is not possible because of DB structure")
        except Exception as exp:
            logger.warning("Services table columns request, error: %s", exp)
            self.update_hosts = False
            logger.warning("updating services state is not possible because of DB structure")

        if self.update_services:
            logger.info("updating services states is enabled")

        try:
            count = 0
            self.db_cursor.execute('SHOW COLUMNS FROM %s' % self.serviceevents_table)
            columns = self.db_cursor.fetchall()
            logger.debug("Services events table, got: ")
            for column in columns:
                if column[0] in ['plugin_monitoring_services_id', 'date',
                                 'state_id', 'state_type_id', 'last_state_id', 'last_hard_state_id',
                                 'state', 'state_type', 'output', 'perf_data']:
                    count += 1
                logger.debug('-: %s', column)
            logger.debug("-> %d columns", count)
            if self.update_services_events and count < 10:
                self.update_services_events = False
                logger.warning("updating services events is not possible because of DB structure")
        except Exception as exp:
            logger.warning("Services events table columns request, error: %s", exp)
            self.update_hosts = False
            logger.warning("updating services events is not possible because of DB structure")

        if self.update_services_events:
            logger.info("updating services events is enabled")

    def create_select_query(self, table, data, where_data):
        """Create a select query for a table with provided data, and use where data for
        the WHERE clause
        """
        fields = [u"`%s`" % (prop) for prop in data]
        where = [u"`%s`=%%(%s)s" % (prop, prop) for prop in where_data]
        query = u"SELECT %s FROM `%s`" % (', '.join(fields), table)
        if where:
            query = query + u" WHERE " + ' AND '.join(where)
        else:
            query = query + u" WHERE 1"
        logger.info("Created a select query: %s", query)
        return query

    def create_insert_query(self, table, data):
        """Create an INSERT query for the table with the provided data
        """
        fields = [u"`%s`" % (prop) for prop in data]
        values = [u"%%(%s)s" % (prop) for prop in data]
        query = u"INSERT INTO `%s` (%s) VALUES (%s)" % (table, ', '.join(fields), ', '.join(values))
        logger.info("Created an insert query: %s", query)
        return query

    def create_update_query(self, table, data, where_data):
        """Create an update query for a table with provided data, and use where data for
        the WHERE clause
        """
        fields = [u"`%s`=%%(%s)s" % (prop, prop) for prop in data if prop not in where_data]
        where = [u"`%s`=%%(%s)s" % (prop, prop) for prop in where_data]
        query = u"UPDATE `%s` SET %s" % (table, ', '.join(fields))
        if where:
            query = query + u" WHERE " + ' AND '.join(where)
        logger.info("Created an update query: %s", query)
        return query

    def execute_query(self, query, data=None):  # pylint: disable=too-many-return-statements
        """Just run the query with the provided parameters
        """
        if self.fake_db:
            return 0

        if not self.is_connected:
            logger.info("Not connected - should have run query: %s with: %s", query, data)
            return -1

        if data is not None:
            logger.debug("Running query : %s with: %s", query, data)
        else:
            logger.debug("Running query : %s", query)

        try:
            if data:
                self.db_cursor.execute(query, data)
            else:
                self.db_cursor.execute(query)

            if 'SELECT' in self.db_cursor.statement:
                logger.debug("Ran: %s", self.db_cursor.statement)
                rows = self.db_cursor.fetchall()
                logger.debug("Got %d rows", len(rows))
                return len(rows)

            self.db.commit()
            logger.debug("Cursor: %s / %s", type(self.db_cursor), self.db_cursor.__dict__)

            if 'INSERT' in self.db_cursor.statement:
                logger.debug("Inserted %d rows", self.db_cursor.rowcount)
                return self.db_cursor.rowcount
            if 'UPDATE' in self.db_cursor.statement:
                logger.debug("Updated %d rows", self.db_cursor.rowcount)
                return self.db_cursor.rowcount

            return 0
        except Exception as exp:
            logger.warning("A query raised an error: %s, error: %s, data: %s", query, exp, data)
            self.db.rollback()
            return -1

    def fetchone(self):
        """Just get an entry"""
        return self.db_cursor.fetchone()

    def fetchall(self):
        """Get all entry"""
        return self.db_cursor.fetchall()

    def bulk_insert(self):
        """
        Periodically called (commit_period), this method prepares a bunch of queued
        insertions (max. commit_volume) to insert them in the DB.
        """
        logger.debug("bulk insertion ... %d events in cache (max insertion is %d lines)",
                     len(self.events_cache), self.commit_volume)

        if not self.events_cache:
            logger.debug("bulk insertion ... nothing to insert.")
            return

        if not self.is_connected:
            if not self.open():
                logger.warning("database is not connected and connection failed")
                logger.warning("%d events to insert in database", len(self.events_cache))
                return

        logger.info("%d lines to insert in database (maximum is %d)",
                    len(self.events_cache), self.commit_volume)

        now = time.time()

        if not self.insert_services_events_query:
            an_event = self.events_cache[0]
            fields = [u"`%s`" % (prop) for prop in an_event]
            values = [u"%s" for prop in an_event]
            self.insert_services_events_query = u"INSERT INTO `%s` (%s) VALUES (%s)" % (
                self.serviceevents_table, ', '.join(fields), ', '.join(values))
            logger.info("Created an insert query: %s", self.insert_services_events_query)

        # Flush all the stored log lines
        some_events = []

        try:
            while True:
                try:
                    event = self.events_cache.popleft()
                    some_events.append(event.values())
                    if len(some_events) >= self.commit_volume:
                        break
                except IndexError:
                    logger.debug("prepared all available events for commit")
                    break

            if some_events:
                logger.debug("Events, %d rows to insert", len(some_events))

                self.db_cursor_many.executemany(self.insert_services_events_query, some_events)
                self.db.commit()
                logger.info("Inserted %d rows (%2.4f seconds)",
                            self.db_cursor_many.rowcount, time.time() - now)
        except Exception as exp:
            logger.warning("Exception: %s / %s / %s", type(exp), str(exp), traceback.print_exc())
            logger.error("error '%s' when executing query: %s", exp, some_events)

    def manage_brok(self, brok):
        """Got a brok, manage only the interesting broks"""
        logger.debug("Got a brok: %s", brok)

        # Not used currently - may be used to update Alignak status in the DB!
        # if b.type == 'program_status':
        #     """Alignak framework start"""
        #     self.manage_program_status_brok(b)

        # Not used currently - may be used to update Alignak status in the DB!
        # if b.type == 'update_program_status':
        #     """Alignak framework status update"""
        #     self.manage_update_program_status_brok(b)

        # Build initial host state cache
        if brok.type == 'initial_host_status':
            # Prepare the known hosts cache
            host_name = brok.data['host_name']
            logger.debug("got initial host status: %s", host_name)

            self.hosts_cache[host_name] = {
                'realm_name': brok.data.get('realm_name', brok.data.get('realm', 'All'))
            }

            try:
                # Data used for DB updates
                logger.debug("initial host status: %s : %s", host_name, brok.data['customs'])
                cached_item = True
                self.hosts_cache[host_name].update({
                    'hostsid': brok.data['customs']['_HOSTSID'],
                    'itemtype': brok.data['customs']['_ITEMTYPE'],
                    'items_id': brok.data['customs']['_ITEMSID']
                })
            except Exception:
                cached_item = False
                self.hosts_cache[host_name].update({'items_id': None})
                logger.debug("no custom _HOSTID and/or _ITEMTYPE and/or _ITEMSID for %s",
                             host_name)

            if self.update_hosts or self.update_services_events:
                start = time.time()
                self.record_host_check_result(brok, cached_item, True)
                logger.debug("host check result: %s, (%2.4f seconds)",
                             host_name, time.time() - start)

            logger.info("initial host status: %s, items_id=%s", host_name,
                        self.hosts_cache[host_name]['items_id'])

        # Build initial service state cache
        if brok.type == 'initial_service_status':
            # Prepare the known services cache
            host_name = brok.data['host_name']
            service_description = brok.data['service_description']
            service_id = host_name + "/" + service_description
            logger.debug("got initial service status: %s", service_id)

            if host_name not in self.hosts_cache:
                logger.error("initial service status, host is unknown: %s.", service_id)
                return

            try:
                logger.debug("initial service status: %s : %s", service_id, brok.data['customs'])
                cached_item = True
                self.services_cache[service_id] = {
                    'items_id': brok.data['customs']['_ITEMSID']
                }
            except Exception:
                cached_item = False
                self.services_cache[service_id] = {'items_id': None}
                logger.debug("no custom _ITEMTYPE and/or _ITEMSID for %s", service_id)

            if self.update_services or self.update_services_events:
                start = time.time()
                self.record_service_check_result(brok, cached_item, True)
                logger.debug("service check result: %s, (%2.4f seconds)",
                             service_id, time.time() - start)

            logger.info("initial service status: %s, items_id=%s",
                        service_id, self.services_cache[service_id]['items_id'])

        # Manage host check result if host is defined in Glpi DB
        if brok.type == 'host_check_result' and \
                (self.update_hosts or self.update_services_events):
            host_name = brok.data['host_name']
            logger.debug("host check result: %s", host_name)

            if host_name not in self.hosts_cache:
                logger.debug("got a host check result for an unknown host: %s", host_name)
                return

            cached_item = True
            if self.hosts_cache[host_name]['items_id'] is None:
                logger.debug("unknown DB information for the host: %s", host_name)
                cached_item = False

            start = time.time()
            self.record_host_check_result(brok, cached_item)
            logger.debug("host check result: %s, (%2.4f seconds)",
                         host_name, time.time() - start)

        # Manage service check result if service is defined in Glpi DB
        if brok.type == 'service_check_result' and \
                (self.update_services or self.update_services_events):
            host_name = brok.data['host_name']
            service_description = brok.data['service_description']
            service_id = host_name + "/" + service_description
            logger.debug("service check result: %s", service_id)

            if host_name not in self.hosts_cache:
                logger.debug("service check result for an unknown host: %s", service_id)
                return

            cached_item = True
            if self.hosts_cache[host_name]['items_id'] is None:
                logger.debug("unknown DB information for the host: %s", host_name)
                cached_item = False

            if self.services_cache[service_id]['items_id'] is None:
                logger.debug("unknown DB information for the service: %s", service_id)
                cached_item = False

            start = time.time()
            self.record_service_check_result(brok, cached_item)
            logger.debug("service check result: %s, (%2.4f seconds)",
                         service_id, time.time() - start)

    def record_host_check_result(self, b, cached_item, initial_status=False):
        """Record an host check result"""
        host_name = b.data['host_name']
        host_cache = self.hosts_cache[host_name]
        logger.debug("record host check result: %s: %s", host_name, b.data)

        # Insert into serviceevents log table
        if self.update_services_events and not initial_status:
            # SQL table is: CREATE TABLE IF NOT EXISTS `glpi_plugin_monitoring_serviceevents` (
            #   `id` bigint(30) NOT NULL AUTO_INCREMENT,
            #   `host_name` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
            #   `service_description` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT
            # 'not_set',
            #   `plugin_monitoring_services_id` int(11) NOT NULL DEFAULT '-1',
            #   `date` datetime DEFAULT NULL,
            #   `state` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            #   `state_type` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            #   `state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `state_type_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `last_state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `last_hard_state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `output` text COLLATE utf8_unicode_ci DEFAULT NULL,
            #   `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
            #   `unavailability` tinyint(1) NOT NULL DEFAULT '0',
            #   PRIMARY KEY (`id`),
            #   KEY `plugin_monitoring_services_id` (`plugin_monitoring_services_id`),
            #   KEY `plugin_monitoring_services_id_2` (`plugin_monitoring_services_id`,`date`),
            #   KEY `plugin_monitoring_services_id_3` (`plugin_monitoring_services_id`,`id`),
            #   KEY `service` (`host_name`(50),`service_description`(50)),
            #   KEY `unavailability` (`unavailability`,`state_type`,`plugin_monitoring_services_id`)
            # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
            logger.debug("append data to events_cache for host check: %s", host_name)
            data = {
                'host_name': b.data['host_name'],
                'service_description': self.hostcheck,
                'date': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                    '%Y-%m-%d %H:%M:%S'),
                'output': ("%s\n%s", b.data['output'], b.data['long_output']) if (
                    b.data['long_output']) else b.data['output'],
                'perf_data': b.data['perf_data'],
                # Use 4 (unknown usual code) if value does not exist in the brok
                'state_id': b.data.get('state_id', 4),
                'state_type_id': b.data.get('state_type_id', 4),
                'last_state_id': b.data.get('last_state_id', 4),
                'last_hard_state_id': b.data.get('last_hard_state_id', 4),
            }
            # if cached_item:
            #     data['plugin_monitoring_services_id'] = host_cache['items_id']

            # Append to bulk insert queue ...
            self.events_cache.append(data)

        # Update hosts state table
        if not self.update_hosts:
            return

        # SQL table is: CREATE TABLE IF NOT EXISTS `glpi_plugin_monitoring_hosts` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `entities_id` int(11) NOT NULL DEFAULT '0',
        #   `itemtype` varchar(100) DEFAULT NULL,
        #   `items_id` int(11) NOT NULL DEFAULT '0',
        #   `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
        #   `host_name` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
        #   `state` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `state_type` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `last_check` datetime DEFAULT NULL,
        #   `output` text COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `latency` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `execution_time` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `dependencies` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `is_acknowledged` tinyint(1) NOT NULL DEFAULT '0',
        #   `is_acknowledgeconfirmed` tinyint(1) NOT NULL DEFAULT '0',
        #   `acknowledge_comment` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `acknowledge_users_id` int(11) NOT NULL DEFAULT '0',
        #   PRIMARY KEY (`id`),
        #   KEY `itemtype` (`itemtype`,`items_id`)
        # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
        data = {
            'host_name': b.data['host_name'],

            'last_check': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'source': self.source,
            'state': b.data['state'],
            'state_type': b.data['state_type'],
            'output': "%s\n%s" % (b.data['output'], b.data['long_output']) if (
                b.data['long_output']) else b.data['output'],
            'perf_data': b.data['perf_data'],
            'latency': b.data['latency'],
            'execution_time': b.data['execution_time'],
            'is_acknowledged': '1' if b.data['problem_has_been_acknowledged'] else '0'
        }

        if not self.update_hosts_query:
            where_clause = {
                'host_name': b.data['host_name']
            }
            self.update_hosts_query = self.create_update_query(self.hosts_table,
                                                               data, where_clause)

        updated = False
        try:
            rows_affected = self.execute_query(self.update_hosts_query, data)
            if rows_affected:
                updated = True
        except Exception as exp:
            logger.error("error '%s', query: %s, data: %s", exp, self.update_hosts_query, data)

        if not updated and self.create_data and initial_status:
            try:
                # Create a new row in the database
                if not self.select_hosts_query:
                    self.select_hosts_query = self.create_select_query(
                        self.hosts_table, data, where_clause)
                if not self.insert_hosts_query:
                    self.insert_hosts_query = self.create_insert_query(self.hosts_table, data)

                if not self.execute_query(self.select_hosts_query, data):
                    self.execute_query(self.insert_hosts_query, data)
                    updated = True
                    logger.warning("Created a new host status row for %s with data: %s",
                                   host_name, data)
            except Exception as exp:
                logger.error("error '%s' when executing a query: %s with data: %s",
                             exp, self.update_hosts_query, data)

        if not updated:
            logger.warning("DB host status update failed for %s with data: %s",
                           host_name, data)

    def record_service_check_result(self, b, cached_item, initial_status=False):
        """Record a service check result"""
        host_name = b.data['host_name']
        service_description = b.data['service_description']
        service_id = host_name + "/" + service_description
        service_cache = self.services_cache[service_id]
        logger.debug("service check result: %s: %s", service_id, b.data)

        # Insert into serviceevents log table
        if self.update_services_events and not initial_status:
            # SQL table is: CREATE TABLE IF NOT EXISTS `glpi_plugin_monitoring_serviceevents` (
            #   `id` bigint(30) NOT NULL AUTO_INCREMENT,
            #   `host_name` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
            #   `service_description` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT
            # 'not_set',
            #   `plugin_monitoring_services_id` int(11) NOT NULL DEFAULT '-1',
            #   `date` datetime DEFAULT NULL,
            #   `state` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            #   `state_type` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            #   `state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `state_type_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `last_state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `last_hard_state_id` tinyint(1) NOT NULL DEFAULT '0',
            #   `output` text COLLATE utf8_unicode_ci DEFAULT NULL,
            #   `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
            #   `unavailability` tinyint(1) NOT NULL DEFAULT '0',
            #   PRIMARY KEY (`id`),
            #   KEY `plugin_monitoring_services_id` (`plugin_monitoring_services_id`),
            #   KEY `plugin_monitoring_services_id_2` (`plugin_monitoring_services_id`,`date`),
            #   KEY `plugin_monitoring_services_id_3` (`plugin_monitoring_services_id`,`id`),
            #   KEY `service` (`host_name`(50),`service_description`(50)),
            #   KEY `unavailability` (`unavailability`,`state_type`,`plugin_monitoring_services_id`)
            # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
            logger.debug("append data to events_cache for service: %s", service_id)
            data = {
                'host_name': b.data['host_name'],
                'service_description': b.data['service_description'],
                'date': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                    '%Y-%m-%d %H:%M:%S'),
                'output': ("%s\n%s", b.data['output'], b.data['long_output']) if (
                    b.data['long_output']) else b.data['output'],
                'perf_data': b.data['perf_data'],
                # Use 4 (unknown usual code) if value does not exist in the brok
                'state_id': b.data.get('state_id', 4),
                'state_type_id': b.data.get('state_type_id', 4),
                'last_state_id': b.data.get('last_state_id', 4),
                'last_hard_state_id': b.data.get('last_hard_state_id', 4),
            }
            # if cached_item:
            #     data['plugin_monitoring_services_id'] = service_cache['items_id']

            # Append to bulk insert queue ...
            self.events_cache.append(data)

        # Record performance data for specific services
        if self.update_records and service_description in self.records_services:
            data = {
                'host_name': b.data['host_name'],
                'service_description': b.data['service_description'],

                'last_check': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                    '%Y-%m-%d %H:%M:%S'),
                'source': self.source,
                'output': "%s\n%s" % (b.data['output'], b.data['long_output']) if (
                    b.data['long_output']) else b.data['output'],
                'perf_data': b.data['perf_data']
            }
            if not self.insert_records_query:
                self.insert_records_query = self.create_insert_query(self.records_table, data)

            try:
                rows_affected = self.execute_query(self.insert_records_query, data)
                if rows_affected:
                    logger.info("Created a new record for %s with data: %s", service_id, data)
            except Exception as exp:
                logger.error("error '%s', query: %s, data: %s", exp, self.update_services_query,
                             data)

        # Update service state table
        if not self.update_services:
            return

        # SQL table is: CREATE TABLE IF NOT EXISTS `glpi_plugin_monitoring_services` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `entities_id` int(11) NOT NULL DEFAULT '0',
        #   `host_name` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
        #   `service_description` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'not_set',
        #   `plugin_monitoring_components_id` int(11) NOT NULL DEFAULT '0',
        #   `plugin_monitoring_componentscatalogs_hosts_id` int(11) NOT NULL DEFAULT '0',
        #   `state` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `state_type` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `last_check` datetime DEFAULT NULL,
        #   `latency` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `execution_time` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `output` text COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `arguments` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `networkports_id` int(11) NOT NULL DEFAULT '0',
        #   `is_acknowledged` tinyint(1) NOT NULL DEFAULT '0',
        #   `is_acknowledgeconfirmed` tinyint(1) NOT NULL DEFAULT '0',
        #   `acknowledge_comment` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `acknowledge_users_id` int(11) NOT NULL DEFAULT '0',
        #   PRIMARY KEY (`id`),
        #   KEY `service` (`host_name`(50),`service_description`(50)),
        #   KEY `state` (`state`(50),`state_type`(50)),
        #   KEY `plugin_monitoring_componentscatalogs_hosts_id`
        # (`plugin_monitoring_componentscatalogs_hosts_id`),
        #   KEY `last_check` (`last_check`)
        # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
        data = {
            'host_name': b.data['host_name'],
            'service_description': b.data['service_description'],

            'last_check': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'source': self.source,
            'state': b.data['state'],
            'state_type': b.data['state_type'],
            'output': "%s\n%s" % (b.data['output'], b.data['long_output']) if (
                b.data['long_output']) else b.data['output'],
            'perf_data': b.data['perf_data'],
            'latency': b.data['latency'],
            'execution_time': b.data['execution_time'],
            'is_acknowledged': '1' if b.data['problem_has_been_acknowledged'] else '0'
        }

        if not self.update_services_query:
            where_clause = {
                'host_name': b.data['host_name'],
                'service_description': b.data['service_description']
            }
            self.update_services_query = self.create_update_query(self.services_table,
                                                                  data, where_clause)

        updated = False
        try:
            rows_affected = self.execute_query(self.update_services_query, data)
            if rows_affected:
                updated = True
        except Exception as exp:
            logger.error("error '%s', query: %s, data: %s", exp, self.update_services_query, data)

        if not updated and self.create_data and initial_status:
            try:
                # Create a new row in the database
                if not self.select_services_query:
                    self.select_services_query = self.create_select_query(
                        self.services_table, data, where_clause)
                if not self.insert_services_query:
                    self.insert_services_query = self.create_insert_query(self.services_table, data)

                updated = True
                if not self.execute_query(self.select_services_query, data):
                    self.execute_query(self.insert_services_query, data)
                    logger.warning("Created a new service status row for %s with data: %s",
                                   service_id, data)
            except Exception as exp:
                logger.error("error '%s' when executing a query: %s with data: %s",
                             exp, self.update_services_query, data)

        if not updated:
            logger.warning("DB service status update failed for %s with data: %s",
                           service_id, data)

    def manage_program_status_brok(self, b):
        """A scheduler provides its initial status

        Shinken brok contains:
        data = {"is_running": 1,
                "instance_id": self.instance_id,
                "instance_name": self.instance_name,
                "last_alive": now,
                "interval_length": self.conf.interval_length,
                "program_start": self.program_start,
                "pid": os.getpid(),
                "daemon_mode": 1,
                "last_command_check": now,
                "last_log_rotation": now,
                "notifications_enabled": self.conf.enable_notifications,
                "active_service_checks_enabled": self.conf.execute_service_checks,
                "passive_service_checks_enabled": self.conf.accept_passive_service_checks,
                "active_host_checks_enabled": self.conf.execute_host_checks,
                "passive_host_checks_enabled": self.conf.accept_passive_host_checks,
                "event_handlers_enabled": self.conf.enable_event_handlers,
                "flap_detection_enabled": self.conf.enable_flap_detection,
                "failure_prediction_enabled": 0,
                "process_performance_data": self.conf.process_performance_data,
                "obsess_over_hosts": self.conf.obsess_over_hosts,
                "obsess_over_services": self.conf.obsess_over_services,
                "modified_host_attributes": 0,
                "modified_service_attributes": 0,
                "global_host_event_handler": self.conf.global_host_event_handler,
                'global_service_event_handler': self.conf.global_service_event_handler,
                'check_external_commands': self.conf.check_external_commands,
                'check_service_freshness': self.conf.check_service_freshness,
                'check_host_freshness': self.conf.check_host_freshness,
                'command_file': self.conf.command_file
                }
        Note that some parameters values are hard-coded and useless ... and some configuration
        parameters are missing!

        Alignak brok contains many more information:
        _config: all the more interesting configuration parameters
        are pushed in the program status brok sent by each scheduler. At minimum, the UI will
        receive all the framework configuration parameters.
        _running: all the running scheduler information: checks count, results, live synthesis
        _macros: the configure Alignak macros and their value

        """
        data = b.data
        c_id = data['instance_id']
        c_name = data.get('instance_name', c_id)
        logger.info("Got a configuration from %s", c_name)
        logger.debug("Data: %s", data)

        now = time.time()
        if c_id in self.schedulers:
            # It may happen that the same scheduler sends several times its initial status brok.
            # Let's manage this and only consider one brok per minute!
            # We already have a configuration for this scheduler instance
            if now - self.schedulers[c_id]['_timestamp'] < 60:
                logger.info("Got near initial program status for %s. "
                            "Ignoring this information.", c_name)
                return

        # And we save the data in the configurations
        data['_timestamp'] = now

        # Shinken renames some "standard" parameters, restore the common name...
        if 'notifications_enabled' in data:
            data['enable_notifications'] = data.pop('notifications_enabled')
        if 'event_handlers_enabled' in data:
            data['enable_event_handlers'] = data.pop('event_handlers_enabled')
        if 'flap_detection_enabled' in data:
            data['enable_flap_detection'] = data.pop('flap_detection_enabled')
        if 'active_service_checks_enabled' in data:
            data['execute_service_checks'] = data.pop('active_service_checks_enabled')
        if 'active_host_checks_enabled' in data:
            data['execute_host_checks'] = data.pop('active_host_checks_enabled')
        if 'passive_service_checks_enabled' in data:
            data['accept_passive_service_checks'] = data.pop('passive_service_checks_enabled')
        if 'passive_host_checks_enabled' in data:
            data['accept_passive_host_checks'] = data.pop('passive_host_checks_enabled')

        self.schedulers[c_id] = data

    def manage_update_program_status_brok(self, b):
        """Each scheduler sends us a "I'm alive" brok.

        Brok data:
        u'instance_name': u'scheduler-master scheduler',
        u'pid': 25300, u'is_running': True,
        u'instance_id': u'SchedulerLink_3',
        u'last_alive': 1551361304.589299
        u'_config': {
            u'log_snapshots': True, u'accept_passive_service_checks': True,
            ......
            u'retention_update_interval': 5},
        u'_running': {
            u'latency': {u'max': 0.0, u'avg': 0.0, u'min': 0.0},
            u'_freshness': 1551361304, u'commands': {}, u'problems': {},
            u'monitored_objects': {
                u'servicesextinfo': 0, u'modules': 0,
                u'hostgroups': 23, u'escalations': 0,
                u'hostescalations': 0, u'schedulers': 0,
                u'hostsextinfo': 0, u'contacts': 8,
                u'servicedependencies': 0,
                u'resultmodulations': 0, u'hosts': 0,
                u'pollers': 0, u'arbiters': 0, u'receivers': 0,
                u'macromodulations': 0, u'reactionners': 0,
                u'contactgroups': 3, u'brokers': 0,
                u'realms': 0, u'services': 0, u'commands': 133,
                u'notificationways': 10,
                u'serviceescalations': 0, u'timeperiods': 2,
                u'businessimpactmodulations': 0,
                u'checkmodulations': 0, u'servicegroups': 17,
                u'hostdependencies': 0
            },
            u'livesynthesis': {
                u'services_not_monitored': 0,
                u'services_acknowledged': 0,
                u'services_unreachable_soft': 0,
                u'hosts_up_soft': 0, u'services_warning_hard': 0,
                u'services_flapping': 0, u'hosts_down_soft': 0,
                u'services_warning_soft': 0,
                u'hosts_acknowledged': 0,
                u'hosts_not_monitored': 0, u'hosts_down_hard': 0,
                u'hosts_flapping': 0, u'services_total': 0,
                u'hosts_in_downtime': 0, u'hosts_problems': 0,
                u'services_unreachable_hard': 0,
                u'services_ok_hard': 0,
                u'hosts_unreachable_hard': 0,
                u'services_problems': 0,
                u'services_critical_soft': 0,
                u'hosts_unreachable_soft': 0,
                u'services_critical_hard': 0, u'hosts_up_hard': 0,
                u'hosts_total': 0, u'services_unknown_soft': 0,
                u'services_ok_soft': 0,
                u'services_in_downtime': 0},
                u'services_unknown_hard': 0,
                u'counters': {
                    u'checks.scheduled': 0, u'actions.in_poller': 0,
                    u'actions.scheduled': 0, u'checks.zombie': 0,
                    u'checks.count': 0, u'actions.zombie': 0,
                    u'actions.count': 0, u'checks.in_poller': 0
                }
            },
            u'_macros': {
                u'PLUGINSDIR': u'/home/fred/IPM_FDJ/commands',
                ......
            },

        """
        data = b.data
        c_id = data['instance_id']
        c_name = data.get('instance_name', c_id)
        logger.debug("Got a scheduler update status from %s", c_name)
        logger.debug("Data: %s", data)

        # Tag with the update time and store the configuration
        data['_timestamp'] = time.time()
        self.schedulers[c_id].update(data)

    def main(self):
        self.set_proctitle(self.name)
        self.set_exit_handler()

        # Open database connection
        self.open()

        db_commit_next_time = time.time()
        db_test_connection = time.time()

        while not self.interrupted:
            logger.debug("queue length: %s", self.to_q.qsize())
            start = time.time()

            # DB connection test ?
            if self.db_test_period and db_test_connection < start:
                logger.debug("Testing database connection ...")
                # Test connection every N seconds ...
                db_test_connection = start + self.db_test_period
                if self.db:
                    self.is_connected = self.db.is_connected()
                    if not self.is_connected:
                        try:
                            logger.info("Trying to reconnect database ...")
                            self.db.reconnect(attempts=3, delay=10)
                            logger.info("Succesfull database reconnection...")
                        except Exception:
                            logger.info("Database reconnection failed.")
                            pass

            # Bulk insert
            if db_commit_next_time < start:
                logger.debug("Logs commit time ...")
                # Commit periodically ...
                db_commit_next_time = start + self.commit_period
                self.bulk_insert()

            try:
                message = self.to_q.get_nowait()
                for brok in message:
                    brok.prepare()
                    self.manage_brok(brok)

                logger.debug("time to manage %d broks (%2.4f seconds)",
                             len(message), time.time() - start)
            except queue.Full:
                logger.warning("Worker control queue is full")
            except queue.Empty:
                time.sleep(0.1)
            except EOFError:
                # Broken queue ... the broker deleted the module queue
                time.sleep(1.0)
                continue
            except Exception as exp:  # pylint: disable=broad-except
                logger.error("Exception when getting master orders: %s. ", str(exp))
