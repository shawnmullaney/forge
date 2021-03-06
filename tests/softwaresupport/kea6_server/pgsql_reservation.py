# Copyright (C) 2016 Internet Systems Consortium.
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND INTERNET SYSTEMS CONSORTIUM
# DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# INTERNET SYSTEMS CONSORTIUM BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Author: Wlodzimierz Wencel

import os
import sys
import logging

from forge_cfg import world, step
from softwaresupport.multi_server_functions import fabric_run_command, fabric_send_file,\
    remove_local_file, copy_configuration_file, fabric_sudo_command, json_file_layout,\
    fabric_download_file, fabric_remove_file_command, locate_entry


log = logging.getLogger('forge')


list_of_all_reservations = []


class PSQLReservation:
    hosts_v6_hex = """
INSERT INTO hosts (dhcp_identifier,dhcp_identifier_type,dhcp6_subnet_id,hostname)
VALUES (DECODE(REPLACE(:'identifier_value', ':', ''), 'hex'),(SELECT type FROM host_identifier_type WHERE name=:'identifier_type'),:dhcp6_subnet_id,:'hostname');
SELECT LASTVAL() INTO lastval;"""
    hosts_v6_flex = hosts_v6_hex
    """
INSERT INTO hosts (dhcp_identifier,dhcp_identifier_type,dhcp6_subnet_id,hostname)
VALUES (:'identifier_value',(SELECT type FROM host_identifier_type WHERE name=:'identifier_type'),:dhcp6_subnet_id,:'hostname');
SELECT LASTVAL() INTO lastval;"""
    hosts_v6 = ""

    hosts_v4_hex = """
INSERT INTO hosts (dhcp_identifier, dhcp_identifier_type, dhcp4_subnet_id, ipv4_address, hostname, dhcp4_next_server, dhcp4_server_hostname, dhcp4_boot_file_name)
VALUES (DECODE(REPLACE(:'identifier_value', ':', ''), 'hex'),(SELECT type FROM host_identifier_type WHERE name=:'identifier_type'), :dhcp4_subnet_id, (SELECT (:'ipv4_address'::inet - '0.0.0.0'::inet)),:'hostname',(SELECT (:'next_server'::inet - '0.0.0.0'::inet)),:'server_hostname',:'boot_file_name');
SELECT LASTVAL() INTO lastval;"""
    hosts_v4_flex = hosts_v4_hex
    """
INSERT INTO hosts (dhcp_identifier, dhcp_identifier_type, dhcp4_subnet_id, ipv4_address, hostname, dhcp4_next_server, dhcp4_server_hostname, dhcp4_boot_file_name)
VALUES (:'identifier_value',(SELECT type FROM host_identifier_type WHERE name=:'identifier_type'), :dhcp4_subnet_id, (SELECT (:'ipv4_address'::inet - '0.0.0.0'::inet)),:'hostname',(SELECT (:'next_server'::inet - '0.0.0.0'::inet)),:'server_hostname',:'boot_file_name');
SELECT LASTVAL() INTO lastval;"""
    hosts_v4 = ""

    def __init__(self):
        self.reservation_id = len(list_of_all_reservations) + 1
        list_of_all_reservations.append(self)
        self.hostname = ""
        self.identifier_type = ""
        self.identifier_value = ""
        self.dhcp4_subnet_id = ""
        self.dhcp6_subnet_id = ""
        self.ipv4_address = ""
        self.dhcp4_client_classes = ""
        self.dhcp6_client_classes = ""
        self.server_hostname = ""
        self.boot_file_name = ""
        self.next_server = "0.0.0.0"  # this is being set because script fail without that value.
        # to ipv6_reservations list please add just dicts:
        #     {"ipv6_address_reservation": "2001::1"}
        #  or {"ipv6_prefix_reservation": "2220::", "ipv6_prefix_len_reservation": 3}
        #TODO: add iaid
        self.ipv6_reservations = []

        # to options list please add just dicts {"code": 1, "option_value": "192.168.1.2",
        #  "space": "dhcp4", "persistent": 1, "scope": }
        self.options = []

        self.configuration_script = "START TRANSACTION;"

    def add_reserved_option(self, single_option):
        self.options += single_option

    ## Build config file
    def set_ipv4_address(self):
        self.configuration_script += "\n\\set ipv4_address '" + self.ipv4_address + "'"

    def set_dhcp4_client_classes(self):
        self.configuration_script += "\n\\set dhcp4_client_classes '" + self.dhcp4_client_classes + "'"

    def set_dhcp6_client_classes(self):
        self.configuration_script += "\n\\set dhcp6_client_classes '" + self.dhcp6_client_classes + "'"

    def set_hostname(self):
        self.configuration_script += "\n\\set hostname '" + self.hostname + "'"

    def set_identifier_type(self):
        self.configuration_script += "\n\\set identifier_type '" + self.identifier_type + "'"

    def set_identifier_value(self):
        self.configuration_script += "\n\\set identifier_value '" + self.identifier_value + "'"

    def set_dhcp4_subnet_id(self):
        if self.dhcp4_subnet_id != "":
            self.dhcp4_subnet_id = str(self.dhcp4_subnet_id)
        self.configuration_script += "\n\\set dhcp4_subnet_id '" + self.dhcp4_subnet_id + "'"

    def set_dhcp6_subnet_id(self):
        if self.dhcp6_subnet_id != "":
            self.dhcp6_subnet_id = str(self.dhcp6_subnet_id)
        self.configuration_script += "\n\\set dhcp6_subnet_id '" + self.dhcp6_subnet_id + "'"

    def set_next_server(self):
        self.configuration_script += "\n\\set next_server '" + self.next_server + "'"

    def set_server_hostname(self):
        self.configuration_script += "\n\\set server_hostname '" + self.server_hostname + "'"

    def set_boot_file_name(self):
        self.configuration_script += "\n\\set boot_file_name '" + self.boot_file_name + "'"

    def set_ipv6_reservations(self):
        for each in self.ipv6_reservations:
            if len(each) == 1:
                self.configuration_script += "\nINSERT INTO ipv6_reservations(address, type, host_id)"
                self.configuration_script += "\nVALUES ('{ipv6_address_reservation}'," \
                                             " 0, (SELECT lastval FROM lastval));".format(**each)
            if len(each) == 2:
                self.configuration_script += "\n\\set ipv6_prefix_reservation " \
                                             "'{ipv6_prefix_reservation}'".format(**each)
                if each["ipv6_prefix_len_reservation"] != "":
                    self.configuration_script += "\n\\set ipv6_prefix_len_reservation '" \
                                                 + str(each["ipv6_prefix_len_reservation"]) + "'"
                    self.configuration_script += "\nINSERT INTO ipv6_reservations(address, prefix_len, type, host_id)\
                            \nVALUES (:'ipv6_prefix_reservation'," \
                                                 ":'ipv6_prefix_len_reservation', 2, (SELECT lastval FROM lastval));"
            else:
                pass

    def set_ipv6_options(self):
        for each in self.options:
            if len(each) > 0:
                each['persistent'] = (True if each['persistent'] == 1 else False)
                self.configuration_script += "\nINSERT INTO dhcp6_options (code, formatted_value," \
                                             " space, host_id, scope_id)"
                self.configuration_script += "\nVALUES ({code}, '{option_value}', '{space}', " \
                                             " (SELECT lastval FROM lastval),(SELECT scope_id FROM dhcp_option_scope " \
                                             "WHERE scope_name= '{scope}'));".format(**each)

    def set_ipv4_options(self):
        for each in self.options:
            if len(each) > 0:
                each['persistent'] = (True if each['persistent'] == 1 else False)
                self.configuration_script += "\nINSERT INTO dhcp4_options (code, formatted_value," \
                                             " space, persistent, host_id, scope_id)"
                self.configuration_script += "\nVALUES ({code}, '{option_value}', '{space}', {persistent}," \
                                             " (SELECT lastval FROM lastval),(SELECT scope_id FROM dhcp_option_scope " \
                                             "WHERE scope_name= '{scope}'));".format(**each)

    def build_v6_script(self):
        if self.identifier_type == "flex-id":
            PSQLReservation.hosts_v6 = PSQLReservation.hosts_v6_flex
        else:
            PSQLReservation.hosts_v6 = PSQLReservation.hosts_v6_hex
        self.set_hostname()
        self.set_identifier_type()
        self.set_identifier_value()
        self.set_dhcp4_subnet_id()
        self.set_dhcp6_subnet_id()
        self.set_dhcp6_client_classes()
        self.configuration_script += PSQLReservation.hosts_v6
        self.set_ipv6_reservations()
        self.set_ipv6_options()
        self.configuration_script += "\nDROP TABLE lastval;\nCOMMIT;"

    def build_v4_script(self):
        if self.identifier_type == "flex-id":
            PSQLReservation.hosts_v4 = PSQLReservation.hosts_v4_flex
        else:
            PSQLReservation.hosts_v4 = PSQLReservation.hosts_v4_hex
        self.set_hostname()
        self.set_identifier_type()
        self.set_identifier_value()
        self.set_dhcp4_subnet_id()
        self.set_dhcp6_subnet_id()
        self.set_server_hostname()
        self.set_next_server()
        self.set_boot_file_name()
        self.set_ipv4_address()
        self.set_dhcp4_client_classes()
        self.configuration_script += PSQLReservation.hosts_v4
        self.set_ipv4_options()
        self.configuration_script += "\nDROP TABLE lastval;\nCOMMIT;"

    def build_script(self):
        if world.proto == "v4":
            self.build_v4_script()
        elif world.proto == "v6":
            self.build_v6_script()

    def print_config(self):
        log.info(self.configuration_script)


