import copy
import os
import sys
import time
import getpass
import datetime
import textfsm
import smtplib
import jinja2
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from netmiko.ssh_exception import NetMikoAuthenticationException
from paramiko.ssh_exception import SSHException
import json

def main():
    os.system('clear')
    print_banner()

    master_obj_list = [] # Used to track the Device objects created throughout the script
    temp_obj_list = []
    temp_obj_list2 = []
    fail_auth_list = []
    
    hostname = 'san-n-sbx-sw-01'
    device = Device(hostname)
    master_obj_list.append(device)

    credentials = confirm_pass()
    if device.authenticate(credentials) is None:
        print('\nCould not authenticate to: {}. Exiting script...\n'.format(device.hostname))
        exit()

    # vlan_list = sorted([113,144,171,173,176,180,181,182,183,184,195,932,940,943,990,996,1210,1212,1213,1215,1217,1220,1221,1267,1268,1269,1288,1396,1496,1700,1701,1702,1703,1704,1705,1706,1707,1708,1709,1710,1711,1712,1713,1714,1715,1716,1717,1718,1719,1720,1721,1722,1723,1724,1730,1731,1732,1733,1741,1742,1743,1745,1746,1750,1751,1752,1753,1755,1756,1759,1761,1762,1763,1764,1765,1766,1767,1768,1769,1770,1771,1772,1773,1774,1781,1782,1811,1814,1818,1819,1822,1823,1826,1831,1832,1833,1834,1835,1836,1837,1838,1839,1840,1841,1842,1843,1844,1845,1846,1847,1848,1849,1850,1851,1852,1853,1854,1855,1856,1859,1860,1861,1862,1863,1864,1865,1866,1867,1868,1871,1872,1873,1874,1875,1876,1877,1878,1881,1882,1887,1892,1893,1899])
    vlan_list = sorted([1884, 1885, 1218, 113])

    vlan_name_dict = vlan_names(vlan_list, credentials, hostname) # Returns dictionary with id:name mappings
    
    for vlan in vlan_list: 
        device.get_stp(vlan)
        device.get_macs(vlan)
    device.get_cdp()
    device.merge_info(vlan_name_dict) # Creates dictionary will all information collected in the methods above
    
    temp_hostname_list = []
    for k in device.vlan_mapping:
        for neighbor in device.vlan_mapping[k]['neighbors']:
            if neighbor not in [obj.hostname for obj in master_obj_list]:
                temp_hostname_list.append(neighbor)
    
    temp_obj_list = [Device(hostname) for hostname in list(set(temp_hostname_list))]
    master_obj_list.extend(temp_obj_list)
   
    while True:
        temp_hostname_list.clear()
        for obj in temp_obj_list:
            if obj.authenticate(credentials) is None:
                print('\n  Could not authenticate to: {}. Skipping...\n'.format(obj.hostname))
                fail_auth_list.append(obj.hostname)
                continue

            vlan_list.clear()
            for obj2 in master_obj_list:
                for vlan in obj2.vlan_mapping:
                    if obj.hostname in obj2.vlan_mapping[vlan]['neighbors']:
                        vlan_list.append(vlan)

            for vlan in list(set(vlan_list)): 
                obj.get_stp(vlan)
                obj.get_macs(vlan)
            obj.get_cdp()
            obj.merge_info(vlan_name_dict)

        for obj in temp_obj_list:
            for k in obj.vlan_mapping:
                for neighbor in obj.vlan_mapping[k]['neighbors']:
                    if neighbor not in [obj2.hostname for obj2 in master_obj_list]:
                        temp_hostname_list.append(neighbor)

        temp_obj_list2 = [Device(hostname) for hostname in list(set(temp_hostname_list))]
        
        if len(temp_obj_list2) < 1: 
            print('\nNo new neighbors found.')
            break
        else:
            temp_obj_list = temp_obj_list2
            temp_obj_list2 = []
            master_obj_list.extend(temp_obj_list)
            continue
    
    # for obj in master_obj_list:
    #     print(json.dumps({obj.hostname: obj.vlan_mapping}, indent=4, sort_keys='True'))


