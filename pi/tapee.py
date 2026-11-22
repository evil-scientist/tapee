#!/usr/bin/env python3
"""Print a ticket on the thermal printer each time the button is pressed.

Short press: print. Hold for 5 s: shut the Pi down safely.
Usage: python3 tapee.py [--port /dev/serial0] [--baud 9600] [--pin 17]
"""
import argparse
import subprocess
import threading
import time
from signal import pause

import serial
from gpiozero import Button

ESC, GS = b"\x1b", b"\x1d"


def print_ticket(port, baud):
    # Placeholder design. Replace the body of this function once we pick a format.
    with serial.Serial(port, baud, timeout=1) as p:
        def out(data, pause=0.05):
            # The printer has a small buffer and usually no flow control, so go slowly.
            p.write(data)
            p.flush()
            time.sleep(pause)

        def line(text=""):
            out(text.encode("ascii", "replace") + b"\n", 0.1)

        out(ESC + b"@", 0.5)  # reset
        out(ESC + b"7" + bytes([11, 120, 40]))  # heating, Adafruit defaults
        out(ESC + b"a" + b"\x01")  # center
        out(GS + b"!" + b"\x11")  # double width + height
        line("TAPEE")
        out(GS + b"!" + b"\x00")
        line(time.strftime("%Y-%m-%d %H:%M:%S"))
        line("-" * 32)
        line("Button press OK")
        out(ESC + b"d" + b"\x04", 0.5)  # feed 4 lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--pin", type=int, default=17, help="BCM GPIO number of the button")
    ap.add_argument("--hold", type=float, default=5, help="seconds to hold for shutdown")
    args = ap.parse_args()

    # Button between the GPIO pin and GND; the internal pull-up keeps it high when open.
    button = Button(args.pin, pull_up=True, bounce_time=0.05, hold_time=args.hold)
    busy = threading.Lock()
    held = False

    def run_print():
        try:
            print_ticket(args.port, args.baud)
            print("Printed ticket", flush=True)
        except Exception as e:
            print(f"Print failed: {e}", flush=True)
        finally:
            busy.release()

    def on_press():
        nonlocal held
        held = False

    def on_held():
        nonlocal held
        held = True
        print("Button held, shutting down", flush=True)
        subprocess.run(["sudo", "-n", "systemctl", "poweroff"], check=False)

    def on_release():
        # Ignore presses while a ticket is still printing.
        if held or not busy.acquire(blocking=False):
            return
        threading.Thread(target=run_print, daemon=True).start()

    button.when_pressed = on_press
    button.when_held = on_held
    button.when_released = on_release
    print(f"Waiting for button on GPIO{args.pin}, printer on {args.port} @ {args.baud}", flush=True)
    pause()


if __name__ == "__main__":
    main()
