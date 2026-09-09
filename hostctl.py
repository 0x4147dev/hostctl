#!/usr/bin/env python3

#
# ------ hosts.py --------
#
# Author: 0x4147
#
# hosts is a simple ad useful tool for pentesters to add hosts into /etc/hosts file.
#
# --------------------
# LIBRARIES

import os
import sys
import argparse

# --------------------
# VARIABLES

HOSTS_FILE = "/etc/hosts"

# --------------------
# INIT

def check_root():
    if os.geteuid() != 0:
        print("[!] Error: run the script with sudo!")
        sys.exit(1)

def add_host(ip, domain):
    check_root()

    entry = f"{ip}\t{domain}\n"
    #
    # Check if the domain name exists
    #
    with open(HOSTS_FILE, "r") as f:
        content = f.readlines()

    for line in content:
        if domain in line.split():
            print(f"The domain {domain} exists in {HOSTS_FILE}.")
            return
            
    # Add new domain into file
    #
    with open(HOSTS_FILE, "a") as f:
        f.write(entry)

    print(f"Added successfully: {ip} -> {domain}")

def remove_host(domain):
    check_root()

    with open(HOSTS_FILE, "r") as f:
        lines = f.readlines()

    new_lines = []
    removed = False

    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            tokens = line.split()
            if domain in tokens:
                removed = True
                continue
        new_lines.append(line)

    if not removed:
        print(f"[!] Domain '{domain}' not found in {HOSTS_FILE}.")
        return

    with open(HOSTS_FILE, "w") as f:
        f.writelines(new_lines)

    print(f"[+] Remove successfully: {domain}")
    
# --------------------
# MAIN
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage /etc/hosts entries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'Add' command
    parser_add = subparsers.add_parser("add", help="Add a host entry")
    parser_add.add_argument("ip", help="IP address (e.g. 127.0.0.1)")
    parser_add.add_argument("domain", help="Domain name (e.g. target.local)")

    # 'Remove' command
    parser_remove = subparsers.add_parser("remove", help="Remove a host entry by domain")
    parser_remove.add_argument("domain", help="Domain name to remove")

    args = parser.parse_args()

    
    if args.command == "add":
        add_host(args.ip, args.domain)
    elif args.command == "remove":
        remove_host(args.domain)
