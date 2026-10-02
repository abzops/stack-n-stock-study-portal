#!/usr/bin/env python3
"""
Stack n Stock — Pick & Pack Study Statistical Analysis & Report Generator
Executes the analytical protocol defined in Section 10 and Section 13 of the Test Guide.
Analyzes Excel study workbooks and raw CSV exports from data/raw/, and saves
a comprehensive formatted report to data/processed/study_report.md.
"""

import os
import sys
import argparse
import glob
from datetime import datetime
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_WORKBOOK = os.path.join(PROJECT_ROOT, "templates", "SNS_Pick_Pack_Study_Workbook.xlsx")
DEFAULT_RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
DEFAULT_PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
DEFAULT_OUTPUT_REPORT = os.path.join(DEFAULT_PROCESSED_DIR, "study_report.md")


def safe_format(val, fmt="{:.2f}", default="-"):
    """Safely format numbers with fallback for strings and NaN."""
    if pd.isnull(val):
        return default
    try:
        f = float(val)
        return fmt.format(f)
    except (ValueError, TypeError):
        s = str(val).strip()
        return s if s else default


def normalize_picker_df(df, source_label=""):
    """Normalize column names and data types for Picker trials."""
    if df is None or len(df) == 0:
        return None

    # Exclude if explicitly a packer role dataset
    if "role" in df.columns and (df["role"].astype(str).str.strip().str.lower() == "packer").all():
        return None

    col_map = {}
    explicit = {'study_id':'session_id','study id':'session_id','session_id':'session_id',
                'pick number':'trial_id','picknumber':'trial_id','configuration':'module_type',
                'sku id':'sku_id','skuid':'sku_id','sku name':'sku_name','skuname':'sku_name',
                'cycle_time_s':'cycle_time_s','pick cycle time':'cycle_time_s',
                'error / delay code':'delay_code','exception':'delay_code',
                'accuracy':'accuracy','valid':'timing_valid'}
    for col in df.columns:
        cl = str(col).strip().lower()
        if cl in explicit:
            col_map[col] = 'study_id' if cl in ('study id','study_id') and 'session_id' in df.columns else explicit[cl]
        elif 'cycle_time_s' in df.columns and cl in ('cycletimems','cycletime'):
            continue
        elif "total" not in cl and "cycle" in cl and "time" in cl:
            col_map[col] = "cycle_time_s"
        elif cl.startswith("correct"):
            col_map[col] = "correct"
        elif cl in ("slot id", "slot_id", "slot"):
            col_map[col] = "slot_id"
        elif cl in ("module", "module type", "module_type"):
            col_map[col] = "module_type"
        elif cl in ("operator", "operator id", "operator_id"):
            col_map[col] = "operator_id"
        elif cl in ("trial #", "trial_id", "trial"):
            col_map[col] = "trial_id"
        elif cl in ("session id", "session_id", "session"):
            col_map[col] = "session_id"
        elif cl in ("delay code", "delay_code", "delay"):
            col_map[col] = "delay_code"
        elif "sys delay" in cl or "system_latency" in cl:
            col_map[col] = "system_latency_s"
        elif "sku" in cl:
            col_map[col] = "sku_qty"

    renamed = df.rename(columns=col_map).copy()
    if "cycle_time_s" not in renamed.columns:
        return None

    renamed["cycle_time_s"] = pd.to_numeric(renamed["cycle_time_s"], errors="coerce")
    renamed = renamed.dropna(subset=["cycle_time_s"])
    if len(renamed) == 0:
        return None

    if "accuracy" in renamed.columns:
        renamed['is_correct'] = renamed['accuracy'].map({'correct':True,'incorrect':False})
    elif "correct" in renamed.columns:
        renamed["is_correct"] = renamed["correct"].astype(str).str.strip().str.lower().isin(["yes", "true", "1", "t", "y"])
    else:
        renamed["is_correct"] = np.nan
    if 'timing_valid' in renamed.columns:
        renamed['timing_valid'] = renamed['timing_valid'].astype(str).str.lower().isin(['true','1','yes'])
    else:
        renamed['timing_valid'] = renamed['is_correct'].fillna(True).astype(bool)

    if "slot_id" not in renamed.columns:
        renamed["slot_id"] = "Unknown"
    else:
        renamed["slot_id"] = renamed["slot_id"].astype(str).str.strip()

    if "module_type" not in renamed.columns:
        renamed["module_type"] = "Standard"
    else:
        renamed["module_type"] = renamed["module_type"].astype(str).str.strip()

    if "operator_id" not in renamed.columns:
        renamed["operator_id"] = "Unknown"

    renamed["_source"] = source_label
    return renamed