def enable_db_backend_reservation():
    world.reservation_backend = "postgresql"


def new_db_backend_reservation(reservation_identifier, reservation_identifier_value):
    enable_db_backend_reservation()
    reservation_record = PSQLReservation()
    reservation_record.identifier_type = reservation_identifier
    reservation_record.identifier_value = reservation_identifier_value


def upload_db_reservation(exp_failed=False):
    db_name = world.f_cfg.db_name
    db_user = world.f_cfg.db_user
    db_passwd = world.f_cfg.db_passwd
    fail_spotted = False
    while list_of_all_reservations:
        each_record = list_of_all_reservations.pop()
        each_record.build_script()
        db_reservation = open("db_reservation", 'w')
        db_reservation.write(each_record.configuration_script)
        db_reservation.close()
        remote_db_path = world.f_cfg.tmp_join("db_reservation")
        fabric_send_file("db_reservation", remote_db_path)
        copy_configuration_file("db_reservation")
        remove_local_file("db_reservation")
        result = fabric_sudo_command('psql -U {db_user} -d {db_name} < {remote_db_path}'.format(**locals()))
        if exp_failed:
            if result.failed:
                fail_spotted = True
        else:
            assert result.succeeded

    if exp_failed:
        assert fail_spotted


def clear_all_reservations():
    db_name = world.f_cfg.db_name
    db_user = world.f_cfg.db_user
    db_passwd = world.f_cfg.db_passwd
    command = 'for table_name in dhcp4_options dhcp6_options ipv6_reservations hosts lease4 lease6; do psql -U {db_user} -d {db_name} -c "delete from $table_name" ; done'.format(**locals())
    fabric_run_command(command)


