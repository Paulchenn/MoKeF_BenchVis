# IBVS Benchmarking Visualization Pipeline

This repository contains a Python-based data processing and visualization pipeline for evaluating the performance of an Image-Based Visual Servo (IBVS) system across various stages, filters, and scenarios.

The pipeline parses raw `.csv` telemetry, aligns time-series data, generates comprehensive performance plots (Line charts, Bar charts), calculates summary statistics (Success Rate, Time to Goal, RMS, Settling Time), and allows for a unique **Two-Pass Global Scaling** system to perfectly align chart axes for side-by-side paper/report comparisons.

## 📂 Directory Structure (What is where?)

### Input Data
* **`2plot/`**: The main raw data folder. It contains subfolders for each run (e.g., `run_01`, `run_02`), which in turn contain stage-specific folders (e.g., `stage_2_filter`) holding the raw `.csv` log files.
* **`ModelIBVS_BenchmarkTracking.xlsx`**: The metadata spreadsheet. The script reads the sheet `"2. Messungen"` to link raw data folders in `2plot/` to their specific parameters (Level, Stage, Scenario, Filter, Bauteil).

### Output Data
* **`outputs/`**: The default output directory for Phase 1 generation. Contains generated PDFs, PGFs, SVGs, and PKL files.
  * `outputs/per_run/`: Contains detailed line plots and summary bar charts grouped by individual benchmark parameters.
  * `outputs/Comparisons/`: Contains aggregated median time-series and summary bar charts comparing different Stage/Filter configurations against each other.
* **`z_2use/`**: A curated reference directory used for Phase 2 (Regeneration). You manually copy the `.pkl` files of the plots you want to publish into this folder. The script uses these to calculate a unified, global Y-axis scale.

### Collection/Export Folders
* **`pgf/`**: Destination folder for LaTeX-ready vector graphic text files, gathered by `collect_pgfs.py`.
* **`svg/`**: Destination folder for standard vector graphics, gathered by `collect_svgs.py`.
* **`collected_csvs/`**: Destination folder for flattened raw data, gathered by `collect_csvs.py`.

---

## 🚀 The Core Workflow (What can you do?)

The plotting architecture is built around a robust **Two-Pass System**. This prevents charts from having drastically different Y-axis limits depending on the local data, which would make side-by-side comparison in a LaTeX document misleading.

### Phase 1: Normal Generation
Run the primary plotting script to process all raw data.
```bash
python plotting.py
```
**What happens:**
1. The script reads the Excel tracking sheet to figure out what data exists.
2. It pulls the `.csv` files from `2plot/`, cleans the data, calculates custom metrics (like Path Length, Settling Time, and relative normalized time based on initial motion), and pads early-terminating runs.
3. It generates local plots in `outputs/`.
4. Crucially, next to every `.pdf`, `.pgf`, and `.svg`, it saves a **`.pkl` file**. This `.pkl` file contains the exact dataframe and parameters needed to perfectly recreate that specific plot later.

### Phase 2: Curation
Navigate into the `outputs/` directory and review your plots. When you find the exact plots you want to include in your final report or paper, **copy their `.pkl` files** into the `z_2use/` directory. You can organize them in subdirectories inside `z_2use/` if you like.

### Phase 3: Global Regeneration
Run the plotting script with the regenerate flag.
```bash
python plotting.py --regenerate
```
**What happens:**
1. The script completely ignores the `2plot/` and Excel files.
2. It scans `z_2use/` for `.pkl` files and loads them into memory.
3. It calculates the absolute global maximums for every metric (RMS, velocity, acceleration, etc.) across *only* the curated plots.
4. It re-draws all the curated plots using these new unified Y-axis limits (plus a 5% visual buffer) and saves the updated `.pdf`, `.pgf`, and `.svg` files right back into the `z_2use/` folder next to the `.pkl`s.

---

## 🧰 Helper Scripts

Because generating plots recursively in subfolders makes it hard to import them cleanly into LaTeX or vector editors, there are three helper scripts included. They flatten the folder structures while preserving names to avoid collisions.

* **`python collect_pgfs.py`**: Scans the curated `z_2use/` directory for `.pgf` files. Copies them all into the flat `pgf/` root folder, renaming them based on their parent folder structure (e.g., `folderA_folderB_plotname.pgf`).
* **`python collect_svgs.py`**: Does the exact same thing as above, but for `.svg` files, moving them to the `svg/` folder.
* **`python collect_csvs.py`**: Scans the raw data `2plot/` folder for `.csv` files and copies them flat into `collected_csvs/`, renaming them by their parent paths.

---

## 📊 Generated Metrics & Plots

The `plotting.py` script automatically evaluates:
* **Line Plots (Individual Runs):** Tracking `ibvs_rms_px`, `ibvs_lin_vel_l2`, `base_lin_vel_l2`, etc., over normalized time. Automatically draws a 20px threshold line and computes settling time.
* **Summary Bars (Individual Runs):** Success Rate, Time to Goal, Mean IBVS RMS, and Final Path Length.
* **Comparison Median Timeseries:** Pads early dropouts (Successes pad velocities to `0.0`, path lengths `forward-fill`) to allow calculating continuous medians across different Filter/Stage configurations.
* **Comparison Summary Bars:** Shows overall configurations alongside their standard deviations (`± std`). Includes logic to format success rates as `X.X%`.

## ⚙️ Requirements

Ensure your Python environment has the following packages installed:
```bash
pip install matplotlib seaborn pandas numpy openpyxl
```

*Note: Your system must also have a functional TeX distribution (like TeX Live or MiKTeX) installed and accessible in the system PATH, as Matplotlib uses `pdflatex` to render the text in the PGF files natively.*
```

<!--
[PROMPT_SUGGESTION]Could you update the `plotting.py` script to also log a summary text file in the `outputs` directory that lists the final global limits calculated during a run?[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Is there a way to add an optional argument to `collect_svgs.py` to zip the output directory so it is easier to share?[/PROMPT_SUGGESTION]
