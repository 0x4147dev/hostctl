#!/usr/bin/env python3

#
# ------ hostctl.py --------
#
# Author: 0x4147dev
#
# hostctl is a simple and useful tool for pentesters to manage
# /etc/hosts entries during an engagement.
#
# Every entry added by hostctl is tagged with a hidden marker
# comment (e.g. "# hostctl:acme-2026"), so you can always list or
# bulk-remove everything you added for a specific engagement without
# touching the system's original entries (localhost, etc.).
#
# --------------------
# LIBRARIES

import os
import re
import sys
import shutil
import tempfile
import ipaddress
import argparse

# --------------------
# VARIABLES

HOSTS_FILE = "/etc/hosts"
BACKUP_FILE = HOSTS_FILE + ".bak"

# Matches a trailing "# hostctl" or "# hostctl:tag" marker on a line
MARKER_RE = re.compile(r"#\s*hostctl(?::(\S+))?\s*$")

# --------------------
# LOW-LEVEL HELPERS


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
    """Write (append or atomically replace) the hosts file, or exit on failure."""
    if mode == "a":
        try:
            with open(HOSTS_FILE, "a") as f:
                f.writelines(lines)
        except OSError as e:
            print(f"[!] Error: cannot write to {HOSTS_FILE}: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Atomic replace: write to a temp file in the same directory, then
    # os.replace() it over the real file. This avoids leaving /etc/hosts
    # half-written if the process is killed mid-write.
    try:
        dir_name = os.path.dirname(HOSTS_FILE) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".hostctl_tmp_")
        with os.fdopen(fd, "w") as f:
            f.writelines(lines)
        shutil.copymode(HOSTS_FILE, tmp_path)
        os.replace(tmp_path, HOSTS_FILE)
    except OSError as e:
        print(f"[!] Error: cannot write to {HOSTS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


# --------------------
# MANAGED-LINE PARSING


def build_line(ip, domains, tag=None):
    """Build a hosts-file line for the given IP/domains, tagged as hostctl-managed."""
    marker = "# hostctl" + (f":{tag}" if tag else "")
    return f"{ip}\t" + "\t".join(domains) + f"\t{marker}\n"


def parse_managed_line(line):
    """Return {ip, domains, tag} if this line was added by hostctl, else None."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    code_part, sep, comment_part = line.partition("#")
    if not sep:
        return None

    match = MARKER_RE.search("#" + comment_part)
    if not match:
        return None

    tokens = code_part.split()
    if len(tokens) < 2:
        return None

    return {"ip": tokens[0], "domains": tokens[1:], "tag": match.group(1)}


# --------------------
# COMMANDS


def add_host(ip, domains, tag=None):
    """Add one or more domains for an IP, tagged for this engagement.

    Domains already present anywhere in the file (managed or not) are
    skipped individually. If a hostctl-managed line already exists for
    the same IP and tag, new domains are merged into it instead of
    creating a duplicate line.
    """
    check_root()
    validate_ip(ip)

    lines = read_hosts_file()

    existing_tokens = set()
    for line in lines:
        code_part = line.split("#", 1)[0]
        existing_tokens.update(code_part.split())

    already_present = [d for d in domains if d in existing_tokens]
    new_domains = [d for d in domains if d not in existing_tokens]

    if already_present:
        print(f"[!] Already present, skipped: {', '.join(already_present)}")

    if not new_domains:
        return

    new_lines = []
    merged = False
    for line in lines:
        parsed = parse_managed_line(line)
        if not merged and parsed and parsed["ip"] == ip and parsed["tag"] == tag:
            merged_domains = parsed["domains"] + new_domains
            new_lines.append(build_line(ip, merged_domains, tag))
            merged = True
        else:
            new_lines.append(line)

    if not merged:
        new_lines.append(build_line(ip, new_domains, tag))

    backup_hosts_file()
    write_hosts_file(new_lines, mode="w")

    tag_info = f" [tag: {tag}]" if tag else ""
    print(f"[+] Added successfully: {ip} -> {', '.join(new_domains)}{tag_info}")


def remove_host(domains):
    """Remove the given domains wherever they appear in the hosts file.

    Only the matching domain tokens are stripped from each line; other
    domains sharing the same line (and any hostctl tag) are preserved.
    A line is dropped entirely only if no domains remain on it.
    """
    check_root()

    domains_set = set(domains)
    lines = read_hosts_file()

    new_lines = []
    removed = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        code_part, sep, comment_part = line.partition("#")
        tokens = code_part.split()
        if len(tokens) < 2:
            new_lines.append(line)
            continue

        ip, line_domains = tokens[0], tokens[1:]
        matched = [d for d in line_domains if d in domains_set]
        if not matched:
            new_lines.append(line)
            continue

        removed.update(matched)
        remaining = [d for d in line_domains if d not in domains_set]

        if remaining:
            comment_suffix = f"\t#{comment_part}" if sep else "\n"
            new_lines.append(f"{ip}\t" + "\t".join(remaining) + comment_suffix)
        # else: no domains left on this line, drop it entirely

    not_found = domains_set - removed
    if not_found:
        print(f"[!] Not found, skipped: {', '.join(not_found)}")

    if not removed:
        return

    backup_hosts_file()
    write_hosts_file(new_lines, mode="w")

    print(f"[+] Removed successfully: {', '.join(removed)}")


def list_hosts(tag=None, show_all=False):
    """List hostctl-managed entries (optionally filtered by tag), or the whole file."""
    lines = read_hosts_file()

    if show_all:
        for line in lines:
            if line.strip():
                print(line.rstrip("\n"))
        return

    found = False
    for line in lines:
        parsed = parse_managed_line(line)
        if not parsed:
            continue
        if tag is not None and parsed["tag"] != tag:
            continue
        found = True
        tag_label = parsed["tag"] or "(no tag)"
        domains_str = ", ".join(parsed["domains"])
        print(f"{parsed['ip']:<16} {domains_str:<45} [{tag_label}]")

    if not found:
        scope = f" for tag '{tag}'" if tag else ""
        print(f"[i] No hostctl-managed entries found{scope}.")


def clean_hosts(tag=None, purge_all=False):
    """Remove every hostctl-managed entry, or only those matching a tag."""
    check_root()

    lines = read_hosts_file()
    new_lines = []
    removed_count = 0
    removed_domains = []

    for line in lines:
        parsed = parse_managed_line(line)
        if parsed and (purge_all or parsed["tag"] == tag):
            removed_count += 1
            removed_domains.extend(parsed["domains"])
            continue
        new_lines.append(line)

    if removed_count == 0:
        scope = "any tag" if purge_all else f"tag '{tag}'"
        print(f"[i] No hostctl-managed entries found for {scope}.")
        return

    backup_hosts_file()
    write_hosts_file(new_lines, mode="w")

    print(f"[+] Cleaned {removed_count} entrie(s): {', '.join(removed_domains)}")


# --------------------
# MAIN

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manage /etc/hosts entries, with per-engagement tagging."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'add' command
    parser_add = subparsers.add_parser("add", help="Add one or more host entries")
    parser_add.add_argument("ip", help="IP address (e.g. 10.10.10.10)")
    parser_add.add_argument(
        "domains",
        nargs="+",
        help="One or more domain names (e.g. target.local api.target.local)",
    )
    parser_add.add_argument(
        "-t", "--tag",
        help="Tag this entry with an engagement/client name (e.g. acme-2026)",
    )

    # 'remove' command
    parser_remove = subparsers.add_parser(
        "remove", help="Remove one or more host entries by domain"
    )
    parser_remove.add_argument("domains", nargs="+", help="Domain name(s) to remove")

    # 'list' command
    parser_list = subparsers.add_parser(
        "list", help="List hostctl-managed entries (optionally by tag)"
    )
    parser_list.add_argument("-t", "--tag", help="Only list entries with this tag")
    parser_list.add_argument(
        "-a", "--all", action="store_true", dest="show_all",
        help="Show the full hosts file, not just hostctl-managed entries",
    )

    # 'clean' command
    parser_clean = subparsers.add_parser(
        "clean", help="Bulk-remove hostctl-managed entries (by tag or all)"
    )
    clean_group = parser_clean.add_mutually_exclusive_group(required=True)
    clean_group.add_argument("-t", "--tag", help="Remove all entries with this tag")
    clean_group.add_argument(
        "-a", "--all", action="store_true", dest="purge_all",
        help="Remove every hostctl-managed entry, regardless of tag",
    )

    args = parser.parse_args()

    if args.command == "add":
        add_host(args.ip, args.domains, tag=args.tag)
    elif args.command == "remove":
        remove_host(args.domains)
    elif args.command == "list":
        list_hosts(tag=args.tag, show_all=args.show_all)
    elif args.command == "clean":
        clean_hosts(tag=args.tag, purge_all=args.purge_all)