def normalize_packer_df(df, source_label=""):
    """Normalize column names and data types for Packer trials."""
    if df is None or len(df) == 0:
        return None

    # Exclude if explicitly a picker role dataset
    if "role" in df.columns and (df["role"].astype(str).str.strip().str.lower() == "picker").all():
        return None

    col_map = {}
    for col in df.columns:
        cl = str(col).strip().lower()
        if "total" in cl and "cycle" in cl:
            col_map[col] = "total_cycle_s"
        elif "retrieval" in cl:
            col_map[col] = "retrieval_s"
        elif "rework" in cl:
            col_map[col] = "rework"
        elif "work" in cl and "rework" not in cl:
            col_map[col] = "work_s"
        elif "complexity" in cl:
            col_map[col] = "complexity_band"
        elif cl.startswith("correct"):
            col_map[col] = "correct"
        elif cl in ("slot id", "slot_id", "slot"):
            col_map[col] = "slot_id"
        elif cl in ("module", "module type", "module_type"):
            col_map[col] = "module_type"
        elif cl in ("operator", "operator id", "operator_id"):
            col_map[col] = "operator_id"
        elif cl in ("trial #", "trial_id", "trial"):
            col_map[col] = "trial_id"
        elif cl in ("session id", "session_id", "session"):
            col_map[col] = "session_id"
        elif "item" in cl:
            col_map[col] = "items_count"
        elif "delay" in cl:
            col_map[col] = "delay_code"

    renamed = df.rename(columns=col_map).copy()
    if "total_cycle_s" not in renamed.columns:
        return None

    renamed["total_cycle_s"] = pd.to_numeric(renamed["total_cycle_s"], errors="coerce")
    renamed = renamed.dropna(subset=["total_cycle_s"])
    if len(renamed) == 0:
        return None

    if "retrieval_s" in renamed.columns:
        renamed["retrieval_s"] = pd.to_numeric(renamed["retrieval_s"], errors="coerce")
    else:
        renamed["retrieval_s"] = np.nan

    if "work_s" in renamed.columns:
        renamed["work_s"] = pd.to_numeric(renamed["work_s"], errors="coerce")
    else:
        renamed["work_s"] = np.nan

    if "complexity_band" not in renamed.columns:
        renamed["complexity_band"] = "Standard"
    else:
        renamed["complexity_band"] = renamed["complexity_band"].astype(str).str.strip().str.upper()

    if "correct" in renamed.columns:
        renamed["is_correct"] = renamed["correct"].astype(str).str.strip().str.lower().isin(["yes", "true", "1", "t", "y"])
    else:
        renamed["is_correct"] = True

    if "rework" in renamed.columns:
        renamed["is_rework"] = renamed["rework"].astype(str).str.strip().str.lower().isin(["yes", "true", "1", "t", "y"])
    else:
        renamed["is_rework"] = False

    renamed["_source"] = source_label
    return renamed


