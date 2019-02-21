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

import time
import queue
import datetime
import logging

import mysql.connector

# import MySQLdb
# from MySQLdb import IntegrityError
# from MySQLdb import ProgrammingError
#

from alignak.basemodule import BaseModule
# from alignak.misc.common import setproctitle, SIGNALS_TO_NAMES_DICT
# from alignak.message import Message

from collections import deque

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

        self.hosts_cache = {}
        self.services_cache = {}

        # Database configuration
        self.host = getattr(mod_conf, 'host', '127.0.0.1')
        self.port = int(getattr(mod_conf, 'port', '3306'))
        self.user = getattr(mod_conf, 'user', 'alignak')
        self.password = getattr(mod_conf, 'password', 'alignak')
        self.database = getattr(mod_conf, 'database', 'glpi')
        self.character_set = getattr(mod_conf, 'character_set', 'utf8')
        logger.info("using '%s' database on %s:%d (user = %s)",
                    self.database, self.host, self.port, self.user)

        # Database tables update configuration
        self.hosts_table = getattr(mod_conf, 'hosts_table',
                                   'glpi_plugin_monitoring_hosts')
        self.update_hosts = bool(getattr(mod_conf, 'update_hosts', '0') == '1')
        logger.info("updating hosts states (%s): %s",
                    self.hosts_table, self.update_hosts)

        self.update_services = bool(getattr(mod_conf, 'update_services', '0') == '1')
        self.services_table = getattr(mod_conf, 'services_table',
                                      'glpi_plugin_monitoring_services')
        logger.info("updating services states (%s): %s",
                    self.services_table, self.update_services)

        self.update_services_events = bool(getattr(mod_conf, 'update_services_events', '0') == '1')
        self.serviceevents_table = getattr(mod_conf, 'serviceevents_table',
                                           'glpi_plugin_monitoring_serviceevents')
        logger.info("updating services events (%s): %s",
                    self.serviceevents_table, self.update_services_events)

        self.db = None
        self.db_cursor = None
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
            self.db = mysql.connector.connect(
                host=self.host, port=self.port, database=self.database,
                user=self.user, passwd=self.password)
            logger.info("connected")

            self.db_cursor = self.db.cursor()
            self.db_cursor.execute('SET NAMES %s;' % self.character_set)
            self.db_cursor.execute('SET CHARACTER SET %s;' % self.character_set)
            self.db_cursor.execute('SET character_set_connection=%s;' % self.character_set)

            self.is_connected = True
            logger.info('database connection configured')
        except Exception as e:
            logger.error("database connection error: %s", str(e))
            self.is_connected = False

        return self.is_connected

    def close(self):
        self.is_connected = False
        self.db_cursor.close()
        self.db.close()
        logger.info('database connection closed')

    def check_database(self):
        try:
            count = 0
            self.db_cursor.execute("SHOW COLUMNS FROM %s" % self.hosts_table)
            columns = self.db_cursor.fetchall()
            logger.debug("Hosts table, got: ")
            for column in columns:
                if column[0] in ['entities_id', 'itemtype', 'items_id', 'state', 'state_type',
                                 'last_check', 'event', 'perf_data', 'latency', 'execution_time',
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
                if column[0] in ['id', 'entities_id', 'state', 'state_type', 'last_check', 'event',
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
                if column[0] in ['plugin_monitoring_services_id', 'date', 'state', 'state_type',
                                 'last_check', 'event', 'perf_data', 'latency', 'execution_time']:
                    count += 1
                logger.debug('-: %s', column)
            logger.debug("-> %d columns", count)
            if self.update_services_events and count < 8:
                self.update_services_events = False
                logger.warning("updating services events is not possible because of DB structure")
        except Exception as exp:
            logger.warning("Services events table columns request, error: %s", exp)
            self.update_hosts = False
            logger.warning("updating services events is not possible because of DB structure")

        if self.update_services_events:
            logger.info("updating services events is enabled")

    def stringify(self, val):
        """Get a unicode from a value"""
        return "%s" % val
        # # If raw string, go in unicode
        # if isinstance(val, str):
        #     val = val.decode('utf8', 'ignore').replace("'", "''")
        # elif isinstance(val, unicode):
        #     val = val.replace("'", "''")
        # else:  # other type, we can str
        #     val = unicode(str(val))
        #     val = val.replace("'", "''")
        # return val

    def create_insert_query(self, table, data):
        """Create a INSERT query in table with all data of data (a dict)"""
        query = u"INSERT INTO %s " % (table)
        props_str = u' ('
        values_str = u' ('
        i = 0  # f or the ',' problem... look like C here...
        for prop in data:
            i += 1
            val = data[prop]
            # Boolean must be catch, because we want 0 or 1, not True or False
            if isinstance(val, bool):
                if val:
                    val = 1
                else:
                    val = 0

            # Get a string of the value
            val = self.stringify(val)

            if i == 1:
                props_str = props_str + u"%s " % prop
                values_str = values_str + u"'%s' " % val
            else:
                props_str = props_str + u", %s " % prop
                values_str = values_str + u", '%s' " % val

        # Ok we've got data, let's finish the query
        props_str = props_str + u' )'
        values_str = values_str + u' )'
        query = query + props_str + u' VALUES' + values_str
        return query

    def create_update_query(self, table, data, where_data):
        """Create a update query of table with data, and use where data for
        the WHERE clause
        """
        query = u"UPDATE %s set " % (table)

        # First data manage
        query_follow = ''
        i = 0  # for the , problem...
        for prop in data:
            # Do not need to update a property that is in where
            # it is even dangerous, will raise a warning
            if prop not in where_data:
                i += 1
                val = data[prop]
                # Boolean must be catched, because we want 0 or 1, not True or False
                if isinstance(val, bool):
                    if val:
                        val = 1
                    else:
                        val = 0

                # Get a string of the value
                val = self.stringify(val)

                if i == 1:
                    query_follow += u"%s='%s' " % (prop, val)
                else:
                    query_follow += u", %s='%s' " % (prop, val)

        # Ok for data, now WHERE, same things
        where_clause = u" WHERE "
        i = 0  # For the 'and' problem
        for prop in where_data:
            i += 1
            val = where_data[prop]
            # Boolean must be catch, because we want 0 or 1, not True or False
            if isinstance(val, bool):
                if val:
                    val = 1
                else:
                    val = 0

            # Get a string of the value
            val = self.stringify(val)

            if i == 1:
                where_clause += u"%s='%s' " % (prop, val)
            else:
                where_clause += u"and %s='%s' " % (prop, val)

        query = query + query_follow + where_clause
        return query

    def execute_query(self, query):
        """Just run the query
        """
        logger.debug("run query %s", query)
        try:
            self.db_cursor.execute(query)
            self.db.commit()
            return True
        except Exception as exp:
            logger.warning("A query raised an error: %s, error: %s", query, exp)
            return False

    def fetchone(self):
        """Just get an entry"""
        return self.db_cursor.fetchone()

    def fetchall(self):
        """Get all entry"""
        return self.db_cursor.fetchall()

    def bulk_insert(self):
        """
        Peridically called (commit_period), this method prepares a bunch of queued
        insertions (max. commit_volume) to insert them in the DB.
        """
        logger.debug("bulk insertion ... %d events in cache (max insertion is %d lines)",
                     len(self.events_cache), self.commit_volume)

        if not self.events_cache:
            logger.info("bulk insertion ... nothing to insert.")
            return

        if not self.is_connected:
            if not self.open():
                logger.warning("database is not connected and connection failed")
                logger.warning("%d events to insert in database", len(self.events_cache))
                return

        logger.info("%d lines to insert in database (max insertion is %d lines)",
                    len(self.events_cache), self.commit_volume)

        # Flush all the stored log lines
        events_to_commit = 1
        now = time.time()
        some_events = []

        # Prepare a query as:
        # INSERT INTO tbl_name (a,b,c)
        # VALUES (1,2,3), (4,5,6), (7,8,9);
        query = u"INSERT INTO `glpi_plugin_monitoring_serviceevents` "

        first = True
        while True:
            try:
                event = self.events_cache.popleft()

                if first:
                    props_str = u' ('
                    i = 0
                    for prop in event:
                        i += 1
                        if i == 1:
                            props_str = props_str + u"%s " % prop
                        else:
                            props_str = props_str + u", %s " % prop
                    props_str = props_str + u')'
                    query = query + props_str + u' VALUES'
                    first = False

                i = 0
                values_str = u' ('
                for prop in event:
                    i += 1
                    val = event[prop]
                    # Boolean must be catched, because we want 0 or 1, not True or False
                    if isinstance(val, bool):
                        if val:
                            val = 1
                        else:
                            val = 0

                    # Get a string for the value
                    val = self.stringify(val)

                    if i == 1:
                        values_str = values_str + u"'%s' " % val
                    else:
                        values_str = values_str + u", '%s' " % val
                values_str = values_str + u')'

                if events_to_commit == 1:
                    query = query + values_str
                else:
                    query = query + u"," + values_str

                events_to_commit = events_to_commit + 1
                if events_to_commit >= self.commit_volume:
                    break
            except IndexError:
                logger.debug("prepared all available events for commit")
                break
            except Exception as exp:
                logger.error("exception: %s", str(exp))
        logger.info("time to prepare %s events for commit (%2.4f)", events_to_commit - 1,
                    time.time() - now)
        logger.info("query: %s", query)

        now = time.time()
        try:
            self.execute_query(query)
        except Exception as e:
            logger.error("error '%s' when executing query: %s", e, query)
            self.close()
        logger.info("time to insert %s line (%2.4f)", events_to_commit - 1,
                    time.time() - now)

    def manage_brok(self, b):
        """Got a brok, manage only the interesting broks"""
        logger.debug("Got a brok: %s", b)

        # Build initial host state cache
        if b.type == 'initial_host_status':
            """Prepare the known hosts cache"""
            host_name = b.data['host_name']
            logger.debug("got initial host status: %s", host_name)

            self.hosts_cache[host_name] = {
                'realm_name': b.data.get('realm_name', b.data.get('realm', 'All'))
            }

            try:
                # Data used for DB updates
                logger.debug("initial host status : %s : %s", host_name, b.data['customs'])
                self.hosts_cache[host_name].update({
                    'hostsid': b.data['customs']['_HOSTSID'],
                    'itemtype': b.data['customs']['_ITEMTYPE'],
                    'items_id': b.data['customs']['_ITEMSID']
                })
            except Exception:
                self.hosts_cache[host_name].update({
                    'items_id': None
                })
                logger.debug("no custom _HOSTID and/or _ITEMTYPE and/or _ITEMSID for %s",
                             host_name)

            logger.info("initial host status : %s is %s", host_name,
                        self.hosts_cache[host_name]['items_id'])

        # Build initial service state cache
        if b.type == 'initial_service_status':
            """Prepare the known services cache"""
            host_name = b.data['host_name']
            service_description = b.data['service_description']
            service_id = host_name + "/" + service_description
            logger.debug("got initial service status: %s", service_id)

            if host_name not in self.hosts_cache:
                logger.error("initial service status, host is unknown: %s.", service_id)
                return

            try:
                logger.debug("initial service status : %s : %s", service_id,
                             b.data['customs'])
                self.services_cache[service_id] = {
                    'itemtype': b.data['customs']['_ITEMTYPE'],
                    'items_id': b.data['customs']['_ITEMSID']
                }
            except:
                self.services_cache[service_id] = {'items_id': None}
                logger.debug("no custom _ITEMTYPE and/or _ITEMSID for %s", service_id)

            logger.info("initial service status : %s is %s",
                        service_id, self.services_cache[service_id]['items_id'])

        # Manage host check result if host is defined in Glpi DB
        if b.type == 'host_check_result' and self.update_hosts:
            host_name = b.data['host_name']
            logger.debug("host check result: %s: %s", host_name)

            if host_name not in self.hosts_cache:
                logger.debug("got a host check result for an unknown host: %s", host_name)
                return

            if self.hosts_cache[host_name]['items_id'] is None:
                logger.debug("unknown DB information for the host: %s", host_name)
                return

            start = time.time()
            self.record_host_check_result(b)
            logger.debug("host check result: %s, %d seconds", host_name, time.time() - start)

        # Manage service check result if service is defined in Glpi DB
        if b.type == 'service_check_result' and \
                (self.update_services or self.update_services_events):
            host_name = b.data['host_name']
            service_description = b.data['service_description']
            service_id = host_name + "/" + service_description
            logger.debug("service check result: %s", service_id)

            if host_name in self.hosts_cache and \
                    self.hosts_cache[host_name]['items_id'] is not None:
                if service_id in self.services_cache and \
                        self.services_cache[service_id]['items_id'] is not None:
                    start = time.time()
                    self.record_service_check_result(b)
                    logger.debug("service check result: %s, %d seconds", service_id,
                                 time.time() - start)

    def record_host_check_result(self, b):
        """Record an host check result"""
        host_name = b.data['host_name']
        host_cache = self.hosts_cache[host_name]
        logger.info("record host check result: %s: %s", host_name, b.data)

        # Escape SQL fields ...
        # b.data['output'] = MySQLdb.escape_string(b.data['output'])
        # b.data['long_output'] = MySQLdb.escape_string(b.data['long_output'])
        # b.data['perf_data'] = MySQLdb.escape_string(b.data['perf_data'])

        # SQL table is: CREATE TABLE `glpi_plugin_monitoring_hosts` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `entities_id` int(11) NOT NULL DEFAULT '0',
        #   `itemtype` varchar(100) DEFAULT NULL,
        #   `items_id` int(11) NOT NULL DEFAULT '0',
        #   `event` varchar(4096) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `state` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `state_type` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `last_check` datetime DEFAULT NULL,
        #   `dependencies` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `latency` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `execution_time` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
        #   `is_acknowledged` tinyint(1) NOT NULL DEFAULT '0',
        # Following fields may be removed?
        #   `is_acknowledgeconfirmed` tinyint(1) NOT NULL DEFAULT '0',
        #   `acknowledge_comment` text DEFAULT NULL COLLATE utf8_unicode_ci,
        #   `acknowledge_users_id` int(11) NOT NULL DEFAULT '0',
        #   `backend_host_id` varchar(50) NOT NULL DEFAULT '0',
        #   `backend_host_id_auto` tinyint(1) NOT NULL DEFAULT '0',
        #   PRIMARY KEY (`id`),
        #   KEY `itemtype` (`itemtype`,`items_id`)
        # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
        data = {
            'state': b.data['state'],
            'state_type': b.data['state_type'],
            'last_check': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'event': "%s \n %s" % (b.data['output'], b.data['long_output']) if (
                    len(b.data['long_output']) > 0) else b.data['output'],
            'perf_data': b.data['perf_data'],
            'latency': b.data['latency'],
            'execution_time': b.data['execution_time'],
            'is_acknowledged': '1' if b.data['problem_has_been_acknowledged'] else '0'
        }

        where_clause = {
            'items_id': host_cache['items_id'],
            'itemtype': host_cache['itemtype']
        }
        query = self.create_update_query(self.hosts_table, data, where_clause)
        logger.debug("query: %s", query)
        try:
            self.execute_query(query)
        except Exception as exp:
            logger.error("error '%s' when executing query: %s", exp, query)

    def record_service_check_result(self, b):
        """Record a service check result"""
        host_name = b.data['host_name']
        service_description = b.data['service_description']
        service_id = host_name + "/" + service_description
        service_cache = self.services_cache[service_id]
        logger.debug("service check result: %s: %s", service_id, b.data)

        # Escape SQL fields ...
        # b.data['output'] = MySQLdb.escape_string(b.data['output'])
        # b.data['long_output'] = MySQLdb.escape_string(b.data['long_output'])
        # b.data['perf_data'] = MySQLdb.escape_string(b.data['perf_data'])

        # Insert into serviceevents log table
        if self.update_services_events:
            # SQL table is: CREATE TABLE `glpi_plugin_monitoring_serviceevents` (
            # `id` bigint(30) NOT NULL AUTO_INCREMENT,
            # `plugin_monitoring_services_id` int(11) NOT NULL DEFAULT '0',
            # `date` datetime DEFAULT NULL,
            # `event` varchar(4096) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `perf_data` text DEFAULT NULL COLLATE utf8_unicode_ci,
            # `state` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            # `state_type` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0',
            # `latency` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `execution_time` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `unavailability` tinyint(1) NOT NULL DEFAULT '0',
            # PRIMARY KEY (`id`),
            # KEY `plugin_monitoring_services_id` (`plugin_monitoring_services_id`),
            # KEY `plugin_monitoring_services_id_2` (`plugin_monitoring_services_id`,`date`),
            # KEY `unavailability` (`unavailability`,`state_type`,`plugin_monitoring_services_id`),
            # KEY `plugin_monitoring_services_id_3` (`plugin_monitoring_services_id`,`id`)
            # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
            logger.info("append data to events_cache for service: %s", service_id)
            data = {
                'plugin_monitoring_services_id': service_cache['items_id'],
                'date': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                    '%Y-%m-%d %H:%M:%S'),
                'event': ("%s \n %s", b.data['output'], b.data['long_output']) if (
                        len(b.data['long_output']) > 0) else b.data['output'],
                'state': b.data['state'],
                'state_type': b.data['state_type'],
                'perf_data': b.data['perf_data'],
                'latency': b.data['latency'],
                'execution_time': b.data['execution_time']
            }

            # Append to bulk insert queue ...
            self.events_cache.append(data)

        # Update service state table
        if self.update_services:
            # SQL table is: CREATE TABLE `glpi_plugin_monitoring_services` (
            # `id` int(11) NOT NULL AUTO_INCREMENT,
            # `entities_id` int(11) NOT NULL DEFAULT '0',
            # `name` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `plugin_monitoring_components_id` int(11) NOT NULL DEFAULT '0',
            # `plugin_monitoring_componentscatalogs_hosts_id` int(11) NOT NULL DEFAULT '0',
            # `event` varchar(4096) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `state` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `state_type` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
            # `last_check` datetime DEFAULT NULL,
            # `arguments` text DEFAULT NULL COLLATE utf8_unicode_ci,
            # `networkports_id` int(11) NOT NULL DEFAULT '0',
            # `is_acknowledged` tinyint(1) NOT NULL DEFAULT '0',
            # `is_acknowledgeconfirmed` tinyint(1) NOT NULL DEFAULT '0',
            # `acknowledge_comment` text DEFAULT NULL COLLATE utf8_unicode_ci,
            # `acknowledge_users_id` int(11) NOT NULL DEFAULT '0',
            # PRIMARY KEY (`id`),
            # KEY `state` (`state`(50),`state_type`(50)),
            # KEY `plugin_monitoring_componentscatalogs_hosts_id`
            # (`plugin_monitoring_componentscatalogs_hosts_id`),
            # KEY `last_check` (`last_check`)
            # ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
            data = {
                'event': "%s \n %s" % (b.data['output'], b.data['long_output']) if (
                    b.data['long_output']) else b.data['output'],
                'state': b.data['state'],
                'state_type': b.data['state_type'],
                'last_check': datetime.datetime.fromtimestamp(int(b.data['last_chk'])).strftime(
                    '%Y-%m-%d %H:%M:%S'),
                'is_acknowledged': '1' if b.data['problem_has_been_acknowledged'] else '0'
            }
            where_clause = {'id': service_cache['items_id']}
            query = self.create_update_query(self.services_table, data, where_clause)
            try:
                self.execute_query(query)
            except Exception as exp:
                logger.error("error '%s' when executing query: %s", exp, query)

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
                if not self.is_connected:
                    logger.info("Trying to connect database ...")
                    self.open()

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

                logger.debug("time to manage %d broks (%d seconds)",
                             len(message), time.time() - start)
            except queue.Full:
                logger.warning("Worker control queue is full")
            except queue.Empty:
                pass
            except EOFError:
                # Broken queue ... the broker deleted the module queue
                time.sleep(1.0)
                continue
            except Exception as exp:  # pylint: disable=broad-except
                logger.error("Exception when getting master orders: %s. ", str(exp))