def confirm_pass():
    while True:
        username = input('Qualnet username: ')

        if username == "":
            custom_errors(6)
            continue
        else:
            break

    password_tries, max_attempts = 0, 3
    while password_tries != max_attempts:
        password = getpass.getpass('Qualnet password: ')
        confirm = getpass.getpass('Confirm password: ')

        if password == "":
            password_tries += 1
            remaining_attempts = max_attempts-password_tries
            print_string = "\nPassword cannot be blank. Attempts remaining: " + str(remaining_attempts)
            print(print_string)
            print(len(print_string) * "-")
            continue
        elif password != confirm:
            password_tries += 1
            remaining_attempts = max_attempts-password_tries
            print_string = "\nPasswords do not match. Attempts remaining: " + str(remaining_attempts)
            print(print_string)
            print(len(print_string) * "-")
            continue
        elif password == confirm:
            break

    if password_tries == max_attempts:
        custom_errors(7)
        restart_script()

    return username, password


def restart_script():
    custom_errors(3)
    time.sleep(1)
    os.execv(sys.executable, ['python'] + sys.argv)


def custom_errors(num):
    num = int(num)
    error_dict = {
        0: "Invalid selection. Please try again.",
        1: "You entered a non-numeric value. Check the value and try again.",
        2: "Quitting script.",
        3: "Restarting script.",
        5: "Do not enter blank values.",
        6: "Username cannot be blank.",
        7: "Maximum number of attempts exceeded.",
        10: "There was an error executing the script..."
    }

    print("\n{}".format(error_dict.get(num)))
    print(len(error_dict.get(num)) * '-')

    return


def print_banner():
    print("""
************************************************************************************************

                    Welcome to the Sandbox VLAN Crawl

Send an email to 'ansible.itnet.core@qualcomm.com' \
to report any issues with the script.

Please make sure to read the README before running the script.

Note: Filtering for VLAN interfaces is performed in TextFSM Templates

************************************************************************************************
""")

    return

def vlan_names(vlan_list, credentials, device):
    device_dictionary = {}
    device_dictionary['timeout'] = 10
    device_dictionary['ip'] = device
    device_dictionary['device_type'] = 'cisco_ios'
    device_dictionary['username'] = credentials[0]
    device_dictionary['password'] = credentials[1]

    try:
        device_connector = ConnectHandler(**device_dictionary)
    except (EOFError, SSHException, NetMikoTimeoutException, NetMikoAuthenticationException):
        print('Could not authenticate to {}. Quitting script.'.format(device))
        exit()

    command = 'show vlan'
    fsm = textfsm.TextFSM(open("./templates/show_vlan.template"))
    print('\n  Device: {}, Command: {}'.format(device, command))
    vlan_results = fsm.ParseText(device_connector.send_command(command))

    if len(vlan_results) < 1: # If the template did not return any vlans, quit the script
        print('\n  The script did not find any VLANs. Quitting script.')
        exit()

    vlan_name_dict = {vlan[0]: vlan[1] for vlan in vlan_results}
    
    return vlan_name_dict


