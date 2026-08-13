# TreeTap Python Package

Python module for ingesting, processing, visualizing, and managing TreeTap acoustic velocity signals and measurement session summaries in a unified DuckDB database backend.

Supports multiple hardware device generations:
- **v2**: File and zip archive ingestion (`treetap-*.csv` summary files & `000000XXXX.csv` tap signals in `.zip` archives).
- **v1**: Serial communication acquisition interface.

---

## Installation & Setup

Create a virtual environment and install the package using `uv`:

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install treetap in editable mode
uv pip install -e .
```

---

## CLI Usage

### Data Ingestion
- **V1 Serial & Log File Ingestion (`File -> Ingest V1 Data (Serial / File)...`)**: Acquire live serial streams over hardware ports (`/dev/ttyUSB0` on Linux, `COM1` / `COM3` on Windows) at `57600` baud with `RTS/CTS` flow control. Features configurable **Probe Separation (cm)** input control (`QDoubleSpinBox`, saved in `QSettings`), non-blocking `QThread` background workers, automatic Linux `PermissionError` detection with a one-click **"Fix Permissions Now (chmod 666)"** workaround button using `pkexec`, plus instructions for permanent `uucp` / `dialout` group membership. Also supports importing offline raw ASCII log files with any extension (`.down`, `.txt`, `.log`, `.csv`, etc.).
- **SHA-256 Data Fingerprinting & Ingest Provenance**: Every import set is fingerprinted with a SHA-256 payload hash (`data_hash`) and assigned a unique `ingest_id` in `ingest_log`. Duplicate uploads of the exact same data payload are short-circuited before parsing with an informative notice.
- **Hierarchical Tree View**: Features 3-level nesting sorted by Ingestion Set -> Measurement Session -> Tap (`Ingest #1 (v1.down)` -> `Meas 1` -> `Tap 1`). Measurement titles are simplified to local session numbers while preserving distinct provenance groups under each ingestion root.
- **Fully Draggable Column Widths**: Headers in both Flat Table View and Hierarchical Tree View feature interactive column sizing (`QHeaderView.ResizeMode.Interactive`), allowing users to freely drag column dividers with the mouse.
- **New Database (`File -> New Database...`)**: Prompts for a target `.duckdb` filename, initializes an empty database schema (`measurements`, `taps`, `tap_metadata`, `tap_signals`, `v_tap_signals_long`), and connects to it immediately.
- **FTP Ingestion Dialog (`File -> Ingest V2 Data via FTP...`)**: Download and ingest V2 summary CSVs and raw signal archives directly from a remote FTP or FTPS server.
- **Port 21 Default & QSettings Persistence**: Default port is set to `21` (configurable), and server credentials/options (Host, Port, Remote Path, Username, Password, Passive Mode, FTPS) are retained across application sessions automatically.
- **Inserted vs. Skipped Reporting**: Post-ingestion dialogs and statistics report the exact number of new records inserted and existing duplicate records skipped across Measurements, Taps, and Signal archives.
- **Resilient Duplicate Handling**: Re-ingesting existing directories uses `INSERT OR IGNORE` with per-row exception handling, ensuring duplicate records are skipped gracefully without throwing foreign key or primary key constraint errors.
- Parse V2 directory via GUI (`File -> Ingest V2 Data Directory...`) or Python API:
```python
from treetap.v2.ingest import ingest_v2_directory
stats = ingest_v2_directory("data/v2", "treetap.duckdb")
print("Ingestion stats:", stats)
```
### Database Inspection

View database summary statistics:

```bash
treetap info --db treetap.duckdb
```

---

## Graphical User Interface (`Treetap Signals`) Usage

Launch the interactive PyQt6 desktop visualizer:

```bash
treetap gui --db treetap.duckdb
```

### Key Features

1. **Hierarchical Tree Upper Panel (`[ Hierarchical Tree | Flat Table ]`)**:
   * **Default View**: Starts in **Hierarchical Tree** mode, organizing Measurement Sessions as expandable parent rows and individual Taps as nested child rows.
   * **Numeric Column Sorting**: Sorting on the **`Meas / Tap`** column sorts numerically (`Meas 2`, `Meas 9`, `Meas 10`...) instead of alphabetically.
   * **Measurement Median Speed**: Displays the median acoustic velocity (`Speed (us)`) across all individual taps on parent Measurement rows (e.g. `203.90`).
   * **Flat Table Mode Toggle**: Switch to flat table view (`QTableView`) at any time for global multi-column sorting across all taps.
   * **Parent Measurement Selection**: Selecting a parent Measurement row overlays and highlights **all taps** for that session in the plot pane below.
   * **Child Tap Selection**: Selecting specific child tap row(s) specifically highlights **only those selected tap(s)** in the plot pane (thick & 100% opaque) while keeping sibling taps in the background at lowered opacity (~25%).
   * **Open Original Source File...**: Opens an in-app viewer dialog inspecting the raw tap CSV text file (resolving seamlessly from local `.zip` archives, folders, or fetching on-demand from the remote FTP server using saved credentials).
   * **Quick Filter**: Use the top filter bar to instantly search notes, IDs, and timestamps across both views.

2. **Lower Overlaid Signal Plot Pane**:
   * Uses high-performance `pyqtgraph` for smooth rendering without grid background clutter.
   * **Single-Axis Overlay**: Plots CH1 (Green `#00A000` solid lines) and CH2 (Red `#D32F2F` solid lines) overlaid on a shared time axis starting at $0\,\mu\text{s}$.
   * **Dual Vertical Measurement Markers**: Left-click on the plot canvas to drop up to 2 vertical measurement markers (M1: Orange, M2: Purple).
   * **Interactive Dragging & $\Delta t$ Calculation**: Select and drag either marker line left or right to dynamically compute and display the time difference ($\Delta t = |x_2 - x_1|\,\mu\text{s}$) in real time. Cursors automatically clear when selecting a different measurement session.
   * **Selection Emphasis**: Clicking any tap row in the upper table highlights its trace with a wider, 100% opaque line brought to the foreground, while lowering the opacity (~25%) of all unselected tap signals.
   * **Blue Crosshairs & Controls**: Hover over signals to inspect exact coordinates with blue crosshairs; use **"Reset View"** or **"Clear Markers"** controls.

3. **Tap Selector Sidebar**:
   * Located to the right of the plot widget with checkboxes for each tap in the selected session.
   * Toggle individual taps on/off dynamically to isolate signals.
   * Toggle **Channel 1 (Green —)** or **Channel 2 (Red —)** visibility globally, or use **"Select All"** / **"Deselect All"** buttons.
