"""
Parser for Version 2 summary CSV files (treetap-*.csv).
Handles edge cases such as unquoted commas in notes and multi-line notes.
"""

from typing import List, Tuple, Dict
import glob
import os

from treetap.backend.models import Measurement, Tap


def parse_summary_file(filepath: str) -> Tuple[List[Measurement], List[Tap]]:
    """
    Parses a single treetap-*.csv summary file and returns extracted Measurement and Tap models.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    taps_dict: Dict[int, Tap] = {}
    meas_dict: Dict[int, Measurement] = {}

    i = 1  # Skip header line
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        if not line:
            i += 1
            continue

        combined_line = line
        while i + 1 < len(lines):
            parts = combined_line.split(",")
            if len(parts) >= 6:
                try:
                    int(parts[-4])        # tap_id
                    float(parts[-2])      # separation_cm
                    float(parts[-1])      # speed_us
                    break
                except ValueError:
                    pass
            i += 1
            combined_line += "\n" + lines[i].rstrip("\r\n")

        parts = combined_line.split(",")
        if len(parts) < 6:
            i += 1
            continue

        try:
            meas_id = int(float(parts[0]))
            tap_id = int(parts[-4])
            tap_time_str = parts[-3].strip()
            sep_cm = float(parts[-2])
            speed_us = float(parts[-1])
            meas_note = ",".join(parts[1:-4]).strip()

            if meas_id not in meas_dict:
                meas_dict[meas_id] = Measurement(
                    meas_id=meas_id,
                    meas_note=meas_note,
                    device_version="v2",
                )

            taps_dict[tap_id] = Tap(
                tap_id=tap_id,
                meas_id=meas_id,
                tap_time=tap_time_str,
                separation_cm=sep_cm,
                speed_us=speed_us,
                meas_note=meas_note,
            )
        except (ValueError, IndexError):
            pass

        i += 1

    return list(meas_dict.values()), list(taps_dict.values())


def parse_summary_directory(data_dir: str) -> Tuple[List[Measurement], List[Tap]]:
    """
    Scans a directory for all treetap-*.csv files, deduplicates entries,
    and returns combined Measurement and Tap lists.
    """
    pattern = os.path.join(data_dir, "treetap-*.csv")
    summary_files = sorted(glob.glob(pattern))

    all_taps: Dict[int, Tap] = {}
    all_meas: Dict[int, Measurement] = {}

    for sf in summary_files:
        meas_list, tap_list = parse_summary_file(sf)
        for m in meas_list:
            all_meas[m.meas_id] = m
        for t in tap_list:
            all_taps[t.tap_id] = t

    return list(all_meas.values()), list(all_taps.values())
