import matplotlib
# MUST be called before importing pyplot
matplotlib.use("pgf")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import pandas as pd
import logging
import re

# Configure LaTeX/PGF settings
matplotlib.rcParams.update({
    "pgf.texsystem": "pdflatex",
    "font.family": "serif",
    "text.usetex": True,
    "pgf.rcfonts": False,
    "axes.labelsize": 10,
    "font.size": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "pgf.preamble": "\n".join([
        r"\usepackage[utf8x]{inputenc}",
        r"\usepackage[T1]{fontenc}",
    ])
})

def export_plot(fig, output_dir: Path, filename_base: str):
    """
    Handles the exporting of the figure into both required formats.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as PDF for quick review
    pdf_path = output_dir / f"{filename_base}.pdf"
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    
    # Save as PGF for LaTeX integration
    pgf_path = output_dir / f"{filename_base}.pgf"
    fig.savefig(pgf_path, format="pgf", bbox_inches="tight")
    
    # Post-process the PGF file to strip hardcoded font families.
    # This forces the text to natively inherit the surrounding LaTeX document's font.
    if pgf_path.exists():
        with open(pgf_path, "r", encoding="utf-8") as f:
            content = f.read()
        for font_cmd in [r"\rmfamily", r"\sffamily", r"\ttfamily"]:
            content = content.replace(font_cmd, "")
        with open(pgf_path, "w", encoding="utf-8") as f:
            f.write(content)

    # Critical: clear memory
    plt.close(fig)

def load_metadata(excel_path: Path) -> pd.DataFrame:
    """
    Reads the Benchmark Tracking Excel file.
    """
    df = pd.read_excel(excel_path, sheet_name="2. Messungen")
    
    if 'Ordnername' not in df.columns:
        logging.warning("No 'Ordnername' column found in Excel. Metadata matching may fail.")
        
    return df

def plot_benchmark_metrics(benchmark_df: pd.DataFrame, benchmark_name: str, output_dir: Path, global_limits: dict):
    """
    Generates individual plots for specified metrics across all runs within a single benchmark.
    """
    metrics = [
        "ibvs_rms_px", "ibvs_lin_vel_l2", "ibvs_ang_vel_l2", 
        "ibvs_lin_acc_l2", "ibvs_ang_acc_l2", "base_lin_vel_l2", 
        "base_ang_vel_l2", "base_lin_acc_l2", "base_ang_acc_l2",
        "filter_reject_count", "local_rescue_attempts_delta", 
        "local_rescue_success_delta", "local_rescue_reject_delta",
        "run_timed_out", "goal_reached", "path_length"
    ]
    
    bench_name4save = benchmark_name.replace(" ", "")
    bench_out_dir = output_dir / str(bench_name4save)
    bench_out_dir.mkdir(parents=True, exist_ok=True)

    # The legend_label column is now expected to exist on benchmark_df
    legend_labels_sorted = sorted(benchmark_df['legend_label'].unique())
    x_col = global_limits['x_col']
    x_label = global_limits['x_label']

    for metric in metrics:
        if metric not in benchmark_df.columns:
            logging.debug(f"Metric {metric} not found in data for {benchmark_name}, skipping.")
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        
        # estimator=None forces Seaborn to draw a separate, raw curve for each run_id without averaging
        sns.lineplot(data=benchmark_df, x=x_col, y=metric, hue='legend_label', hue_order=legend_labels_sorted, estimator=None, ax=ax)
        
        metric_pretty = metric.replace('_', ' ').upper()
        bench_split = benchmark_name.split("_")
        ax.set_title(f"Stufe: {bench_split[1]} | Szen.: {bench_split[2]} | Filter: {bench_split[3]} | Level: {bench_split[0]} | Bauteil: {bench_split[4]}\n{metric_pretty}")
        ax.set_xlabel(x_label)
            
        # Apply global axes limits to ensure 1:1 comparison across all plots
        ax.set_xlim(left=0, right=global_limits['x_max'])
        
        y_min = global_limits['y_mins'].get(metric, 0)
        y_max = global_limits['y_maxs'].get(metric, 1)
        margin = (y_max - y_min) * 0.05 if y_max > y_min else 0.1
        ax.set_ylim(bottom=y_min, top=y_max + margin)
            
        # Move the legend outside the plot to avoid overlapping data
        ax.legend(loc='upper right', title="Run")
        
        export_plot(fig, bench_out_dir, f"{bench_name4save}_{metric}")

def plot_benchmark_summary_bars(benchmark_df: pd.DataFrame, benchmark_name: str, output_dir: Path, global_limits: dict):
    """
    Generates a figure with 3 subplots (bar charts) summarizing each run.
    Metrics: Success Rate (1/0), Time to Goal, Mean IBVS RMS.
    """
    bench_name4save = benchmark_name.replace(" ", "")
    bench_out_dir = output_dir / str(bench_name4save)
    bench_out_dir.mkdir(parents=True, exist_ok=True)
    
    x_col = global_limits['x_col']
    
    summary_records = []
    for run_id, group in benchmark_df.groupby('run_id'):
        legend_label = group['legend_label'].iloc[0]
        
        # Success Rate (1 or 0)
        if 'goal_reached' in group.columns:
            is_success_mask = group['goal_reached'].astype(str).str.lower().isin(['1', 'true', 'yes', 'y'])
            is_success = is_success_mask.any()
            success = 1.0 if is_success else 0.0
            
            if is_success:
                time_to_goal = group.loc[is_success_mask, x_col].min()
            else:
                time_to_goal = group[x_col].max()
        else:
            success = 0.0
            time_to_goal = group[x_col].max()
            
        # Mean IBVS RMS
        mean_rms = group['ibvs_rms_px'].mean() if 'ibvs_rms_px' in group.columns else 0.0
        
        # Final Path Length
        final_path_length = group['path_length'].iloc[-1] if 'path_length' in group.columns else 0.0
        
        summary_records.append({
            'Run': legend_label,
            'Success Rate': success,
            'Time to Goal': time_to_goal,
            'Mean IBVS RMS': mean_rms,
            'Path Length': final_path_length
        })
        
    summary_df = pd.DataFrame(summary_records).sort_values('Run')
    
    fig, axes = plt.subplots(4, 1, figsize=(8, 13), sharex=True)
    
    sns.barplot(data=summary_df, x='Run', y='Success Rate', ax=axes[0], color='tab:blue')
    bench_split = benchmark_name.split("_")
    axes[0].set_title(f"Stufe: {bench_split[1]} | Szen.: {bench_split[2]} | Filter: {bench_split[3]} | Level: {bench_split[0]} | Bauteil: {bench_split[4]}\nRun Summaries")
    axes[0].set_ylabel("Success Rate")
    axes[0].set_ylim(0, 1.1)
    
    sns.barplot(data=summary_df, x='Run', y='Time to Goal', ax=axes[1], color='tab:orange')
    axes[1].set_ylabel(f"Time to Goal ({'s' if x_col == 'normalized_time' else 'steps'})")
    
    sns.barplot(data=summary_df, x='Run', y='Mean IBVS RMS', ax=axes[2], color='tab:green')
    axes[2].set_ylabel("Mean IBVS RMS (px)")
    
    sns.barplot(data=summary_df, x='Run', y='Path Length', ax=axes[3], color='tab:red')
    axes[3].set_ylabel("Path Length (m)")
    
    for ax in axes:
        ax.set_xlabel("")
        ax.tick_params(axis='x', rotation=45)
        ax.grid(axis='y', alpha=0.3)
        
    axes[-1].set_xlabel("Run")
    fig.tight_layout()
    
    export_plot(fig, bench_out_dir, f"{bench_name4save}_summary_bars")

def plot_comparison_summary_bars(comparison_df: pd.DataFrame, comparison_name: str, output_dir: Path, max_steps: int):
    """
    Generates a figure with 5 subplots comparing different Stage/Filter configurations
    for a specific Level, Scenario, and Type (Bauteil).
    """
    comp_name4save = comparison_name.replace(" ", "")
    comp_out_dir = output_dir / "Comparisons" / str(comp_name4save)
    comp_out_dir.mkdir(parents=True, exist_ok=True)
    
    summary_records = []
    for run_id, group in comparison_df.groupby('run_id'):
        stage_filter = group['Stage_Filter'].iloc[0]
        
        # Averages calculated by assuming 0 for padded steps up to max_steps (timeout)
        mean_vel = group['ibvs_lin_vel_l2'].sum() / max_steps if 'ibvs_lin_vel_l2' in group.columns else 0.0
        mean_acc = group['ibvs_lin_acc_l2'].sum() / max_steps if 'ibvs_lin_acc_l2' in group.columns else 0.0
        mean_rms = group['ibvs_rms_px'].sum() / max_steps if 'ibvs_rms_px' in group.columns else 0.0
        
        # Final/Maximum summary values achieved by the end of the run
        final_reject = group['filter_reject_count'].iloc[-1] if 'filter_reject_count' in group.columns else 0.0
        final_path = group['path_length'].iloc[-1] if 'path_length' in group.columns else 0.0
        final_rescue = group['local_rescue_success_delta'].iloc[-1] if 'local_rescue_success_delta' in group.columns else 0.0
        
        summary_records.append({
            'Run ID': run_id,
            'Configuration': stage_filter,
            'Mean IBVS Lin Vel': mean_vel,
            'Mean IBVS Lin Acc': mean_acc,
            'Mean IBVS RMS': mean_rms,
            'Filter Reject Count': final_reject,
            'Path Length': final_path,
            'Local Rescue Success': final_rescue
        })
        
    summary_df = pd.DataFrame(summary_records).sort_values('Configuration')
    
    comp_split = comparison_name.split("_")
    title_base = f"Level: {comp_split[0]} | Szen.: {comp_split[1]} | Bauteil: {comp_split[2]}"
    
    metrics_to_plot = [
        ('Mean IBVS Lin Vel', 'Mean Lin Vel (m/s)', 'tab:cyan'),
        ('Mean IBVS Lin Acc', 'Mean Lin Acc (m/s²)', 'tab:blue'),
        ('Mean IBVS RMS', 'Mean RMS (px)', 'tab:orange'),
        ('Filter Reject Count', 'Filter Rejects (Final)', 'tab:green'),
        ('Path Length', 'Path Length (m)', 'tab:red'),
        ('Local Rescue Success', 'Local Rescues (Final)', 'tab:purple')
    ]
    
    for col_name, y_label, color in metrics_to_plot:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        sns.barplot(data=summary_df, x='Configuration', y=col_name, ax=ax, color=color)
        ax.set_title(f"{title_base}\n{col_name}")
        ax.set_ylabel(y_label)
        ax.set_xlabel("Configuration (Stage - Filter)")
        ax.tick_params(axis='x', rotation=45)
        ax.grid(axis='y', alpha=0.3)
        
        fig.tight_layout()
        safe_metric_name = col_name.replace(" ", "_").lower()
        export_plot(fig, comp_out_dir, f"{comp_name4save}_{safe_metric_name}")

def run_pipeline(root_dir: Path, excel_path: Path, output_dir: Path):
    """
    The main loop that iterates over runs, accumulates data, and triggers grouped plotting.
    """
    metadata_df = load_metadata(excel_path)
    all_data = []
    
    for idx, meta_row in metadata_df.iterrows():
        run_folder_name = meta_row.get('Ordnername')
        if pd.isna(run_folder_name):
            continue
            
        run_folder = root_dir / str(run_folder_name)
        if not run_folder.is_dir():
            logging.warning(f"Directory {run_folder} not found for row {idx}.")
            continue
            
        # Generate benchmark name from metadata columns
        components = []
        for col in ["Level", "Stage", "Szenario", "Filter", "Bauteil"]:
            val = meta_row.get(col)
            components.append(str(val) if pd.notna(val) else "NA")
        benchmark_name = "_".join(components)
        
        stage_val = str(meta_row.get('Stage', '')).lower()
        filter_val = str(meta_row.get('Filter', '')).lower()
        
        # Determine stage directory based on 'Stage' column
        if '1' in stage_val:
            stage_path = run_folder / "stage_1_keypoint_only"
        elif '2' in stage_val:
            stage_path = run_folder / "stage_2_filter"
        elif '3' in stage_val:
            stage_path = run_folder / "stage_3_filter_local_rescue"
        else:
            logging.warning(f"Unknown stage '{stage_val}' for {run_folder_name}")
            continue
            
        if not stage_path.exists():
            logging.warning(f"Stage path {stage_path} does not exist.")
            continue
            
        all_csvs = list(stage_path.glob("*.csv"))
        if not all_csvs:
            continue
            
        # Filter CSVs for stage 2 and 3 based on Filter name
        if '1' in stage_val:
            csv_files = all_csvs
        else:
            if filter_val == 'nan' or not filter_val:
                logging.warning(f"Filter value missing for stage {stage_val} in {run_folder_name}")
                continue
            # Use regex to safely match filter_val (e.g. ekf) without matching sub-strings (e.g. eskf)
            csv_files = [f for f in all_csvs if re.search(rf"(^|[_.-]){re.escape(filter_val)}([_.-]|$)", f.name.lower())]
            
        if not csv_files:
            logging.warning(f"No CSVs matching filter '{filter_val}' found in {stage_path}")
            continue
            
        # Read each CSV and assign it a unique ID so it gets its own distinct curve
        df_list = []
        for csv in csv_files:
            df = pd.read_csv(csv)
            # Ensure run_id uniquely identifies this specific file for this benchmark row
            df['run_id'] = f"row{idx}_{csv.stem}"
            df_list.append(df)
            
        combined_run_df = pd.concat(df_list, ignore_index=True)
        
        # --- FUTURE INTEGRATION: process_logs ---
        # log_path = run_folder / "process_logs"
        # if log_path.exists():
        #     log_df = parse_node_logs(log_path)
        #     combined_run_df = pd.merge(combined_run_df, log_df, on="time", how="left")
        # ----------------------------------------
        
        # Append identifiers required for comparative plotting
        combined_run_df['BenchmarkName'] = benchmark_name
        combined_run_df['Level'] = components[0]
        combined_run_df['Stage'] = components[1]
        combined_run_df['Szenario'] = components[2]
        combined_run_df['Filter'] = components[3]
        combined_run_df['Bauteil'] = components[4]
        
        # Grouping identifiers for the high-level configuration comparisons
        combined_run_df['ComparisonGroup'] = f"{components[0]}_{components[2]}_{components[4]}"
        combined_run_df['Stage_Filter'] = f"Stage {components[1]} - {components[3]}"
        
        # Calculate time normalization here so limits can be extracted globally later
        if 't_rel_s' in combined_run_df.columns:
            if 'ibvs_lin_vel_l2' in combined_run_df.columns:
                motion_mask = combined_run_df['ibvs_lin_vel_l2'] > 1e-5
                start_times = combined_run_df[motion_mask].groupby('run_id')['t_rel_s'].min()
                combined_run_df['start_time'] = combined_run_df['run_id'].map(start_times)
                
                fallback_starts = combined_run_df.groupby('run_id')['t_rel_s'].min()
                combined_run_df['start_time'] = combined_run_df['start_time'].fillna(combined_run_df['run_id'].map(fallback_starts))
                
                combined_run_df['normalized_time'] = combined_run_df['t_rel_s'] - combined_run_df['start_time']
                combined_run_df = combined_run_df[combined_run_df['normalized_time'] >= 0.0].copy()
            else:
                combined_run_df['normalized_time'] = combined_run_df.groupby('run_id')['t_rel_s'].transform(lambda x: x - x.min())
            combined_run_df['normalized_time'] = combined_run_df.groupby('run_id')['t_rel_s'].transform(lambda x: x - x.iloc[0] if len(x) > 0 else x)
            
            # Calculate Path Length
            if 'path_length' not in combined_run_df.columns and 'base_lin_vel_l2' in combined_run_df.columns:
                combined_run_df['delta_t'] = combined_run_df.groupby('run_id')['t_rel_s'].diff().fillna(0.0)
                combined_run_df['step_dist'] = combined_run_df['base_lin_vel_l2'] * combined_run_df['delta_t']
                combined_run_df['path_length'] = combined_run_df.groupby('run_id')['step_dist'].cumsum()
                combined_run_df.drop(columns=['delta_t', 'step_dist'], inplace=True)
        else:
            combined_run_df['step'] = combined_run_df.groupby('run_id').cumcount()
            
        # Zero out the starting values for specific cumulative metrics
        cols_to_zero = [
            "filter_reject_count",
            "local_rescue_attempts_delta",
            "local_rescue_success_delta",
            "local_rescue_reject_delta"
        ]
        for col in cols_to_zero:
            if col in combined_run_df.columns:
                combined_run_df[col] = combined_run_df.groupby('run_id')[col].transform(lambda x: x - x.iloc[0] if len(x) > 0 else x)
            
        all_data.append(combined_run_df)
        
    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)
        
        # Determine the maximum steps any run took, to use as the baseline "timeout" for average calculation
        max_steps = master_df.groupby('run_id').size().max()
        
        # Compute global axis limits for unified scaling
        global_limits = {'y_mins': {}, 'y_maxs': {}}
        if 'normalized_time' in master_df.columns:
            global_limits['x_max'] = master_df['normalized_time'].max()
            global_limits['x_col'] = 'normalized_time'
            global_limits['x_label'] = "Time (s)"
        else:
            global_limits['x_max'] = master_df['step'].max()
            global_limits['x_col'] = 'step'
            global_limits['x_label'] = "Step"
            
        metrics_to_scale = [
            "ibvs_rms_px", "ibvs_lin_vel_l2", "ibvs_ang_vel_l2", "ibvs_lin_acc_l2", "ibvs_ang_acc_l2",
            "base_lin_vel_l2", "base_ang_vel_l2", "base_lin_acc_l2", "base_ang_acc_l2", "filter_reject_count",
            "local_rescue_attempts_delta", "local_rescue_success_delta", "local_rescue_reject_delta", "run_timed_out", "goal_reached", "path_length"
        ]
        for m in metrics_to_scale:
            if m in master_df.columns:
                global_limits['y_mins'][m] = master_df[m].min()
                global_limits['y_maxs'][m] = master_df[m].max()
        
        for benchmark_name, group_df in master_df.groupby('BenchmarkName'):
            logging.info(f"Generating aggregated plots for benchmark group: {benchmark_name}")

            # Create legend labels once for the group to be used by all plotting functions
            group_df = group_df.copy()
            unique_run_ids = sorted(group_df['run_id'].unique())
            run_id_to_label_map = {run_id: f"run{i+1:02d}" for i, run_id in enumerate(unique_run_ids)}
            group_df['legend_label'] = group_df['run_id'].map(run_id_to_label_map)

            #plot_benchmark_metrics(group_df, benchmark_name, output_dir, global_limits)
            #plot_benchmark_summary_bars(group_df, benchmark_name, output_dir, global_limits)
            
        # Generate high-level configuration comparisons
        for comp_name, comp_df in master_df.groupby('ComparisonGroup'):
            logging.info(f"Generating configuration comparison plots for group: {comp_name}")
            plot_comparison_summary_bars(comp_df, comp_name, output_dir, max_steps)
    else:
        logging.warning("No valid data was found to plot.")

if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    # Define primary directories
    base_directory = Path(__file__).parent
    data_directory = base_directory / "2plot"
    metadata_excel = base_directory / "ModelIBVS_BenchmarkTracking.xlsx"
    output_directory = base_directory / "outputs"
    
    if metadata_excel.exists():
        logging.info("Starting benchmarking visualization pipeline...")
        run_pipeline(data_directory, metadata_excel, output_directory)
        logging.info("Pipeline execution complete.")
    else:
        logging.critical(f"Metadata file not found at {metadata_excel}")
