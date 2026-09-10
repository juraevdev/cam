#!/usr/bin/env python3
"""
Simulate a camera scan without OpenCV/EasyOCR.

Use this to verify backend entry/exit logging before wiring a real camera.

  python simulate_scan.py 01A123AA
  python simulate_scan.py 01A123AA --type entry
  python simulate_scan.py 01A123AA --type exit
  python simulate_scan.py 01A123AA --roundtrip
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import requests

from config import API_BASE_URL


def scan(plate: str, camera_type: str, api: str) -> dict:
    url = f"{api.rstrip('/')}/api/scan/"
    response = requests.post(
        url,
        json={"license_plate": plate, "camera_type": camera_type},
        timeout=5,
    )
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    data["_http_status"] = response.status_code
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate CV scan → /api/scan/")
    parser.add_argument("plate", help="License plate, e.g. 01A123AA")
    parser.add_argument(
        "--type",
        choices=("auto", "entry", "exit"),
        default="auto",
        help="Camera type (default auto)",
    )
    parser.add_argument("--api", default=API_BASE_URL)
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help="Entry then exit for the same plate (tests time_in/time_out)",
    )
    args = parser.parse_args()

    if args.roundtrip:
        print("--- ENTRY ---")
        entry = scan(args.plate, "entry", args.api)
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        time.sleep(1)
        print("--- EXIT ---")
        exit_data = scan(args.plate, "exit", args.api)
        print(json.dumps(exit_data, indent=2, ensure_ascii=False))

        ok = (
            entry.get("action") == "open_barrier"
            and exit_data.get("action") == "open_barrier"
            and exit_data.get("entry_log", {}).get("time_out")
        )
        print("\nRESULT:", "PASS ✓" if ok else "FAIL ✗")
        return 0 if ok else 1

    data = scan(args.plate, args.type, args.api)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0 if data.get("action") == "open_barrier" else 1


if __name__ == "__main__":
    sys.exit(main())