class Device:
    def __init__(self, hostname):
        self.hostname = hostname
        self.device_connector = None
        self.cdp = {}
        self.stp = {}
        self.macs = {}
        self.vlan_mapping = {}

    def authenticate(self, credentials):
        device_dictionary = {}
        device_dictionary['timeout'] = 10
        device_dictionary['ip'] = self.hostname
        device_dictionary['device_type'] = 'cisco_ios'
        device_dictionary['username'] = credentials[0]
        device_dictionary['password'] = credentials[1]

        try:
            self.device_connector = ConnectHandler(**device_dictionary)
        except (EOFError, SSHException, NetMikoTimeoutException, NetMikoAuthenticationException):
            pass

        return self.device_connector

    def get_stp(self, vlan_id):
        template_file = "./templates/stp.template"
        fsm = textfsm.TextFSM(open(template_file))

        command = 'show spanning-tree vlan {}'.format(vlan_id)
        print("  Device: {}, command: {}".format(self.hostname, command))
        fsm_results = fsm.ParseText(self.device_connector.send_command(command))

        for n in fsm_results: self.stp[n[0]] = {'interfaces': []}
        for n in fsm_results: self.stp[n[0]]['interfaces'].append(n[1])

    def get_macs(self, vlan_id):
        command = 'show mac address-table dynamic vlan {}'.format(vlan_id)
        print("  Device: {}, command: {}".format(self.hostname, command))
        results = self.device_connector.send_command(command)
        temp_dict = {vlan_id: results}

        self.macs.update(temp_dict)

    def get_cdp(self):
        template_file = "./templates/cdp.template"
        fsm = textfsm.TextFSM(open(template_file))

        command = 'show cdp neighbors detail'
        print("  Device: {}, command: {}".format(self.hostname, command))
        fsm_results = fsm.ParseText(self.device_connector.send_command(command))
        
        replace_list = ["TenGigabitEthernet", "GigabitEthernet", "FastEthernet", "Port-Channel", "Ethernet"]
        for n in fsm_results:
            if '.' in n[0]:
                n[0] = n[0].split('.')[0]

            for o in replace_list:
                n[3] = n[3].replace(o, o[:2])
                n[4] = n[4].replace(o, o[:2])

            temp_dict = {n[4]: n[0]}
            self.cdp.update(temp_dict)

    def merge_info(self, vlan_name_dict):
        self.vlan_mapping = copy.deepcopy(self.stp)

        for k in self.vlan_mapping: self.vlan_mapping[k]['neighbors'] = []; self.vlan_mapping[k]['name'] = None
        for k in self.vlan_mapping:
            for interface in self.vlan_mapping[k]['interfaces']:
                if interface in self.cdp:
                    self.vlan_mapping[k]['neighbors'].append(self.cdp[interface])
            self.vlan_mapping[k]['name'] = vlan_name_dict[k]


# def main():
#     """ """

#     os.system('clear')
#     print_banner()

#     master_hostname_list = []
#     master_obj_list = []

#     device = 'san-n-sbx-rt-01'
#     print("Running script on: {}".format(device))

#     credentials = confirm_pass()

#     router = Router(device)
#     master_obj_list.append(router)
#     master_hostname_list.append(router.hostname)

#     if router.authenticate(credentials) is None:
#         print('\nCould not authenticate to: {}. Exiting script...\n'.format(router.hostname))
#         exit()

#     print("\n-----------------------")
#     router.getVrfInterfaces()
#     router.getVlanInterfaces()
#     print("-----------------------")


# #    sorted_vlan_list = sorted([int(n) for n in router.vlan_interfaces.keys()])
# #    string_vlan_list = [str(n) for n in sorted_vlan_list]
    
# #    sorted_vlan_list = sorted([1389,1390,1392])
#     sorted_vlan_list = sorted([113,144,171,173,176,180,181,182,183,184,195,932,940,943,990,996,1210,1212,1213,1215,1217,1220,1221,1267,1268,1269,1288,1396,1496,1700,1701,1702,1703,1704,1705,1706,1707,1708,1709,1710,1711,1712,1713,1714,1715,1716,1717,1718,1719,1720,1721,1722,1723,1724,1730,1731,1732,1733,1741,1742,1743,1745,1746,1750,1751,1752,1753,1755,1756,1759,1761,1762,1763,1764,1765,1766,1767,1768,1769,1770,1771,1772,1773,1774,1781,1782,1811,1814,1818,1819,1822,1823,1826,1831,1832,1833,1834,1835,1836,1837,1838,1839,1840,1841,1842,1843,1844,1845,1846,1847,1848,1849,1850,1851,1852,1853,1854,1855,1856,1859,1860,1861,1862,1863,1864,1865,1866,1867,1868,1871,1872,1873,1874,1875,1876,1877,1878,1881,1882,1887,1892,1893,1899])
#     string_vlan_list = [str(n) for n in sorted_vlan_list]


#     print("\n-----------------------")
#     for n in string_vlan_list:
#         router.getMac(n)
#         router.getArp(n)
#     print("-----------------------")

#     router.device_connector.disconnect()

#     while True:
#         choice = raw_input("\nWould you like a copy of the output and exit the script? [Y|N]: ").upper().strip()

#         if choice in ("Y", "N"):
#             break
#         else:
#             continue

