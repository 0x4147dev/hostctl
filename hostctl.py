#!/usr/bin/env python3

#
# ------ hostctl.py --------
#
# Author: 0x4147dev
#
# hostctl is a simple and useful tool for pentesters to add and
# remove entries in the /etc/hosts file.
#
# --------------------
# LIBRARIES

import os
import sys
import shutil
import ipaddress
import argparse

# --------------------
# VARIABLES

HOSTS_FILE = "/etc/hosts"
BACKUP_FILE = HOSTS_FILE + ".bak"

# --------------------
# INIT


def check_root():
    """Exit if the script is not run with root privileges."""
    if os.geteuid() != 0:
        print("[!] Error: run the script with sudo!", file=sys.stderr)
        sys.exit(1)


def validate_ip(ip):
    """Exit if the given string is not a valid IPv4/IPv6 address."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        print(f"[!] Error: '{ip}' is not a valid IP address.", file=sys.stderr)
        sys.exit(1)


def backup_hosts_file():
    """Create a backup copy of the hosts file before modifying it."""
    try:
        shutil.copy(HOSTS_FILE, BACKUP_FILE)
    except OSError as e:
        print(f"[!] Warning: could not create backup ({e}).", file=sys.stderr)


def read_hosts_file():
    """Read and return all lines of the hosts file, or exit on failure."""
    try:
        with open(HOSTS_FILE, "r") as f:
            return f.readlines()
    except OSError as e:
        print(f"[!] Error: cannot read {HOSTS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def write_hosts_file(lines, mode="w"):
    """Write (or append) lines to the hosts file, or exit on failure."""
    try:
        with open(HOSTS_FILE, mode) as f:
            f.writelines(lines)
    except OSError as e:
        print(f"[!] Error: cannot write to {HOSTS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def add_host(ip, domain):
    """Add a new IP -> domain entry to the hosts file."""
    check_root()
    validate_ip(ip)

    entry = f"{ip}\t{domain}\n"

    # Check if the domain name already exists
    content = read_hosts_file()
    for line in content:
        if domain in line.split():
            print(f"[!] The domain '{domain}' already exists in {HOSTS_FILE}.")
            return

    backup_hosts_file()
    write_hosts_file([entry], mode="a")

    print(f"[+] Added successfully: {ip} -> {domain}")


def remove_host(domain):
    """Remove any line containing the given domain from the hosts file."""
    check_root()

    lines = read_hosts_file()

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

    backup_hosts_file()
    write_hosts_file(new_lines, mode="w")

    print(f"[+] Removed successfully: {domain}")


# --------------------
# MAIN

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage /etc/hosts entries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'add' command
    parser_add = subparsers.add_parser("add", help="Add a host entry")
    parser_add.add_argument("ip", help="IP address (e.g. 127.0.0.1)")
    parser_add.add_argument("domain", help="Domain name (e.g. target.local)")

    # 'remove' command
    parser_remove = subparsers.add_parser("remove", help="Remove a host entry by domain")
    parser_remove.add_argument("domain", help="Domain name to remove")

    args = parser.parse_args()

    if args.command == "add":
        add_host(args.ip, args.domain)
    elif args.command == "remove":
        remove_host(args.domain)
