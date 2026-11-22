#!/usr/bin/env python3
"""Write first-boot settings onto a freshly flashed Raspberry Pi OS boot partition.

Does what Raspberry Pi Imager's customisation step does: cloud-init user, SSH, Wi-Fi,
hostname, time zone. Also turns on the GPIO UART and keeps the console off it.
Usage: python3 firstboot.py BOOT_DIR SETTINGS_FILE
       python3 firstboot.py --check SETTINGS_FILE   (validate only, write nothing)
"""
import hashlib
import json
import os
import pwd
import subprocess
import sys

# Groups Raspberry Pi OS gives its first user.
GROUPS = "adm,dialout,cdrom,sudo,audio,video,plugdev,games,users,input,render,netdev,gpio,i2c,spi"


def load_settings(path):
    settings = {}
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip().strip('"').strip("'")
    return settings


def q(value):
    # JSON strings are valid YAML scalars and handle quotes and spaces in SSIDs.
    return json.dumps(value)


def main():
    boot, settings_file = sys.argv[1], sys.argv[2]
    s = load_settings(settings_file)
    for key in ("HOSTNAME", "PI_USER", "WIFI_SSID", "WIFI_PASSWORD", "WIFI_COUNTRY", "TIMEZONE", "KEYMAP"):
        if not s.get(key):
            sys.exit(f"{settings_file}: {key} is empty")

    keyfile = s.get("SSH_PUBKEY_FILE", "")
    if keyfile.startswith("~/") and os.environ.get("SUDO_USER"):
        # Under sudo, ~ means root's home; use the home of whoever ran sudo.
        keyfile = os.path.join(pwd.getpwnam(os.environ["SUDO_USER"]).pw_dir, keyfile[2:])
    keyfile = os.path.expanduser(keyfile)
    if keyfile and not os.path.isfile(keyfile):
        sys.exit(f"{settings_file}: SSH_PUBKEY_FILE {keyfile} not found")
    pubkey = open(keyfile).read().strip() if keyfile else ""
    password = s.get("PI_PASSWORD", "")
    if not pubkey and not password:
        sys.exit(f"{settings_file}: set PI_PASSWORD or SSH_PUBKEY_FILE, or you can't log in")

    user = [
        f"  - name: {q(s['PI_USER'])}",
        f"    groups: {GROUPS}",
        "    shell: /bin/bash",
        "    sudo: ALL=(ALL) NOPASSWD:ALL",
    ]
    if password:
        hashed = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input=password,
                                capture_output=True, text=True, check=True).stdout.strip()
        user += ["    lock_passwd: false", f"    passwd: {q(hashed)}"]
    else:
        user += ["    lock_passwd: true"]
    if pubkey:
        user += ["    ssh_authorized_keys:", f"      - {q(pubkey)}"]

    country = s["WIFI_COUNTRY"].upper()
    user_data = "\n".join([
        "#cloud-config",
        f"hostname: {q(s['HOSTNAME'])}",
        "manage_etc_hosts: true",
        f"timezone: {q(s['TIMEZONE'])}",
        "keyboard:",
        "  model: pc105",
        f"  layout: {q(s['KEYMAP'])}",
        "users:",
        *user,
        f"ssh_pwauth: {'true' if password else 'false'}",
        "runcmd:",
        f"  - [raspi-config, nonint, do_wifi_country, {q(country)}]",
        "  - [rfkill, unblock, wifi]",
        "  - [systemctl, enable, --now, ssh]",
        "",
    ])

    # Store the WPA key as its 64-hex PSK so the plain password isn't left on the card.
    ssid, wifi_pw = s["WIFI_SSID"], s["WIFI_PASSWORD"]
    if not 8 <= len(wifi_pw) <= 63:
        sys.exit(f"{settings_file}: WIFI_PASSWORD must be 8 to 63 characters")
    psk = hashlib.pbkdf2_hmac("sha1", wifi_pw.encode(), ssid.encode(), 4096, 32).hex()
    network_config = "\n".join([
        "network:",
        "  version: 2",
        "  wifis:",
        "    wlan0:",
        "      dhcp4: true",
        "      optional: true",
        f"      regulatory-domain: {q(country)}",
        "      access-points:",
        f"        {q(ssid)}:",
        f"          password: {q(psk)}",
        "",
    ])

    if boot == "--check":
        print(f"Settings OK: user {s['PI_USER']}, host {s['HOSTNAME']}.local, Wi-Fi {ssid}, "
              f"login by {'password and key' if password and pubkey else 'password' if password else 'key'}")
        return

    with open(os.path.join(boot, "user-data"), "w") as f:
        f.write(user_data)
    with open(os.path.join(boot, "network-config"), "w") as f:
        f.write(network_config)
    open(os.path.join(boot, "ssh"), "w").close()

    # Keep boot messages off the printer.
    cmdline_path = os.path.join(boot, "cmdline.txt")
    cmdline = open(cmdline_path).read().split()
    cmdline = [arg for arg in cmdline if not arg.startswith("console=serial0")]
    with open(cmdline_path, "w") as f:
        f.write(" ".join(cmdline) + "\n")

    # GPIO 14/15 get the PL011 UART instead of Bluetooth (same as setup.sh).
    config_path = os.path.join(boot, "config.txt")
    config = open(config_path).read()
    extra = [line for line in ("enable_uart=1", "dtoverlay=disable-bt") if line not in config.splitlines()]
    if extra:
        with open(config_path, "a") as f:
            f.write("\n".join(extra) + "\n")

    print(f"Wrote first-boot settings: user {s['PI_USER']}, host {s['HOSTNAME']}.local, Wi-Fi {ssid}")


if __name__ == "__main__":
    main()