def update_db_backend_reservation(field_name, field_value, reservation_record_id):
    for each_record in list_of_all_reservations:
        if each_record.reservation_id == reservation_record_id:
            each_record.__dict__[field_name] = field_value


def ipv6_prefix_db_backend_reservation(reserved_prefix, reserved_prefix_len, reserved_iaid, reservation_record_id):
    for each_record in list_of_all_reservations:
        if each_record.reservation_id == reservation_record_id:
            each_record.ipv6_reservations.append({"ipv6_prefix_reservation": reserved_prefix,
                                                  "ipv6_prefix_len_reservation": reserved_prefix_len}) #TODO iaid


def ipv6_address_db_backend_reservation(reserved_address, reserved_iaid, reservation_record_id):
    for each_record in list_of_all_reservations:
        if each_record.reservation_id == reservation_record_id:
            each_record.ipv6_reservations.append({"ipv6_address_reservation": reserved_address}) #TODO iaid


def option_db_record_reservation(reserved_option_code, reserved_option_value, reserved_option_space,
                                 reserved_option_persistent, reserved_option_client_class, reserved_subnet_id,
                                 reserved_option_scope, reservation_record_id):
    for each_record in list_of_all_reservations:
        if each_record.reservation_id == reservation_record_id:
            each_record.options.append({"code": reserved_option_code, "option_value": reserved_option_value,
                                        "space": reserved_option_space, "persistent": reserved_option_persistent,
                                        "scope": reserved_option_scope}) #TODO client class


