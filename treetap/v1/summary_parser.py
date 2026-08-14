"""
Parser for Version 1 TreeTap ASCII serial stream data and log files (.down, .txt, .log, etc.).
"""

from typing import List, Dict, Any, Tuple, Optional
import datetime
import logging

from treetap.backend.models import Measurement, Tap, TapMetadata, TapSignal

logger = logging.getLogger(__name__)


def parse_v1_text(
    text_data: str,
    source_name: str = "v1.down",
    separation_cm: float = 0.0,
) -> List[Tuple[Measurement, List[Tuple[Tap, TapMetadata, TapSignal]]]]:
    """
    Parses TreeTap V1 ASCII serial output or log file text into Measurement sessions and Tap tuples.

    Returns a list of tuples: [(Measurement, [(Tap, TapMetadata, TapSignal), ...]), ...]
    """
    lines = [line.strip() for line in text_data.splitlines() if line.strip()]
    if not lines:
        return []

    unit_id = 0
    firmware_ver = "v1"

    # Header parsing
    data_lines = []
    for line in lines:
        if line.lower().startswith("treetap"):
            firmware_ver = line
        elif "unit" in line.lower() and "taps" in line.lower():
            # Example: "Unit 0, Taps 1364"
            parts = line.split(",")
            for p in parts:
                if "unit" in p.lower():
                    try:
                        unit_id = int(p.lower().replace("unit", "").strip())
                    except ValueError:
                        pass
        elif "," in line:
            # Data record line
            data_lines.append(line)

    if not data_lines:
        return []

    # Group record lines by tree/session ID (col1)
    sessions: Dict[int, List[Dict[str, Any]]] = {}

    for idx, line in enumerate(data_lines):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue

        try:
            seq_num = int(parts[0])
            tree_id = int(parts[1])
            tap_num = int(parts[2])
            direction = parts[3].upper()

            speed_raw = parts[4]
            is_flagged = "*" in speed_raw
            speed_val_str = speed_raw.replace("*", "").strip()
            speed_us = float(speed_val_str) if speed_val_str else 0.0

            q_metric_1 = int(parts[5])
            q_metric_2 = int(parts[6])

            if tree_id not in sessions:
                sessions[tree_id] = []

            sessions[tree_id].append({
                "seq_num": seq_num,
                "tree_id": tree_id,
                "tap_num": tap_num,
                "direction": direction,
                "speed_us": speed_us,
                "is_flagged": is_flagged,
                "quality_metric_1": q_metric_1,
                "quality_metric_2": q_metric_2,
            })
        except Exception as err:
            logger.warning(f"Error parsing V1 data line #{idx+1} '{line}': {err}")
            continue

    results = []

    for tree_id, taps_list in sorted(sessions.items()):
        meas_id = tree_id
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meas = Measurement(
            meas_id=meas_id,
            meas_note=f"V1 Tree {tree_id} (Unit {unit_id})",
            device_version="v1",
        )

        tap_tuples = []
        for t_dict in taps_list:
            tap_id = t_dict["seq_num"]

            flag_str = " [FLAGGED]" if t_dict["is_flagged"] else ""
            tap = Tap(
                tap_id=tap_id,
                meas_id=meas_id,
                tap_time=now_str,
                speed_us=t_dict["speed_us"],
                separation_cm=separation_cm,
                meas_note=f"Tap {t_dict['tap_num']} ({t_dict['direction']}){flag_str}",
            )

            meta = TapMetadata(
                tap_id=tap_id,
                firmware_version=firmware_ver,
                device_version="v1",
                gain=None,
                v1direction=t_dict["direction"],
                v1col5=t_dict["quality_metric_1"],
                v1col6=t_dict["quality_metric_2"],
                tap_note=f"Dir={t_dict['direction']}, Col5={t_dict['quality_metric_1']}, Col6={t_dict['quality_metric_2']}",
                source_file=source_name,
            )

            sig = TapSignal(
                tap_id=tap_id,
                ch1_samples=[],
                ch2_samples=[],
            )

            tap_tuples.append((tap, meta, sig))

        results.append((meas, tap_tuples))

    return results