#     if choice == "Y":
#         prepEmail(credentials, write_file(router))

#     print("-----------------------")
# ###########################################################################################
#     neighbors_list = ['san-n-sbx-sw-01']

#     variable_dict = {"router": router,
#                      "credentials": credentials,
#                      "neighbors_list": neighbors_list,
#                      "master_hostname_list": master_hostname_list,
#                      "master_obj_list": master_obj_list}

#     while len(neighbors_list) > 0:
#         neighbors_list = loopFunc(**variable_dict)
#         variable_dict['neighbors_list'] = neighbors_list

#     print('\nWriting results to file...')
#     prepEmail(credentials, write_file(router, master_obj_list))


# def loopFunc(router, credentials, neighbors_list, master_hostname_list, master_obj_list):
#     """ """

#     obj_list = [Switch(n) for n in neighbors_list]

#     print("\nThe script will now try authenticating on to:")
#     print("-----------------------")
#     for n in obj_list:
#         print " - {}".format(n.hostname)
#     print("-----------------------")

#     text = None
#     while text is not "":
#         text = raw_input("\nPress Enter to continue: ")

#     for n in obj_list:
#         if n.authenticate(credentials) is None:
#             print('\nCould not authenticate on to: {}'.format(n.hostname))
#         else:
#             master_hostname_list.append(n.hostname)
#             master_obj_list.append(n)

#     for n in obj_list:
#         if n.device_connector is None:
#             obj_list.remove(n)

#     if len(obj_list) < 1:
#         exit()

#     print("\nThe script will now run 'show spanning-tree' and 'show cdp neighbors detail' on the following devices:")
#     print("-----------------------")
#     for n in obj_list:
#         print " - {}".format(n.hostname)
#     print("-----------------------")

#     text = None
#     while text is not "":
#         text = raw_input("\nPress Enter to continue: ")

#     print("\n-----------------------")
#     for n in obj_list:
#         n.getStp()
#         n.getCdp()
#     print("-----------------------")

#     print('\nFinding VLANs that can be pruned...')

#     for n in obj_list:
#         n.getPruneVlans(router.vlan_interfaces)
#         n.getPruneNeighbors(router.vlan_interfaces)

#     for n in obj_list:
#         print("\n{}".format(n.hostname))
#         print("-----------------------")
#         if len(n.prune_vlans.keys()) < 1:
#             print("  Did not find any VLANs to prune")
#         else:
#             for k, v in n.prune_vlans.items():
#                 interface_list = [n['interface'] for n in v]
#                 print("  VLAN {} can be pruned from the following interfaces: {}".format(k, interface_list))
#         print("-----------------------")

#     neighbors_list = []
#     for n in obj_list:
#         if n.prune_neighbors is not None:
#             for o in n.prune_neighbors:
#                 if o not in master_hostname_list:
#                     if o not in neighbors_list:
#                         neighbors_list.append(o)

#     return neighbors_list



# class Router:
#     def __init__(self, hostname):
#         self.hostname = hostname
#         self.vlan_interfaces = {}
#         self.vrf_interfaces = {}
#         self.device_connector = None

#     def authenticate(self, credentials):
#         device_dictionary = {
#             'device_type': 'cisco_ios',
#             'ip': self.hostname,
#             'username': credentials[0],
#             'password': credentials[1]
#             }

#         try:
#             self.device_connector = ConnectHandler(**device_dictionary)
#         except (EOFError, SSHException, NetMikoTimeoutException, NetMikoAuthenticationException):
#             pass

#         return self.device_connector

#     def getVrfInterfaces(self):
#         template_file = "./templates/vrfinterfaces.template"
#         fsm = textfsm.TextFSM(open(template_file))

#         command = 'show vrf ipv4 interfaces'
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         fsm_results = fsm.ParseText(self.device_connector.send_command(command))

#         for n in fsm_results:
#             self.vrf_interfaces[n[0]] = {"vrf": n[1]}

#     def getVlanInterfaces(self):
#         template_file = "./templates/vlaninterfaces.template"
#         fsm = textfsm.TextFSM(open(template_file))

#         command = 'show interface'
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         fsm_results = fsm.ParseText(self.device_connector.send_command(command))