if __name__ == '__main__':
    world.proto = "v6"
    test_v6_PSQLReservation_class = PSQLReservation()
    test_v6_PSQLReservation_class.hostname = "some.host.name.com"
    test_v6_PSQLReservation_class.identifier_type = "duid"
    test_v6_PSQLReservation_class.identifier_value = "00:02:00:00:09:BF:10:20:03:04:05:06:07:08"
    test_v6_PSQLReservation_class.ipv6_reservations.append({"ipv6_address_reservation": "2001:db8:1::1111"})
    test_v6_PSQLReservation_class.ipv6_reservations.append({"ipv6_address_reservation": "2001:db8:1::2222"})
    test_v6_PSQLReservation_class.ipv6_reservations.append({"ipv6_prefix_reservation": "2001:db8:1::",
                                                            "ipv6_prefix_len_reservation": 43})
    test_v6_PSQLReservation_class.ipv6_reservations.append({"ipv6_prefix_reservation": "2001:db8:2::",
                                                            "ipv6_prefix_len_reservation": 53})
    test_v6_PSQLReservation_class.dhcp4_subnet_id = 4
    test_v6_PSQLReservation_class.dhcp6_subnet_id = 2
    test_v6_PSQLReservation_class.options.append({"code": 1, "option_value": "2001:db8:1::1",
                                                   "space": "dhcp6", "persistent": 1, "scope": "subnet"})
    test_v6_PSQLReservation_class.options.append({"code": 2, "option_value": "2001:db8:1::1",
                                                   "space": "dhcp6", "persistent": 1, "scope": "subnet"})
    #build config:
    test_v6_PSQLReservation_class.build_v6_script()
    #print config:
    test_v6_PSQLReservation_class.print_config()

    #v4 reservation test:
    # world.proto = "v4"
    # test_v4_PSQLReservation_class = PSQLReservation()
    # test_v4_PSQLReservation_class.hostname = "22222222some.host.name.com"
    # test_v4_PSQLReservation_class.identifier_type = "hw-address"
    # test_v4_PSQLReservation_class.identifier_value = "10:20:30:40:50:63"
    # test_v4_PSQLReservation_class.ipv4_address = "192.168.1.12"
    # test_v4_PSQLReservation_class.dhcp4_subnet_id = 4
    # test_v4_PSQLReservation_class.dhcp6_subnet_id = 2
    # test_v4_PSQLReservation_class.next_server = "10.0.0.1"
    # test_v4_PSQLReservation_class.server_hostname = "example.org"
    # test_v4_PSQLReservation_class.boot_file_name = "bootfile.efi"
    # test_v4_PSQLReservation_class.options.append({"code": 1, "option_value": "2001:db8:1::1",
    #                                                "space": "dhcp4", "persistent": 1, "scope": "subnet"})
    # test_v4_PSQLReservation_class.options.append({"code": 2, "option_value": "2001:db8:1::1",
    #                                                "space": "dhcp4", "persistent": 1, "scope": "subnet"})
    # #build config:
    # test_v4_PSQLReservation_class.build_v4_script()
    # #print config:
    # test_v4_PSQLReservation_class.print_config()
    #
    for each in list_of_all_reservations:
        del each