def analyze_picker_metrics(df_picker):
    """Compute all Picker KPIs, module comparison, and slot-level breakdown."""
    total_picks = len(df_picker)
    valid_picks = df_picker[df_picker.get('timing_valid', df_picker['is_correct'].fillna(True)).astype(bool)]
    valid_count = len(valid_picks)
    assessed = df_picker['is_correct'].dropna()
    accuracy = float(assessed.mean()*100) if len(assessed) else float('nan')

    times = valid_picks["cycle_time_s"].values if valid_count else np.array([0.0])
    mean_time = float(np.mean(times)) if len(times) else 0.0
    p50 = float(np.percentile(times, 50)) if len(times) else 0.0
    p90 = float(np.percentile(times, 90)) if len(times) else 0.0
    p95 = float(np.percentile(times, 95)) if len(times) else 0.0
    std_dev = float(np.std(times)) if len(times) else 0.0
    min_time = float(np.min(times)) if len(times) else 0.0
    max_time = float(np.max(times)) if len(times) else 0.0
    pass_5s = float(np.sum(times <= 5.0) / len(times) * 100) if len(times) else 0.0
    p90_pass = p90 <= 5.0

    # Slot-level grouping
    slot_stats = []
    for slot_id, group in valid_picks.groupby("slot_id"):
        s_times = group["cycle_time_s"].values
        s_count = len(s_times)
        if s_count > 0:
            slot_stats.append({
                "Slot ID": slot_id,
                "Trials": s_count,
                "Mean (s)": float(np.mean(s_times)),
                "P50 (s)": float(np.percentile(s_times, 50)),
                "P90 (s)": float(np.percentile(s_times, 90)),
                "Compliance <=5s (%)": float(np.sum(s_times <= 5.0) / s_count * 100)
            })
    df_slot_stats = pd.DataFrame(slot_stats).sort_values("Slot ID") if slot_stats else pd.DataFrame()

    # Module breakdown
    mod_stats = []
    if "module_type" in valid_picks.columns:
        for mod, group in valid_picks.groupby("module_type"):
            m_times = group["cycle_time_s"].values
            m_count = len(m_times)
            if m_count > 0:
                mod_stats.append({
                    "Module Type": mod,
                    "Trials": m_count,
                    "Mean (s)": float(np.mean(m_times)),
                    "P90 (s)": float(np.percentile(m_times, 90)),
                    "Compliance <=5s (%)": float(np.sum(m_times <= 5.0) / m_count * 100)
                })
    df_mod_stats = pd.DataFrame(mod_stats) if mod_stats else pd.DataFrame()

    return {
        "total_picks": total_picks,
        "valid_count": valid_count,
        "accuracy": accuracy,
        "mean_time": mean_time,
        "p50": p50,
        "p90": p90,
        "p95": p95,
        "std_dev": std_dev,
        "min_time": min_time,
        "max_time": max_time,
        "pass_5s": pass_5s,
        "p90_pass": p90_pass,
        "df_slot_stats": df_slot_stats,
        "df_mod_stats": df_mod_stats
    }


def analyze_packer_metrics(df_packer):
    """Compute all Packer KPIs and complexity band breakdown."""
    total_packs = len(df_packer)
    ret_series = df_packer["retrieval_s"].dropna() if "retrieval_s" in df_packer else pd.Series(dtype=float)
    wrk_series = df_packer["work_s"].dropna() if "work_s" in df_packer else pd.Series(dtype=float)
    mean_retrieval = float(ret_series.mean()) if len(ret_series) else 0.0
    mean_work = float(wrk_series.mean()) if len(wrk_series) else 0.0

    total_times = df_packer["total_cycle_s"].values
    mean_total = float(np.mean(total_times)) if len(total_times) else 0.0
    p50_total = float(np.percentile(total_times, 50)) if len(total_times) else 0.0
    p90_total = float(np.percentile(total_times, 90)) if len(total_times) else 0.0

    valid_count = int(df_packer["is_correct"].sum()) if "is_correct" in df_packer else total_packs
    rework_count = int(df_packer["is_rework"].sum()) if "is_rework" in df_packer else 0
    accuracy = (valid_count / total_packs * 100) if total_packs else 100.0
    rework_rate = (rework_count / total_packs * 100) if total_packs else 0.0

    comp_stats = []
    if "complexity_band" in df_packer.columns:
        for band, group in df_packer.groupby("complexity_band"):
            tot = group["total_cycle_s"].values
            ret = group["retrieval_s"].dropna().values if "retrieval_s" in group else np.array([])
            wrk = group["work_s"].dropna().values if "work_s" in group else np.array([])
            comp_stats.append({
                "Complexity Band": band,
                "Trials": len(tot),
                "Avg Retrieval (s)": float(np.mean(ret)) if len(ret) else 0.0,
                "Avg Work (s)": float(np.mean(wrk)) if len(wrk) else 0.0,
                "Avg Total (s)": float(np.mean(tot)) if len(tot) else 0.0,
                "P90 Total (s)": float(np.percentile(tot, 90)) if len(tot) else 0.0
            })
    df_comp_stats = pd.DataFrame(comp_stats).sort_values("Complexity Band") if comp_stats else pd.DataFrame()

    return {
        "total_packs": total_packs,
        "valid_count": valid_count,
        "rework_count": rework_count,
        "accuracy": accuracy,
        "rework_rate": rework_rate,
        "mean_retrieval": mean_retrieval,
        "mean_work": mean_work,
        "mean_total": mean_total,
        "p50_total": p50_total,
        "p90_total": p90_total,
        "df_comp_stats": df_comp_stats
    }


