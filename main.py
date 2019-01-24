import csv
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
    temp_obj_list = [] # Used as a temporary list to track new neighbors
    temp_obj_list2 = [] # Used as a list to store Device objects 
    fail_auth_list = [] # Stores hostnames of devices that failed authentication
    temp_hostname_list = []
    
    hostname = 'san-n-sbx-sw-01'
    device = Device(hostname)
    master_obj_list.append(device)

    credentials = confirm_pass()
    if device.authenticate(credentials) is None:
        print('\nCould not authenticate to: {}. Exiting script...\n'.format(device.hostname))
        exit()

    # vlan_list = sorted([113,144,171,173,176,180,181,182,183,184,195,932,940,943,990,996,1210,1212,1213,1215,1217,1220,1221,1267,1268,1269,1288,1396,1496,1700,1701,1702,1703,1704,1705,1706,1707,1708,1709,1710,1711,1712,1713,1714,1715,1716,1717,1718,1719,1720,1721,1722,1723,1724,1730,1731,1732,1733,1741,1742,1743,1745,1746,1750,1751,1752,1753,1755,1756,1759,1761,1762,1763,1764,1765,1766,1767,1768,1769,1770,1771,1772,1773,1774,1781,1782,1811,1814,1818,1819,1822,1823,1826,1831,1832,1833,1834,1835,1836,1837,1838,1839,1840,1841,1842,1843,1844,1845,1846,1847,1848,1849,1850,1851,1852,1853,1854,1855,1856,1859,1860,1861,1862,1863,1864,1865,1866,1867,1868,1871,1872,1873,1874,1875,1876,1877,1878,1881,1882,1887,1892,1893,1899])
    vlan_list = sorted([1218])
    # vlan_list = sorted([113,184,195,932,940,943,990,1210,1212,1213,1217,1496,1715,1716,1717,1750,1867,1868,1871,1872,1873,1874])

    vlan_name_dict = vlan_names(vlan_list, credentials, hostname) # Returns dictionary with id:name mappings
    
    device.get_cdp()
    for vlan in vlan_list: 
        device.get_stp(vlan)
        device.get_macs(vlan)
    device.merge_info(vlan_name_dict) # Creates dictionary will all information collected in the methods above
    
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
        # print(json.dumps({obj.hostname: obj.vlan_mapping}, indent=4, sort_keys='True'))

    master_vlan_dict = {}
    for obj in master_obj_list:
        for (key, value) in obj.vlan_mapping.items():
            master_vlan_dict[key] = {'name': value['name'], 'devices': []}

    for obj in master_obj_list:
        for (key, value) in obj.vlan_mapping.items():
            if key in master_vlan_dict:
                master_vlan_dict[key]['devices'].extend(value['neighbors'])

    for (key, value) in master_vlan_dict.items():
        value['devices'] = list(set(value['devices']))

    # print(json.dumps(master_vlan_dict, indent=4, sort_keys='True'))    

    file_name = 'vlan_crawl.csv'
    print('Writing results to {}'.format(file_name))

    with open(file_name, 'w') as f:
        writer = csv.writer(f)

        header = ['VLAN', 'NAME', 'DEVICES']
        writer.writerow(header)

        for vlan in master_vlan_dict:
            line = [vlan, master_vlan_dict[vlan]['name'], None]
            writer.writerow(line)
            for device in master_vlan_dict[vlan]['devices']:
                line = [None, None, device]
                writer.writerow(line)

    print('\nThe script has finished successfully.\n')

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
        self.macs.update({vlan_id: results})

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

            self.cdp.update({n[4]: n[0]})

    def merge_info(self, vlan_name_dict):
        self.vlan_mapping = copy.deepcopy(self.stp)

        for k in self.vlan_mapping: self.vlan_mapping[k]['neighbors'] = []; self.vlan_mapping[k]['name'] = None
        for k in self.vlan_mapping:
            for interface in self.vlan_mapping[k]['interfaces']:
                if interface in self.cdp:
                    self.vlan_mapping[k]['neighbors'].append(self.cdp[interface])
            self.vlan_mapping[k]['name'] = vlan_name_dict[k]


if __name__ == '__main__':
    main()
