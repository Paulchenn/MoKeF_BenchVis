import matplotlib
# MUST be called before importing pyplot
matplotlib.use("pgf")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import pandas as pd
import logging
import re
import numpy as np

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
        plot_df = benchmark_df
        current_legend_labels = legend_labels_sorted
        
        if metric == "ibvs_rms_px":
            ax.axhline(y=20, color='r', linestyle='--', linewidth=1)
            
            # Create a copy to modify labels just for this plot
            plot_df = benchmark_df.copy()
            new_labels = {}
            if 'normalized_time' in plot_df.columns:
                for run_id, run_group in plot_df.groupby('run_id'):
                    label = run_group['legend_label'].iloc[0]
                    run_group = run_group.sort_values('normalized_time')
                    above_mask = run_group['ibvs_rms_px'] > 20
                    
                    if not above_mask.any():
                        settling_time = 0.0
                    else:
                        last_true_index = above_mask[above_mask].index[-1]
                        loc = run_group.index.get_loc(last_true_index)
                        if loc + 1 < len(run_group):
                            settling_time = run_group.iloc[loc + 1]['normalized_time']
                        else:
                            settling_time = None # Never settled
                    
                    if settling_time is not None:
                        new_labels[run_id] = f"{label} (settles at {settling_time:.2f}s)"
                    else:
                        new_labels[run_id] = f"{label} (never settles)"
                
                plot_df['legend_label'] = plot_df['run_id'].map(new_labels)
                current_legend_labels = sorted(plot_df['legend_label'].unique())

        # estimator=None forces Seaborn to draw a separate, raw curve for each run_id without averaging
        sns.lineplot(data=plot_df, x=x_col, y=metric, hue='legend_label', hue_order=current_legend_labels, estimator=None, ax=ax)
        
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
        
        # Success Rate (1 or 0) - based on pre-calculated 'goal_reached' column
        if 'goal_reached' in group.columns:
            # Success is a pre-calculated int (1 or 0) constant for the whole run
            is_success = group['goal_reached'].iloc[0] == 1
        else:
            is_success = False # Default to failure if column is missing
        
        success = 1.0 if is_success else 0.0
        # The time taken is simply the total duration of the run's data.
        time_to_goal = group[x_col].max() if not group.empty else 0.0
            
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
        
        # Add numerical value annotations on top of each bar
        for patch in ax.patches:
            val = patch.get_height()
            if not pd.isna(val):
                ax.text(patch.get_x() + patch.get_width() / 2., val, 
                        f"${val:.4f}$", ha='center', va='bottom', fontsize=8)
                        
        # Expand Y-axis to make room for text
        ymin, ymax = ax.get_ylim()
        ax.set_ylim(ymin, ymax + (ymax - ymin) * 0.15)
        
    axes[0].set_ylim(0, 1.25) # Success rate limit manually adjusted to fit text
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
        
        is_success = group['goal_reached'].iloc[0] == 1 if 'goal_reached' in group.columns else False
        success_rate = 1.0 if is_success else 0.0

        # These metrics are ONLY calculated for successful runs. For failed runs, they are NaN and ignored by seaborn.
        mean_vel = group['ibvs_lin_vel_l2'].sum() / max_steps if is_success and 'ibvs_lin_vel_l2' in group.columns else np.nan
        mean_acc = group['ibvs_lin_acc_l2'].sum() / max_steps if is_success and 'ibvs_lin_acc_l2' in group.columns else np.nan
        final_path = group['path_length'].iloc[-1] if is_success and 'path_length' in group.columns else np.nan
        
        # These metrics are calculated for ALL runs. Averages are padded to max_steps for fairness.
        mean_rms = group['ibvs_rms_px'].sum() / max_steps if 'ibvs_rms_px' in group.columns else 0.0
        
        # Final/Maximum summary values achieved by the end of the run
        final_reject = group['filter_reject_count'].iloc[-1] if 'filter_reject_count' in group.columns else 0.0
        final_rescue = group['local_rescue_success_delta'].iloc[-1] if 'local_rescue_success_delta' in group.columns else 0.0
        
        summary_records.append({
            'Run ID': run_id,
            'Configuration': stage_filter,
            'Success Rate': success_rate,
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
        ('Success Rate', 'Success Rate', 'tab:pink'),
        ('Mean IBVS Lin Vel', 'Mean Lin Vel (m/s) [SUCCESSFUL RUNS]', 'tab:cyan'),
        ('Mean IBVS Lin Acc', 'Mean Lin Acc (m/s²) [SUCCESSFUL RUNS]', 'tab:blue'),
        ('Mean IBVS RMS', 'Mean RMS (px)', 'tab:orange'),
        ('Filter Reject Count', 'Filter Rejects (Final)', 'tab:green'),
        ('Path Length', 'Path Length (m) [SUCCESSFUL RUNS]', 'tab:red'),
        ('Local Rescue Success', 'Local Rescues (Final)', 'tab:purple')
    ]
    
    for col_name, y_label, color in metrics_to_plot:
        print(f"Plotting {col_name} for comparison {comparison_name}")
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Use standard deviation for error bars to match the +/- text logic
        sns.barplot(data=summary_df, x='Configuration', y=col_name, ax=ax, color=color, errorbar='sd', capsize=0.1)
        if col_name == 'Mean IBVS RMS':
            ax.axhline(y=20, color='r', linestyle='--', linewidth=1)

        ax.set_title(f"{title_base}\n{col_name}")
        ax.set_ylabel(y_label)
        ax.set_xlabel("Configuration (Stage - Filter)")
        ax.tick_params(axis='x', rotation=45)
        ax.grid(axis='y', alpha=0.3)
        
        # Calculate stats for the +/- annotations
        stats = summary_df.groupby('Configuration')[col_name].agg(['mean', 'std'])
        
        for patch, tick_label in zip(ax.patches, ax.get_xticklabels()):
            print(f"patch: {patch}, tick_label: {tick_label}")
            config = tick_label.get_text()
            if config in stats.index:
                print(f"config: {config}")
                mean_val = stats.loc[config, 'mean']
                std_val = stats.loc[config, 'std']
                
                if pd.isna(mean_val): continue
                if pd.isna(std_val): std_val = 0.0
                    
                # Place text slightly above the error bar (mean + std)
                y_pos = mean_val + std_val
                ax.text(patch.get_x() + patch.get_width() / 2., y_pos, 
                        f"${mean_val:.4f} \\pm {std_val:.4f}$", 
                        ha='center', va='bottom', fontsize=8)
                        
        # Add headroom for the text annotations
        ymin, ymax = ax.get_ylim()
        ax.set_ylim(ymin, ymax + (ymax - ymin) * 0.15)
        
        fig.tight_layout()
        safe_metric_name = col_name.replace(" ", "_").lower()
        export_plot(fig, comp_out_dir, f"{comp_name4save}_{safe_metric_name}")
        
def plot_comparison_timeseries(comparison_df: pd.DataFrame, comparison_name: str, output_dir: Path, global_limits: dict, max_steps: int):
    """
    Generates line plots showing the median over time for different Stage/Filter configurations.
    Pads early-terminating runs (success) with 0 or forward-filled values up to the timeout (max_steps).
    """
    comp_name4save = comparison_name.replace(" ", "")
    comp_out_dir = output_dir / "Comparisons" / str(comp_name4save)
    comp_out_dir.mkdir(parents=True, exist_ok=True)
    
    x_col = global_limits['x_col']
    x_label = global_limits['x_label']
    
    df_plot = comparison_df.copy()
    # Create an aligned step index for the matrix pivot
    df_plot['step'] = df_plot.groupby('run_id').cumcount()
    
    # Map step back to x_col (e.g. normalized_time) to maintain correct x-axis scale on the plot
    step_to_time = df_plot.groupby('step')[x_col].median()
    
    if x_col != 'step' and max_steps > step_to_time.index.max():
        # Extrapolate time for padded steps assuming constant dt
        last_steps = step_to_time.dropna().iloc[-5:]
        dt = last_steps.diff().median() if len(last_steps) > 1 else 0.1
        missing_steps = range(int(step_to_time.index.max()) + 1, max_steps)
        new_times = [step_to_time.iloc[-1] + (i * dt) for i in range(1, len(missing_steps) + 1)]
        step_to_time = pd.concat([step_to_time, pd.Series(new_times, index=missing_steps)])
        
    metrics_to_plot = [
        ("ibvs_lin_acc_l2", "Median Lin Acc (m/s²)"),
        ("ibvs_lin_vel_l2", "Median Lin Vel (m/s)"),
        ("ibvs_rms_px", "Median RMS (px)"),
        ("path_length", "Median Path Length (m)")
    ]
    
    comp_split = comparison_name.split("_")
    title_base = f"Level: {comp_split[0]} | Szen.: {comp_split[1]} | Bauteil: {comp_split[2]}"

    for metric, y_label in metrics_to_plot:
        if metric not in df_plot.columns:
            continue
            
        fig, ax = plt.subplots(figsize=(8, 5))
        
        if metric == 'ibvs_rms_px':
            ax.axhline(y=20, color='r', linestyle='--', linewidth=1)

        for config, group in df_plot.groupby('Stage_Filter'):
            # Pivot to get a step x run_id matrix
            pivot = group.pivot(index='step', columns='run_id', values=metric)
            
            # Reindex to force the matrix to extend exactly to the global timeout limit
            pivot = pivot.reindex(range(max_steps))
            
            # Apply padding logic for runs that reached the goal early
            if metric == 'path_length':
                pivot = pivot.ffill()  # Distance stays at its final maximum value
            else:
                pivot = pivot.fillna(0.0)  # Velocities and Errors drop to 0
            
            # Calculate the median across all runs for this configuration at each time step
            median_line = pivot.median(axis=1)
            
            label = config
            if metric == 'ibvs_rms_px' and x_col == 'normalized_time':
                above_threshold = median_line > 20
                if not above_threshold.any():
                    settling_time = 0.0
                else:
                    last_above_step = above_threshold[above_threshold].index.max()
                    settling_step = last_above_step + 1
                    
                    if settling_step >= max_steps:
                        settling_time = None # Never settled
                    else:
                        settling_time = step_to_time.get(settling_step)

                if settling_time is not None:
                    label = f"{config} (settles at {settling_time:.2f}s)"
                else:
                    label = f"{config} (never settles)"

            # Map the steps back to the proper X-axis values for plotting
            x_vals = median_line.index if x_col == 'step' else step_to_time.reindex(median_line.index).ffill().values
                
            ax.plot(x_vals, median_line.values, label=label)
            
        metric_pretty = metric.replace('_', ' ').upper()
        ax.set_title(f"{title_base}\n{metric_pretty} (Median over time)")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        
        ax.set_xlim(left=0, right=global_limits['x_max'])
        y_min = global_limits['y_mins'].get(metric, 0)
        y_max = global_limits['y_maxs'].get(metric, 1)
        margin = (y_max - y_min) * 0.05 if y_max > y_min else 0.1
        ax.set_ylim(bottom=y_min, top=y_max + margin)
        
        ax.legend(loc='upper right', title="Configuration")
        ax.grid(alpha=0.3)
        
        fig.tight_layout()
        safe_metric_name = metric.lower()
        export_plot(fig, comp_out_dir, f"{comp_name4save}_timeseries_median_{safe_metric_name}")

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

            # Define success based on time threshold and overwrite 'goal_reached'
            success_map = combined_run_df.groupby('run_id')['normalized_time'].max() < 28.0
            combined_run_df['goal_reached'] = combined_run_df['run_id'].map(success_map).astype(int)
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

            plot_benchmark_metrics(group_df, benchmark_name, output_dir, global_limits)
            plot_benchmark_summary_bars(group_df, benchmark_name, output_dir, global_limits)
            
        # Generate high-level configuration comparisons
        for comp_name, comp_df in master_df.groupby('ComparisonGroup'):
            logging.info(f"Generating configuration comparison plots for group: {comp_name}")
            plot_comparison_summary_bars(comp_df, comp_name, output_dir, max_steps)
            plot_comparison_timeseries(comp_df, comp_name, output_dir, global_limits, max_steps)
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