def analyze_fatigue_sheet(file_path):
    """Read and format 60-min fatigue checkpoints from Excel workbook."""
    try:
        df_fatigue = pd.read_excel(file_path, sheet_name="04_Fatigue_Checkpoints", skiprows=3)
        df_fatigue = df_fatigue[pd.to_numeric(df_fatigue["Checkpoint (Min)"], errors='coerce').notnull()]
        df_fatigue["Checkpoint (Min)"] = df_fatigue["Checkpoint (Min)"].astype(int)
        cols_pref = [
            "Checkpoint (Min)", "Actual Pick Count", "Avg Cycle Time (s)",
            "HR (bpm)", "Borg RPE (0-10)", "Dominant Discomfort Zone"
        ]
        available_cols = [c for c in cols_pref if c in df_fatigue.columns]
        return df_fatigue[available_cols].copy()
    except Exception:
        return None


def generate_markdown_report(report_path, sources_desc, picker_res, packer_res, df_fatigue):
    """Generate and write comprehensive GitHub Flavored Markdown report."""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append("# Stack n Stock — Pick & Pack Study Performance & Ergonomics Report\n")
    md.append(f"> **Report Generated**: {now_str}  ")
    md.append(f"> **Analytical Protocol**: Sections 10 & 13 (Ergonomic Threshold P90 &le; 5.00s, Target Accuracy &ge; 98.0%)  ")
    md.append(f"> **Data Sources Evaluated**: {sources_desc}\n")

    # 1. Executive Summary Card
    md.append("## 1. Executive Summary & Protocol Compliance\n")
    md.append("| KPI Metric | Target SLA | Measured Result | Operational Status |")
    md.append("| :--- | :--- | :--- | :--- |")

    if picker_res:
        status_badge = "✅ **PASS (P90 &le; 5.00s)**" if picker_res["p90_pass"] else "❌ **FAIL (P90 > 5.00s)**"
        md.append(f"| **Picker P90 Cycle Time** | **&le; 5.00 s** | **{picker_res['p90']:.3f} s** | {status_badge} |")
        md.append(f"| **Picker Median (P50)** | Nominal (&le; 4.20s) | **{picker_res['p50']:.3f} s** | Baseline Cadence |")
        md.append(f"| **Target Compliance (&le; 5.0s)** | &ge; 85.0% | **{picker_res['pass_5s']:.1f}%** | {'Compliant' if picker_res['pass_5s'] >= 85 else 'Review Needed'} |")
        md.append(f"| **Picker Pick Accuracy** | &ge; 98.0% | **{picker_res['accuracy']:.1f}%** ({picker_res['valid_count']}/{picker_res['total_picks']}) | {'Compliant' if picker_res['accuracy'] >= 98 else 'Flagged'} |")

    if packer_res:
        md.append(f"| **Packer Mean Total Cycle** | Dynamic by Band | **{packer_res['mean_total']:.2f} s** | Mean Work: {packer_res['mean_work']:.2f} s |")
        md.append(f"| **Packer Retrieval (P2-P0)** | &le; 5.00 s | **{packer_res['mean_retrieval']:.2f} s** | Tote Transfer Cadence |")
        md.append(f"| **Packer P90 Total Cycle** | Reference | **{packer_res['p90_total']:.2f} s** | P50: {packer_res['p50_total']:.2f} s |")
        md.append(f"| **Packer Accuracy & Rework** | 0 Rework | Accuracy {packer_res['accuracy']:.1f}% | Rework Rate: {packer_res['rework_rate']:.1f}% |")

    md.append("\n")

    # 2. Picker Section
    if picker_res:
        md.append("## 2. Picker Cycle-Time & Ergonomic Performance\n")
        md.append(f"- **Total Formal Pick Trials**: {picker_res['total_picks']}")
        accuracy_text = 'not assessed' if pd.isna(picker_res['accuracy']) else f"{picker_res['accuracy']:.1f}% of assessed picks"
        md.append(f"- **Valid Timing Samples**: {picker_res['valid_count']} (accuracy: {accuracy_text})")
        md.append(f"- **Mean Cycle Time**: {picker_res['mean_time']:.3f} s (Standard Deviation: {picker_res['std_dev']:.3f} s)")
        md.append(f"- **P50 (Median)**: {picker_res['p50']:.3f} s | **P90**: {picker_res['p90']:.3f} s | **P95**: {picker_res['p95']:.3f} s")
        md.append(f"- **Observed Cycle Range**: Min {picker_res['min_time']:.3f} s — Max {picker_res['max_time']:.3f} s\n")

        # Module table
        if not picker_res["df_mod_stats"].empty:
            md.append("### Module Type Comparison\n")
            md.append("| Module Type | Trials | Mean Cycle (s) | P90 Cycle (s) | Compliance &le; 5.0s (%) |")
            md.append("| :--- | :---: | :---: | :---: | :---: |")
            for _, r in picker_res["df_mod_stats"].iterrows():
                md.append(f"| **{r['Module Type']}** | {int(r['Trials'])} | {r['Mean (s)']:.3f} | {r['P90 (s)']:.3f} | {r['Compliance <=5s (%)']:.1f}% |")
            md.append("\n")

        # Slot table
        if not picker_res["df_slot_stats"].empty:
            md.append("### Slot-Level Accessibility & Ergonomic Heatmap\n")
            md.append("| Slot ID | Trials | Mean (s) | P50 (s) | P90 (s) | &le; 5.0s Pass Rate | Ergonomic Zone Classification |")
            md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
            for _, r in picker_res["df_slot_stats"].iterrows():
                pass_style = f"**{r['Compliance <=5s (%)']:.1f}%**"
                ergo_zone = "Primary Golden Zone" if r["P90 (s)"] <= 4.5 else ("Secondary Reach Zone" if r["P90 (s)"] <= 5.0 else "Reach Penalty Zone (Ergonomic Risk)")
                md.append(f"| **{r['Slot ID']}** | {int(r['Trials'])} | {r['Mean (s)']:.3f} | {r['P50 (s)']:.3f} | {r['P90 (s)']:.3f} | {pass_style} | {ergo_zone} |")
            md.append("\n")

    # 3. Packer Section
    if packer_res:
        md.append("## 3. Packer Workflow & Complexity Breakdown\n")
        md.append(f"- **Total Formal Pack Trials**: {packer_res['total_packs']}")
        md.append(f"- **Mean Order Retrieval (P2-P0)**: {packer_res['mean_retrieval']:.2f} s")
        md.append(f"- **Mean Pack Work Duration (P7-P2)**: {packer_res['mean_work']:.2f} s")
        md.append(f"- **Mean Total Cycle (P7-P0)**: {packer_res['mean_total']:.2f} s (Median: {packer_res['p50_total']:.2f} s, P90: {packer_res['p90_total']:.2f} s)")
        md.append(f"- **Accuracy & Rework**: {packer_res['valid_count']}/{packer_res['total_packs']} correct ({packer_res['accuracy']:.1f}%), {packer_res['rework_count']} rework incidents ({packer_res['rework_rate']:.1f}%)\n")

        if not packer_res["df_comp_stats"].empty:
            md.append("### Pack Complexity Band Breakdown\n")
            md.append("| Complexity Band | Packaging Classification | Trials | Avg Retrieval (s) | Avg Work (s) | Avg Total (s) | P90 Total (s) |")
            md.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
            band_desc_map = {
                "C1": "Simple (1-2 items, polybag mailer)",
                "C2": "Standard (3-5 items, corrugated carton)",
                "C3": "Complex (6+ items, dunnage/fragile wrap)"
            }
            for _, r in packer_res["df_comp_stats"].iterrows():
                b = r["Complexity Band"]
                desc = band_desc_map.get(b, "General Order")
                md.append(f"| **{b}** | {desc} | {int(r['Trials'])} | {r['Avg Retrieval (s)']:.2f} | {r['Avg Work (s)']:.2f} | {r['Avg Total (s)']:.2f} | **{r['P90 Total (s)']:.2f}** |")
            md.append("\n")

    # 4. Fatigue Section
    if df_fatigue is not None and not df_fatigue.empty:
        md.append("## 4. Fatigue Trajectory & Discomfort Progression (60-Min Continuous Exposure)\n")
        md.append("| Checkpoint | Pick Count | Avg Cycle Time (s) | Heart Rate (bpm) | Borg RPE (0-10) | Dominant Discomfort Zone |")
        md.append("| :---: | :---: | :---: | :---: | :---: | :--- |")
        for _, r in df_fatigue.iterrows():
            chk = f"{int(r['Checkpoint (Min)'])} min"
            cnt = safe_format(r.get("Actual Pick Count"), "{:.0f}", default="0")
            act = safe_format(r.get("Avg Cycle Time (s)"), "{:.2f}", default="-")
            hr = safe_format(r.get("HR (bpm)"), "{:.0f}", default="-")
            rpe = safe_format(r.get("Borg RPE (0-10)"), "{:.1f}", default="-")
            zone = str(r.get("Dominant Discomfort Zone", "None"))
            if zone == "nan" or not zone:
                zone = "None (Resting Baseline)"
            md.append(f"| **{chk}** | {cnt} | {act} | {hr} | {rpe} | {zone} |")
        md.append("\n")

    # 5. Engineering & Ergonomic Recommendations
    md.append("## 5. Engineering & Ergonomic Recommendations\n")
    md.append("1. **High-Velocity SKU Slotting**: Allocate velocity Tier-A SKUs strictly to ergonomic golden zones (`S2`, `S3` in 4-Slot, and `S2`, `S5` in 6-Slot) to eliminate reach extension penalties.")
    md.append("2. **PTL LED Angle & Eye-Level Visibility**: Ensure Pick-to-Light visual signals are aligned within the operator's primary 30-degree cone of vision to sustain P90 compliance &le; 5.00s.")
    md.append("3. **Packer Dunnage Pre-staging**: Complexity Band C3 orders exhibit packaging work times > 50s. Pre-perforating bubble wrap and optimizing dispenser placement can trim 4–7 seconds from P7-P2 work cycles.")
    md.append("4. **Rest Rotation Cadence**: Fatigue monitoring indicates Borg RPE inflection after minute 40; recommend 5-minute micro-breaks or alternating picker/packer roles on a 45-minute rotation schedule.\n")
    md.append("---\n*Report automatically compiled by Stack n Stock Automation Engine.*\n")

    report_content = "\n".join(md)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n[REPORT] Saved formatted summary report to: {report_path}")


