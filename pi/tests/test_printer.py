#!/usr/bin/env python3
"""Print a test page on a DP-EH500 / Adafruit-style TTL thermal printer.

Usage: python3 test_printer.py [--port /dev/ttyUSB0] [--baud 9600]
"""
import argparse
import time

import serial

ESC, GS = b"\x1b", b"\x1d"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    args = ap.parse_args()

    with serial.Serial(args.port, args.baud, timeout=1) as p:
        def out(data, pause=0.05):
            # The printer has a small buffer and usually no flow control, so go slowly.
            p.write(data)
            p.flush()
            time.sleep(pause)

        def line(text=""):
            out(text.encode("ascii") + b"\n", 0.1)

        out(ESC + b"@", 0.5)  # reset
        # Heating: max dots=11 (x8), heat time=120 (x10us), interval=40 (x10us). Adafruit defaults.
        out(ESC + b"7" + bytes([11, 120, 40]))

        # Ask for paper status (DLE EOT 4). Many units have no RX wire or ignore this.
        p.reset_input_buffer()
        out(b"\x10\x04\x04", 0.3)
        reply = p.read(1)
        status = f"0x{reply[0]:02x}" if reply else "no reply (normal if RX not wired)"

        out(ESC + b"a" + b"\x01")  # center
        out(GS + b"!" + b"\x11")  # double width + height
        line("PRINTER TEST")
        out(GS + b"!" + b"\x00")
        line(f"{args.port} @ {args.baud} baud")
        line(time.strftime("%Y-%m-%d %H:%M:%S"))
        out(ESC + b"a" + b"\x00")  # left
        line("-" * 32)

        line("Normal text")
        out(ESC + b"E" + b"\x01"); line("Bold text"); out(ESC + b"E" + b"\x00")
        out(ESC + b"-" + b"\x01"); line("Underlined text"); out(ESC + b"-" + b"\x00")
        out(GS + b"B" + b"\x01"); line(" Inverse text "); out(GS + b"B" + b"\x00")
        out(GS + b"!" + b"\x01"); line("Tall text"); out(GS + b"!" + b"\x00")
        out(GS + b"!" + b"\x10"); line("Wide text"); out(GS + b"!" + b"\x00")
        line("-" * 32)

        line("Character set:")
        chars = "".join(chr(c) for c in range(0x20, 0x7F))
        for i in range(0, len(chars), 32):
            line(chars[i:i + 32])
        line("-" * 32)

        # Full-width inverse bands show uneven heating or dead dots in the head.
        line("Darkness check (should be solid):")
        out(GS + b"B" + b"\x01")
        for _ in range(3):
            line(" " * 32)
        out(GS + b"B" + b"\x00")
        line("-" * 32)

        line(f"Paper status: {status}")
        line("If you can read this, it works!")
        out(ESC + b"d" + b"\x04", 0.5)  # feed 4 lines

    print(f"Sent test page to {args.port} at {args.baud} baud. Paper status: {status}")


if __name__ == "__main__":
    main()
