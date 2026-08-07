"""
Archive and directory scanner for Version 2 individual tap signal CSV files.
Parses signal header metadata and time-series channel ADC counts.
"""

from typing import List, Tuple, Dict, Optional, Any
import glob
import os
import zipfile

from treetap.backend.models import TapMetadata, TapSignal


class TapSignalArchiveReader:
    """
    Scans zip archives and directory trees to read individual tap signal CSV files.
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.tap_file_index: Dict[int, Tuple[str, str, str]] = {}  # tap_id -> (kind, archive_path, inner_path)
        self.warnings: List[str] = []
        self._index_files()

    def _index_files(self) -> None:
        zip_paths = sorted(glob.glob(os.path.join(self.data_dir, "*.zip")))
        dir_paths = [
            d
            for d in glob.glob(os.path.join(self.data_dir, "*"))
            if os.path.isdir(d) and not os.path.basename(d).startswith("Zebra_")
        ]

        for zp in zip_paths:
            try:
                with zipfile.ZipFile(zp, "r") as zf:
                    for info in zf.infolist():
                        bname = os.path.basename(info.filename)
                        if bname.endswith(".csv") and bname[:-4].isdigit():
                            tap_id = int(bname[:-4])
                            if tap_id not in self.tap_file_index:
                                self.tap_file_index[tap_id] = ("zip", zp, info.filename)
            except Exception as e:
                self.warnings.append(f"Corrupt or unreadable zip archive '{zp}': {e}")

        for dp in dir_paths:
            for fname in os.listdir(dp):
                if fname.endswith(".csv") and fname[:-4].isdigit():
                    tap_id = int(fname[:-4])
                    if tap_id not in self.tap_file_index:
                        self.tap_file_index[tap_id] = ("dir", os.path.join(dp, fname), fname)

    def read_tap(self, tap_id: int) -> Optional[Tuple[TapMetadata, TapSignal]]:
        if tap_id not in self.tap_file_index:
            return None

        kind, path1, path2 = self.tap_file_index[tap_id]
        try:
            if kind == "zip":
                with zipfile.ZipFile(path1, "r") as zf:
                    content = zf.read(path2).decode("utf-8", errors="replace")
                source_file = f"{os.path.basename(path1)}/{path2}"
            else:
                with open(path1, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                source_file = path1

            return self._parse_tap_content(tap_id, content, source_file)
        except Exception as e:
            self.warnings.append(f"Failed to read signal for tap_id {tap_id} from {path1}: {e}")
            return None

    def read_all_taps(self) -> Tuple[List[TapMetadata], List[TapSignal]]:
        metadata_list: List[TapMetadata] = []
        signals_list: List[TapSignal] = []

        for tap_id in sorted(self.tap_file_index.keys()):
            res = self.read_tap(tap_id)
            if res:
                meta, sig = res
                metadata_list.append(meta)
                signals_list.append(sig)

        return metadata_list, signals_list

    @staticmethod
    def _parse_tap_content(tap_id: int, content: str, source_file: str) -> Tuple[TapMetadata, TapSignal]:
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        
        firmware_version = None
        device_batch = None
        raw_meta: Dict[str, str] = {}
        data_start_idx = 0

        if lines and lines[0].startswith("#"):
            first_line = lines[0][1:].strip()
            parts = first_line.split(",")
            firmware_version = parts[0].strip()
            if len(parts) > 1 and parts[1].strip().isdigit():
                device_batch = int(parts[1].strip())

        for idx, line in enumerate(lines):
            if line.startswith("#"):
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    raw_meta[parts[0].strip()] = parts[1].strip()
            else:
                data_start_idx = idx
                break

        channels = int(raw_meta.get("channels", 2))
        samples = int(raw_meta.get("samples", 2048))
        threshold = int(raw_meta["threshold"]) if "threshold" in raw_meta else None
        gain = int(raw_meta["gain"]) if "gain" in raw_meta else None
        rate_hz = float(raw_meta.get("rate", 500000.0))
        delay_us = float(raw_meta.get("delay", 0.0))
        tap_note = raw_meta.get("note", "")

        offset_ch1, offset_ch2 = 0.0, 0.0
        if "offset" in raw_meta:
            offsets = [float(x.strip()) for x in raw_meta["offset"].split(",")]
            if len(offsets) >= 1:
                offset_ch1 = offsets[0]
            if len(offsets) >= 2:
                offset_ch2 = offsets[1]

        std_ch1, std_ch2 = 0.0, 0.0
        if "std" in raw_meta:
            stds = [float(x.strip()) for x in raw_meta["std"].split(",")]
            if len(stds) >= 1:
                std_ch1 = stds[0]
            if len(stds) >= 2:
                std_ch2 = stds[1]

        ch1_samples: List[int] = []
        ch2_samples: List[int] = []

        for line in lines[data_start_idx:]:
            if line.startswith("#"):
                continue
            vals = line.split(",")
            if len(vals) >= 2:
                try:
                    ch1_samples.append(int(float(vals[0])))
                    ch2_samples.append(int(float(vals[1])))
                except ValueError:
                    pass

        metadata = TapMetadata(
            tap_id=tap_id,
            firmware_version=firmware_version,
            device_batch=device_batch,
            channels=channels,
            samples=samples,
            threshold=threshold,
            gain=gain,
            rate_hz=rate_hz,
            offset_ch1=offset_ch1,
            offset_ch2=offset_ch2,
            std_ch1=std_ch1,
            std_ch2=std_ch2,
            delay_us=delay_us,
            tap_note=tap_note,
            source_file=source_file,
            device_version="v2",
        )

        signal = TapSignal(
            tap_id=tap_id,
            ch1_samples=ch1_samples,
            ch2_samples=ch2_samples,
        )

        return metadata, signal