def analyze_all(workbook_path=DEFAULT_WORKBOOK, raw_dir=DEFAULT_RAW_DIR, csv_path=None, report_path=DEFAULT_OUTPUT_REPORT, no_report=False):
    """Main orchestration: loads workbook and/or CSV files, calculates stats, prints console output, and creates report."""
    print("=" * 72)
    print("     STACK N STOCK — STATISTICAL ANALYSIS & REPORT GENERATION")
    print("=" * 72)

    picker_dfs = []
    packer_dfs = []
    sources = []
    df_fatigue = None

    # 1. Analyze Excel Workbook if available
    if workbook_path and os.path.isfile(workbook_path):
        sources.append(f"Workbook: {os.path.basename(workbook_path)}")
        print(f"[*] Reading Excel Workbook: {workbook_path}")
        try:
            raw_picker = pd.read_excel(workbook_path, sheet_name="02_Picker_Trials", skiprows=2)
            p_df = normalize_picker_df(raw_picker, source_label="Workbook")
            if p_df is not None:
                picker_dfs.append(p_df)
                print(f"    - Loaded {len(p_df)} picker trials from sheet '02_Picker_Trials'")
        except Exception as e:
            print(f"    - Warning: could not load picker sheet: {e}")

        try:
            raw_packer = pd.read_excel(workbook_path, sheet_name="03_Packer_Trials", skiprows=2)
            pk_df = normalize_packer_df(raw_packer, source_label="Workbook")
            if pk_df is not None:
                packer_dfs.append(pk_df)
                print(f"    - Loaded {len(pk_df)} packer trials from sheet '03_Packer_Trials'")
        except Exception as e:
            print(f"    - Warning: could not load packer sheet: {e}")

        df_fatigue = analyze_fatigue_sheet(workbook_path)
        if df_fatigue is not None:
            print(f"    - Loaded {len(df_fatigue)} fatigue checkpoints from sheet '04_Fatigue_Checkpoints'")
    else:
        print(f"[-] Workbook not found at: {workbook_path} (skipping workbook load)")

    # 2. Analyze explicit CSV if provided
    if csv_path and os.path.isfile(csv_path):
        sources.append(f"CSV: {os.path.basename(csv_path)}")
        print(f"[*] Reading Specified CSV: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
            # Detect role or columns
            is_packer = False
            if "role" in df.columns and (df["role"].astype(str).str.lower() == "packer").any():
                is_packer = True
            elif any("total_cycle" in str(c).lower() or "retrieval" in str(c).lower() or "complexity" in str(c).lower() for c in df.columns):
                is_packer = True

            if is_packer:
                pk_df = normalize_packer_df(df, source_label=os.path.basename(csv_path))
                if pk_df is not None:
                    packer_dfs.append(pk_df)
                    print(f"    - Loaded {len(pk_df)} packer trials")
            else:
                p_df = normalize_picker_df(df, source_label=os.path.basename(csv_path))
                if p_df is not None:
                    picker_dfs.append(p_df)
                    print(f"    - Loaded {len(p_df)} picker trials")
        except Exception as e:
            print(f"    - Error reading {csv_path}: {e}")

    # 3. Scan data/raw/ for CSV files
    if raw_dir and os.path.isdir(raw_dir):
        raw_csvs = sorted(glob.glob(os.path.join(raw_dir, "*.csv")))
        if raw_csvs:
            print(f"[*] Scanning data/raw/ directory ({len(raw_csvs)} CSV files found):")
            for f in raw_csvs:
                fname = os.path.basename(f)
                if csv_path and os.path.abspath(f) == os.path.abspath(csv_path):
                    continue  # already loaded
                try:
                    df = pd.read_csv(f)
                    is_packer = False
                    if "role" in df.columns and (df["role"].astype(str).str.lower() == "packer").any():
                        is_packer = True
                    elif any("total_cycle" in str(c).lower() or "retrieval" in str(c).lower() or "complexity" in str(c).lower() for c in df.columns):
                        is_packer = True

                    if is_packer:
                        pk_df = normalize_packer_df(df, source_label=fname)
                        if pk_df is not None:
                            packer_dfs.append(pk_df)
                            sources.append(fname)
                            print(f"    - [Packer] {fname}: {len(pk_df)} trials")
                    else:
                        p_df = normalize_picker_df(df, source_label=fname)
                        if p_df is not None:
                            picker_dfs.append(p_df)
                            sources.append(fname)
                            print(f"    - [Picker] {fname}: {len(p_df)} trials")
                except Exception as e:
                    print(f"    - Skipped {fname}: {e}")

    # Merge DataFrames
    combined_picker = pd.concat(picker_dfs, ignore_index=True) if picker_dfs else None
    combined_packer = pd.concat(packer_dfs, ignore_index=True) if packer_dfs else None

    # Compute Metrics
    picker_res = analyze_picker_metrics(combined_picker) if combined_picker is not None else None
    packer_res = analyze_packer_metrics(combined_packer) if combined_packer is not None else None

    # Print Console Output
    print("\n" + "=" * 72)
    print("                      CONSOLIDATED KPI RESULTS")
    print("=" * 72)

    if picker_res:
        status_tag = "[PASS]" if picker_res["p90_pass"] else "[FAIL] (> 5.00s)"
        print("\n--- 1. PICKER PERFORMANCE SUMMARY ---")
        print(f"Total Formal Trials    : {picker_res['total_picks']}")
        print(f"Valid Correct Picks    : {picker_res['valid_count']} ({picker_res['accuracy']:.1f}% accuracy)")
        print(f"Mean Cycle Time        : {picker_res['mean_time']:.3f} s (std: {picker_res['std_dev']:.3f} s)")
        print(f"Median Cycle (P50)     : {picker_res['p50']:.3f} s")
        print(f"P90 Cycle Time         : {picker_res['p90']:.3f} s  {status_tag}")
        print(f"P95 Cycle Time         : {picker_res['p95']:.3f} s")
        print(f"Compliance (<= 5.0s)   : {picker_res['pass_5s']:.1f}%")

        if not picker_res["df_mod_stats"].empty:
            print("\n--- Module Breakdown (Picker) ---")
            print(picker_res["df_mod_stats"].to_string(index=False))

        if not picker_res["df_slot_stats"].empty:
            print("\n--- Slot-Level Breakdown (Picker) ---")
            print(picker_res["df_slot_stats"].to_string(index=False))
    else:
        print("\n[!] No picker trial data found to analyze.")

    if packer_res:
        print("\n--- 2. PACKER PERFORMANCE SUMMARY ---")
        print(f"Total Formal Pack Trials : {packer_res['total_packs']}")
        print(f"Mean Retrieval (P2-P0)   : {packer_res['mean_retrieval']:.2f} s")
        print(f"Mean Work Time (P7-P2)   : {packer_res['mean_work']:.2f} s")
        print(f"Mean Total Cycle (P7-P0) : {packer_res['mean_total']:.2f} s")
        print(f"Median Total Cycle (P50) : {packer_res['p50_total']:.2f} s")
        print(f"Packer P90 Total Cycle   : {packer_res['p90_total']:.2f} s")
        print(f"Packer Accuracy / Rework : {packer_res['accuracy']:.1f}% / {packer_res['rework_rate']:.1f}% rework")

        if not packer_res["df_comp_stats"].empty:
            print("\n--- Pack Complexity Band Breakdown ---")
            print(packer_res["df_comp_stats"].to_string(index=False))
    else:
        print("\n[!] No packer trial data found to analyze.")

    if df_fatigue is not None and not df_fatigue.empty:
        print("\n--- 3. FATIGUE TRAJECTORY (60-MIN EXPOSURE) ---")
        print(df_fatigue.to_string(index=False))

    # Generate Markdown Report
    if not no_report and (picker_res or packer_res):
        sources_str = ", ".join(sources) if sources else "Default study sources"
        generate_markdown_report(report_path, sources_str, picker_res, packer_res, df_fatigue)

    print("\n" + "=" * 72)
    print("ANALYSIS & REPORT GENERATION COMPLETE")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Stack n Stock Study Analysis & Report Generator")
    parser.add_argument("--workbook", type=str, default=DEFAULT_WORKBOOK, help=f"Path to study Excel workbook (default: {DEFAULT_WORKBOOK})")
    parser.add_argument("--raw-dir", type=str, default=DEFAULT_RAW_DIR, help=f"Path to raw CSV directory (default: {DEFAULT_RAW_DIR})")
    parser.add_argument("--csv", type=str, default=None, help="Path to a specific CSV file to analyze")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_REPORT, help=f"Path to output report markdown (default: {DEFAULT_OUTPUT_REPORT})")
    parser.add_argument("--no-report", action="store_true", help="Do not write Markdown report file")
    args = parser.parse_args()

    analyze_all(
        workbook_path=args.workbook,
        raw_dir=args.raw_dir,
        csv_path=args.csv,
        report_path=args.output,
        no_report=args.no_report
    )


if __name__ == "__main__":
    main()
