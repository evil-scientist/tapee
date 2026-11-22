#!/usr/bin/env bash
# Write Raspberry Pi OS to an SD card with dd, then add first-boot settings from pi/sdcard/flash.env.
# Usage: sudo bash pi/sdcard/flash.sh /dev/sdX path/to/raspios-lite.img[.xz]
set -euo pipefail

DEV=${1:?Usage: sudo bash pi/sdcard/flash.sh /dev/sdX image.img[.xz]}
IMG=${2:?Usage: sudo bash pi/sdcard/flash.sh /dev/sdX image.img[.xz]}
DIR=$(cd "$(dirname "$0")" && pwd)
SETTINGS="$DIR/flash.env"

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }
[[ -f $SETTINGS ]] || { echo "Missing $SETTINGS. Copy flash.env.example and fill it in."; exit 1; }
[[ -f $IMG ]] || { echo "Image $IMG not found."; exit 1; }
[[ -b $DEV ]] || { echo "$DEV is not a block device."; exit 1; }

# Only whole, removable disks up to 256 GB, and never the disk holding /.
[[ $(lsblk -dno TYPE "$DEV") == disk ]] || { echo "$DEV is not a whole disk (use /dev/sdX, not /dev/sdX1)."; exit 1; }
[[ $(lsblk -dno RM "$DEV" | tr -d ' ') == 1 || $(lsblk -dno TRAN "$DEV") == usb ]] \
    || { echo "$DEV is not removable. Refusing."; exit 1; }
size=$(lsblk -dbno SIZE "$DEV")
(( size <= 256 * 1000**3 )) || { echo "$DEV is larger than 256 GB. Refusing."; exit 1; }
root_disk=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")
[[ /dev/$root_disk != "$DEV" ]] || { echo "$DEV holds this computer's root filesystem. Refusing."; exit 1; }

# Check the settings before erasing anything.
python3 -I "$DIR/firstboot.py" --check "$SETTINGS"

echo
lsblk -o NAME,SIZE,TRAN,MODEL,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
echo
read -rp "Everything on $DEV will be erased. Type the device name ($DEV) to continue: " answer
[[ $answer == "$DEV" ]] || { echo "Cancelled."; exit 1; }

for part in $(lsblk -lnpo NAME "$DEV" | tail -n +2); do
    umount "$part" 2>/dev/null || true
done

echo "Writing $IMG to $DEV..."
if [[ $IMG == *.xz ]]; then
    xz -dc "$IMG" | dd of="$DEV" bs=4M conv=fsync iflag=fullblock status=progress
else
    dd if="$IMG" of="$DEV" bs=4M conv=fsync status=progress
fi
sync
partprobe "$DEV" 2>/dev/null || true
udevadm settle

BOOT_PART=$(lsblk -lnpo NAME "$DEV" | sed -n 2p)
MNT=$(mktemp -d)
mount "$BOOT_PART" "$MNT"
trap 'umount "$MNT" 2>/dev/null || true; rmdir "$MNT"' EXIT
python3 -I "$DIR/firstboot.py" "$MNT" "$SETTINGS"
umount "$MNT"
sync

echo "Done. Remove the card, put it in the Pi and power it on."
