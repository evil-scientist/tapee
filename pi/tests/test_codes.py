#!/usr/bin/env python3
"""Print scannable barcodes and QR codes on a DP-EH500 / Adafruit-style thermal printer.

Each section is labelled so you can see which command styles the firmware supports.
Usage: .venv/bin/python pi/tests/test_codes.py [--port /dev/ttyUSB0] [--baud 9600]
"""
import argparse
import time

import segno
import serial

ESC, GS, DC2 = b"\x1b", b"\x1d", b"\x12"
MAX_WIDTH_BYTES = 48  # 384 dots across the head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    args = ap.parse_args()

    stamp = time.strftime("%H%M%S")
    qr_text = f"Thermal printer QR OK {time.strftime('%Y-%m-%d %H:%M:%S')}"

    with serial.Serial(args.port, args.baud, timeout=1) as p:
        def out(data, pause=0.05):
            # The printer has a small buffer and usually no flow control, so go slowly.
            p.write(data)
            p.flush()
            time.sleep(pause)

        def line(text=""):
            out(text.encode("ascii") + b"\n", 0.1)

        def barcode_settings():
            out(GS + b"h" + bytes([80]))  # height in dots
            out(GS + b"w" + bytes([3]))  # module width
            out(GS + b"H" + bytes([2]))  # human-readable text below

        def bitmap(rows, width_bytes):
            # DC2 * r n: Adafruit raster bitmap, at most 255 rows per block.
            for start in range(0, len(rows), 255):
                block = rows[start:start + 255]
                out(DC2 + b"*" + bytes([len(block), width_bytes]), 0)
                for row in block:
                    out(row, 0.03)  # roughly one dot-line print time per row
            time.sleep(0.3)

        out(ESC + b"@", 0.5)  # reset
        out(ESC + b"7" + bytes([11, 120, 40]))  # heating, Adafruit defaults
        out(ESC + b"a" + b"\x01")  # center everything

        line("BARCODE / QR TEST")
        line("-" * 32)

        # Format B (standard ESC/POS, Adafruit firmware >= 2.68): GS k m n data
        line("1) CODE128 (GS k 73)")
        barcode_settings()
        data = b"{B" + f"TEST{stamp}".encode()
        out(GS + b"k" + bytes([73, len(data)]) + data, 1.0)
        line()

        line("2) CODE39 (GS k 69)")
        barcode_settings()
        data = f"TEST{stamp}".encode()
        out(GS + b"k" + bytes([69, len(data)]) + data, 1.0)
        line()

        line("3) EAN13 (GS k 67)")
        barcode_settings()
        data = b"400638133393"  # printer adds the check digit (1)
        out(GS + b"k" + bytes([67, len(data)]) + data, 1.0)
        line()

        # Format A (older firmware): GS k m data NUL
        line("4) CODE39 old-style (GS k 4)")
        barcode_settings()
        out(GS + b"k" + bytes([4]) + f"OLD{stamp}".encode() + b"\x00", 1.0)
        line()
        line("-" * 32)

        # QR rendered on the PC and sent as a bitmap. Works on any firmware with DC2 *.
        line("5) QR as bitmap (DC2 *)")
        qr = segno.make(qr_text, error="m")
        scale = min(8, (MAX_WIDTH_BYTES * 8) // (qr.symbol_size(border=2)[0]))
        matrix = [list(r) for r in qr.matrix_iter(scale=scale, border=2)]
        width_bytes = (len(matrix[0]) + 7) // 8
        rows = []
        for r in matrix:
            bits = r + [0] * (width_bytes * 8 - len(r))
            rows.append(bytes(
                sum(bits[i + b] << (7 - b) for b in range(8)) for i in range(0, len(bits), 8)
            ))
        bitmap(rows, width_bytes)
        line(qr_text[:32])
        line(qr_text[32:])
        line()

        # Native QR (GS ( k). Many cheap firmwares lack it; blank or junk here is expected then.
        line("6) QR native (GS ( k)")
        payload = qr_text.encode()

        def gs_k(fn_and_args):
            out(GS + b"(k" + len(fn_and_args).to_bytes(2, "little") + fn_and_args, 0.1)

        gs_k(b"1A2\x00")  # model 2
        gs_k(b"1C\x06")  # module size 6
        gs_k(b"1E1")  # error correction M
        gs_k(b"1P0" + payload)  # store data
        gs_k(b"1Q0")  # print
        time.sleep(2)
        line()
        line("-" * 32)
        line("Scan each code and compare.")
        out(ESC + b"d" + b"\x04", 0.5)  # feed 4 lines

    print(f"Sent barcode/QR test. QR should read: {qr_text!r}")
    print(f"Barcodes should read: TEST{stamp}, 4006381333931, OLD{stamp}")


if __name__ == "__main__":
    main()
