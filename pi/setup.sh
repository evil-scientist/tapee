#!/usr/bin/env bash
# One-time setup on the Pi: GPIO serial port, Python packages, and the button service.
# Run it from your normal user in the folder that holds tapee.py:  sudo bash setup.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo: sudo bash setup.sh"
    exit 1
fi
APP_USER=${SUDO_USER:?Run with sudo from your normal user, not as root}
APP_DIR=$(cd "$(dirname "$0")" && pwd)
CONFIG=/boot/firmware/config.txt

apt-get update
apt-get install -y python3-serial python3-gpiozero python3-lgpio

# Turn on the UART on GPIO 14/15 and take the Linux console off it,
# otherwise boot messages come out on the paper.
raspi-config nonint do_serial_hw 0
raspi-config nonint do_serial_cons 1

# On a Zero W / Zero 2 W, Bluetooth owns the good UART (PL011) and GPIO gets the mini UART,
# whose baud rate follows the CPU clock. Give the PL011 to GPIO instead.
grep -q '^dtoverlay=disable-bt' "$CONFIG" || echo 'dtoverlay=disable-bt' >> "$CONFIG"
systemctl disable hciuart.service 2>/dev/null || true

usermod -aG dialout,gpio "$APP_USER"

sed -e "s|@USER@|$APP_USER|g" -e "s|@DIR@|$APP_DIR|g" \
    "$APP_DIR/tapee.service" > /etc/systemd/system/tapee.service
systemctl daemon-reload
systemctl enable tapee.service

echo "Done. Reboot to apply the serial changes: sudo reboot"