#         for n in fsm_results:
#             self.vlan_interfaces[n[0]] = {
#                 "link": n[1],
#                 "protocol": n[2],
#                 "hardware": n[3],
#                 "description": n[4],
#                 "ip": n[5],
#                 "input": n[6],
#                 "arp": "",
#                 "mac": "",
#                 "entries": "",
#                 "vrf": ""}

#         for n in self.vlan_interfaces.keys():
#             if self.vrf_interfaces.get(n):
#                 self.vlan_interfaces[n]['vrf'] = self.vrf_interfaces[n]['vrf']
#             else:
#                 self.vlan_interfaces[n]['vrf'] = None

#     def getMac(self, vlan_id):
#         command = 'show mac address-table dynamic vlan'
#         command = '{} {}'.format(command, vlan_id)
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         results = self.device_connector.send_command(command)

#         if results:
#             self.vlan_interfaces[vlan_id]['mac'] = results
#             if 'No entries present.' in results:
#                 self.vlan_interfaces[vlan_id]['entries'] = False
#             else:
#                 self.vlan_interfaces[vlan_id]['entries'] = True

#     def getArp(self, vlan_id):
#         if self.vlan_interfaces[vlan_id]['vrf'] is None:
#             command = 'show arp vlan'
#         else:
#             command = 'show arp vrf {} vlan'.format(self.vlan_interfaces[vlan_id]['vrf'])

#         command = '{} {}'.format(command, vlan_id)
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         results = self.device_connector.send_command(command)

#         if results:
#             self.vlan_interfaces[vlan_id]['arp'] = results


# class Switch(Router):
#     def __init__(self, hostname):
#         Router.__init__(self, hostname)

#         self.cdp = []
#         self.stp = {}
#         self.prune_vlans = {}
#         self.prune_neighbors = []

#     def getCdp(self):

#         replace_list = ["TenGigabitEthernet", "GigabitEthernet", "FastEthernet", "Port-Channel", "Ethernet"]

#         template_file = "./templates/cdp.template"
#         fsm = textfsm.TextFSM(open(template_file))

#         command = 'show cdp neighbors detail'
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         fsm_results = fsm.ParseText(self.device_connector.send_command(command))

#         for n in fsm_results:
#             if '.' in n[0]:
#                 n[0] = n[0].split('.')[0]

#             for o in replace_list:
#                 n[3] = n[3].replace(o, o[:2])
#                 n[4] = n[4].replace(o, o[:2])

#             temp_dict = {'destination_host': n[0], 'remote_port': n[3], 'local_port': n[4], }
#             self.cdp.append(temp_dict)

#     def getStp(self):

#         template_file = "./templates/stp.template"
#         fsm = textfsm.TextFSM(open(template_file))

#         command = 'show spanning-tree'
#         print("  Device: {}, command: {}".format(self.hostname, command))
#         fsm_results = fsm.ParseText(self.device_connector.send_command(command))

#         for n in fsm_results:
#             n[0] = str(n[0])
#             self.stp[n[0]] = []

#         for n in fsm_results:
#             n[0] = str(n[0])
#             temp_dict = {'interface': n[1], 'role': n[2], 'status': n[3], 'type': n[7]}
#             self.stp[n[0]].append(temp_dict)

#     def getPruneVlans(self, vlan_interfaces):
#         for n in vlan_interfaces.keys():
#             if vlan_interfaces[n].get('entries') is False:
#                 if self.stp.get(n):
#                     temp_dict = {n: self.stp[n]}
#                     self.prune_vlans.update(temp_dict)

#     def getPruneNeighbors(self, vlan_interfaces):
#         neighbors_list = []

#         for n in vlan_interfaces.keys():
#             if self.prune_vlans.get(n) is not None:
#                 for o in self.prune_vlans[n]:
#                     for p in self.cdp:
#                         if o['interface'] == p['local_port']:
#                             neighbors_list.append(p['destination_host'])

#         if len(neighbors_list) < 1:
#             self.prune_neighbors = None

#         if self.prune_neighbors is not None:
#             self.prune_neighbors = list(set(neighbors_list))


if __name__ == '__main__':
    main()
