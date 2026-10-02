"""
Stack n Stock — Pick & Pack Study Comprehensive Automated Test Suite
===================================================================
Covers:
1. Balanced Anti-Pattern Randomizer (scripts/balanced_randomizer.py)
   - Slot frequency balance across picker & packer pools
   - Zero consecutive slot streaks constraint
   - Sequence conditional transition entropy > 2.1 bits
2. Ergonomic & Kinematics Predictive Model (scripts/ergonomic_predictive_model.py)
   - Hick-Hyman cognitive decision latency
   - Fitts' Law reach-acquisition time & bin-tilt angle delta correction
   - Pick-to-light confirmation tech benchmark & P90 SLA prediction (<= 5.00s)
3. Statistical Analysis & Report Engine (scripts/analyze_study.py)
   - Exact cycle-time percentiles (P50, P90, P95) & compliance calculations
   - Robust DataFrame normalizers and dirty telemetry handling
   - Multi-source CSV telemetry ingestion from data/raw/
   - Markdown executive report generation & structural verification
4. Study Portal Local HTTP Server & Telemetry API (portal/launch_portal.py)
   - Live server lifecycle & CORS pre-flight handling
   - /api/save_csv POST endpoint data persistence & timestamping
   - Raw payload fallback & 400 Bad Request rejection on empty telemetry

Execution:
    python -m unittest tests/test_study_suite.py
"""

import os
import sys
import io
import contextlib
import json
import math
import glob
import shutil
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer

import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.balanced_randomizer import (
    generate_balanced_picker_pool,
    generate_balanced_packer_pool,
    compute_sequence_entropy,
)
from scripts.ergonomic_predictive_model import ErgonomicKinematicsModel
from scripts.analyze_study import (
    normalize_picker_df,
    normalize_packer_df,
    analyze_picker_metrics,
    analyze_packer_metrics,
    generate_markdown_report,
    analyze_all,
    DEFAULT_RAW_DIR,
    DEFAULT_WORKBOOK,
)
import portal.launch_portal as portal_server
from portal.launch_portal import PortalRequestHandler, find_available_port


class TestBalancedRandomizer(unittest.TestCase):
    """Unit tests for scripts/balanced_randomizer.py."""

    def test_picker_pool_frequency_balance_4_slots(self):
        """Verify that 4-slot picker pool has exactly reps_per_slot trials per slot."""
        slots = ["S1", "S2", "S3", "S4"]
        reps = 10
        pool = generate_balanced_picker_pool(slots=slots, reps_per_slot=reps, seed=42)

        self.assertEqual(len(pool), len(slots) * reps)
        counts = {}
        for trial in pool:
            s = trial["slot_id"]
            counts[s] = counts.get(s, 0) + 1

        for s in slots:
            self.assertEqual(counts[s], reps, f"Slot {s} does not have exactly {reps} trials")

        # Verify sequential trial IDs
        trial_ids = [t["trial_id"] for t in pool]
        self.assertEqual(trial_ids, list(range(1, len(pool) + 1)))

    def test_picker_pool_frequency_balance_6_slots(self):
        """Verify that 6-slot picker pool has uniform distribution across all slots."""
        slots = ["S1", "S2", "S3", "S4", "S5", "S6"]
        reps = 15
        pool = generate_balanced_picker_pool(slots=slots, reps_per_slot=reps, seed=101)

        self.assertEqual(len(pool), len(slots) * reps)
        counts = {}
        for trial in pool:
            s = trial["slot_id"]
            counts[s] = counts.get(s, 0) + 1

        for s in slots:
            self.assertEqual(counts[s], reps)

    def test_picker_pool_zero_consecutive_streaks_across_seeds(self):
        """Verify anti-streak constraint: zero adjacent duplicate slots across multiple seeds."""
        test_seeds = [42, 100, 2026, 7777, 99999]
        slots = ["S1", "S2", "S3", "S4", "S5", "S6"]

        for seed in test_seeds:
            pool = generate_balanced_picker_pool(slots=slots, reps_per_slot=10, seed=seed)
            seq = [t["slot_id"] for t in pool]
            streaks = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
            self.assertEqual(streaks, 0, f"Found {streaks} consecutive streaks with seed {seed}")

    def test_packer_pool_slot_and_complexity_balance(self):
        """Verify packer pool frequency balance and orthogonal complexity band allocation."""
        slots = ["S1", "S2", "S3", "S4", "S5", "S6"]
        reps = 6
        pool = generate_balanced_packer_pool(slots=slots, reps_per_slot=reps, seed=42)

        self.assertEqual(len(pool), len(slots) * reps)

        # Check slot counts
        counts = {}
        comp_per_slot = {s: {"C1": 0, "C2": 0, "C3": 0} for s in slots}
        for trial in pool:
            s = trial["slot_id"]
            c = trial["complexity_band"]
            counts[s] = counts.get(s, 0) + 1
            comp_per_slot[s][c] += 1

        for s in slots:
            self.assertEqual(counts[s], reps)
            # 6 reps distributed across C1, C2, C3 -> 2 of each
            self.assertEqual(comp_per_slot[s]["C1"], 2)
            self.assertEqual(comp_per_slot[s]["C2"], 2)
            self.assertEqual(comp_per_slot[s]["C3"], 2)

        # Check zero consecutive slot streaks in packer pool
        seq = [t["slot_id"] for t in pool]
        streaks = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
        self.assertEqual(streaks, 0, f"Found {streaks} consecutive streaks in packer pool")

    def test_sequence_entropy_exceeds_threshold(self):
        """Verify conditional transition entropy H(S_j | S_i) > 2.1 bits for 6-slot pool."""
        pool = generate_balanced_picker_pool(
            slots=["S1", "S2", "S3", "S4", "S5", "S6"],
            reps_per_slot=10,
            seed=42
        )
        seq = [t["slot_id"] for t in pool]
        entropy = compute_sequence_entropy(seq)

        # Requirement: entropy > 2.1 bits
        self.assertGreater(
            entropy, 2.1,
            f"Expected entropy > 2.1 bits, but measured {entropy:.4f} bits"
        )
        # Cannot exceed theoretical max for 5 possible non-identical transitions: log2(5) ~= 2.322
        self.assertLessEqual(entropy, math.log2(5.0) + 1e-6)

    def test_entropy_mathematical_properties(self):
        """Verify entropy calculation on deterministic and uniform transition sequences."""
        # Purely deterministic 2-slot alternation: S1 always -> S2, S2 always -> S1
        det_seq = ["S1", "S2"] * 20
        det_entropy = compute_sequence_entropy(det_seq)
        self.assertAlmostEqual(det_entropy, 0.0, places=4)

        # Single repeated state: no branching
        repeat_seq = ["S1"] * 10
        repeat_entropy = compute_sequence_entropy(repeat_seq)
        self.assertAlmostEqual(repeat_entropy, 0.0, places=4)


class TestErgonomicPredictiveModel(unittest.TestCase):
    """Unit tests for scripts/ergonomic_predictive_model.py."""

    def test_hick_hyman_reaction_latencies(self):
        """Verify Hick-Hyman Law RT = a + b * log2(N) for 4-Slot and 6-Slot configurations."""
        model_4 = ErgonomicKinematicsModel(module_type="4-Slot")
        rt_4 = model_4.compute_reaction_time()
        # N=4: 0.180 + 0.080 * log2(4) = 0.180 + 0.160 = 0.340s
        self.assertAlmostEqual(rt_4, 0.340, places=3)

        model_6 = ErgonomicKinematicsModel(module_type="6-Slot")
        rt_6 = model_6.compute_reaction_time()
        # N=6: 0.180 + 0.080 * log2(6) = 0.180 + 0.080 * 2.5849625 ~= 0.3868s
        expected_rt_6 = 0.180 + 0.080 * math.log2(6)
        self.assertAlmostEqual(rt_6, expected_rt_6, places=4)

        # Reaction time for 6 candidates must be strictly higher than for 4 candidates
        self.assertGreater(rt_6, rt_4)

    def test_fitts_law_reach_times_and_dimensions(self):
        """Verify Fitts' Law MT = a_m + b_m * log2(2D / W) calculations and slot differentials."""
        # 4-Slot: W = 280mm
        m4 = ErgonomicKinematicsModel(module_type="4-Slot", bin_angle_deg=20.0)
        # S1: D = 560mm -> 2D / W = 1120 / 280 = 4.0 -> log2(4) = 2.0 -> MT = 0.250 + 0.350 * 2 = 0.950s
        mt_s1 = m4.compute_reach_acquisition_time("S1")
        self.assertAlmostEqual(mt_s1, 0.950, places=3)

        # S3: D = 410mm -> 2D / W = 820 / 280 = 2.92857 -> log2(2.92857) ~= 1.55018 -> MT ~= 0.79256s
        mt_s3 = m4.compute_reach_acquisition_time("S3")
        expected_s3 = 0.250 + 0.350 * math.log2(820.0 / 280.0)
        self.assertAlmostEqual(mt_s3, expected_s3, places=3)

        # Deep slot (S1) reach time must exceed front slot (S3) reach time
        self.assertGreater(mt_s1, mt_s3)

        # 6-Slot: W = 185mm
        m6 = ErgonomicKinematicsModel(module_type="6-Slot", bin_angle_deg=20.0)
        # S6 extended lateral reach (660mm) vs S4 front slot (420mm)
        mt_s6 = m6.compute_reach_acquisition_time("S6")
        mt_s4 = m6.compute_reach_acquisition_time("S4")
        self.assertGreater(mt_s6, mt_s4)

    def test_fitts_law_bin_tilt_angle_correction(self):
        """Verify that increasing bin tilt recovers reach distance and reduces movement time."""
        m_flat = ErgonomicKinematicsModel(module_type="6-Slot", bin_angle_deg=20.0)
        m_tilted = ErgonomicKinematicsModel(module_type="6-Slot", bin_angle_deg=25.0)

        mt_flat = m_flat.compute_reach_acquisition_time("S1")
        mt_tilted = m_tilted.compute_reach_acquisition_time("S1")

        # 5 deg tilt recovery = 5 * 12mm = 60mm forward reach recovery
        self.assertLess(mt_tilted, mt_flat)

        # Verify distance clamping at 350.0 mm
        m_extreme_tilt = ErgonomicKinematicsModel(module_type="6-Slot", bin_angle_deg=60.0)
        mt_clamped = m_extreme_tilt.compute_reach_acquisition_time("S4")
        expected_clamped = 0.250 + 0.350 * math.log2(700.0 / 185.0)
        self.assertAlmostEqual(mt_clamped, expected_clamped, places=3)

    def test_confirmation_technologies(self):
        """Verify latencies across user-acknowledgement hardware interfaces."""
        tech_cases = {
            "screen_tap": 0.720,
            "mechanical_button": 0.520,
            "capacitive_bar": 0.220,
            "light_curtain": 0.085,
            "unknown_hardware": 0.250,  # Fallback default
        }
        for tech, expected_lat in tech_cases.items():
            m = ErgonomicKinematicsModel(confirmation_tech=tech)
            self.assertAlmostEqual(m.compute_confirmation_time(), expected_lat, places=3)

    def test_simulate_pick_cycle_component_integrity(self):
        """Verify that simulated pick cycle totals match the exact sum of biomechanical sub-stages."""
        model = ErgonomicKinematicsModel(module_type="6-Slot", confirmation_tech="light_curtain")
        res = model.simulate_pick_cycle("S2")

        expected_human = round(
            res["t_reaction"] + res["t_reach"] + res["t_transfer"] + res["t_confirm"], 3
        )
        # The sum of 4 pre-rounded components can differ from the rounded sum by at most 0.002 due to precision rounding
        self.assertAlmostEqual(res["t_human"], expected_human, delta=0.002)

        expected_total = round(res["t_human"] + res["t_system"], 3)
        self.assertAlmostEqual(res["t_total"], expected_total, delta=0.002)

    def test_p90_sla_prediction(self):
        """Verify P90 SLA prediction logic and optimization headroom."""
        # Baseline model with mechanical button
        base_model = ErgonomicKinematicsModel(
            module_type="6-Slot",
            bin_angle_deg=20.0,
            confirmation_tech="mechanical_button"
        )
        dist_base = base_model.predict_module_distribution()
        self.assertEqual(dist_base["p90_target_s"], 5.000)
        self.assertIn("median_cycle_s", dist_base)
        self.assertIn("p90_cycle_s", dist_base)
        self.assertEqual(len(dist_base["slot_breakdown"]), 6)

        # Optimized model: 22.5 deg tilt + optical light curtain
        opt_model = ErgonomicKinematicsModel(
            module_type="6-Slot",
            bin_angle_deg=22.5,
            confirmation_tech="light_curtain"
        )
        dist_opt = opt_model.predict_module_distribution()

        # Both predict cycle distribution; optimized model yields faster P90
        self.assertTrue(dist_opt["meets_p90_sla"])
        self.assertLess(dist_opt["p90_cycle_s"], 5.000)
        self.assertLess(dist_opt["p90_cycle_s"], dist_base["p90_cycle_s"])

        # Delta should be >= 0.4s improvement from optical curtain + tilt recovery
        delta_p90 = dist_base["p90_cycle_s"] - dist_opt["p90_cycle_s"]
        self.assertGreaterEqual(delta_p90, 0.40)


class TestAnalyzeStudy(unittest.TestCase):
    """Unit and integration tests for scripts/analyze_study.py."""

    def test_percentile_calculations_p50_p90_p95(self):
        """Verify accurate calculation of P50, P90, P95, mean, and compliance against numpy."""
        # Deterministic sequence of 100 values from 3.01 to 6.00
        cycle_times = np.linspace(3.01, 6.00, 100)
        df_picker = pd.DataFrame({
            "cycle_time_s": cycle_times,
            "is_correct": [True] * 95 + [False] * 5,  # 95% accuracy
            "slot_id": ["S1", "S2", "S3", "S4"] * 25,
            "module_type": ["4-Slot"] * 100,
        })

        metrics = analyze_picker_metrics(df_picker)

        valid_times = cycle_times[:95]
        expected_p50 = float(np.percentile(valid_times, 50))
        expected_p90 = float(np.percentile(valid_times, 90))
        expected_p95 = float(np.percentile(valid_times, 95))
        expected_mean = float(np.mean(valid_times))

        self.assertAlmostEqual(metrics["p50"], expected_p50, places=3)
        self.assertAlmostEqual(metrics["p90"], expected_p90, places=3)
        self.assertAlmostEqual(metrics["p95"], expected_p95, places=3)
        self.assertAlmostEqual(metrics["mean_time"], expected_mean, places=3)
        self.assertEqual(metrics["total_picks"], 100)
        self.assertEqual(metrics["valid_count"], 95)
        self.assertAlmostEqual(metrics["accuracy"], 95.0, places=1)

        # Slot-level grouping check
        df_slots = metrics["df_slot_stats"]
        self.assertEqual(len(df_slots), 4)
        for _, row in df_slots.iterrows():
            self.assertIn(row["Slot ID"], ["S1", "S2", "S3", "S4"])
            self.assertGreater(row["Trials"], 0)

    def test_packer_metrics_and_complexity_bands(self):
        """Verify packer KPIs and complexity band breakdown calculations."""
        df_packer = pd.DataFrame({
            "total_cycle_s": [20.0, 22.0, 30.0, 35.0, 60.0, 70.0],
            "retrieval_s": [3.5, 3.8, 3.2, 3.6, 4.0, 4.2],
            "work_s": [16.5, 18.2, 26.8, 31.4, 56.0, 65.8],
            "complexity_band": ["C1", "C1", "C2", "C2", "C3", "C3"],
            "is_correct": [True, True, True, True, True, False],
            "is_rework": [False, False, False, False, True, False],
        })

        metrics = analyze_packer_metrics(df_packer)
        self.assertEqual(metrics["total_packs"], 6)
        self.assertEqual(metrics["valid_count"], 5)
        self.assertEqual(metrics["rework_count"], 1)
        self.assertAlmostEqual(metrics["mean_total"], np.mean([20.0, 22.0, 30.0, 35.0, 60.0, 70.0]), places=2)
        self.assertAlmostEqual(metrics["p50_total"], np.percentile([20.0, 22.0, 30.0, 35.0, 60.0, 70.0], 50), places=2)

        df_comp = metrics["df_comp_stats"]
        self.assertEqual(len(df_comp), 3)
        self.assertListEqual(list(df_comp["Complexity Band"]), ["C1", "C2", "C3"])

    def test_normalizers_resilience(self):
        """Verify normalizer handles varied column casing, aliases, and bad records."""
        # Picker DF with dirty column names
        raw_picker = pd.DataFrame({
            "TRIAL #": [1, 2, 3],
            "Cycle Time (s)": ["4.12", "invalid", "3.85"],
            "Correct?": ["Yes", "true", "0"],
            "Slot ID": ["S1", "S2", "S3"],
            "Module Type": ["4-Slot", "4-Slot", "4-Slot"],
        })
        norm_p = normalize_picker_df(raw_picker)
        self.assertIsNotNone(norm_p)
        # Row 2 with 'invalid' cycle time should be dropped
        self.assertEqual(len(norm_p), 2)
        self.assertIn("cycle_time_s", norm_p.columns)
        self.assertIn("is_correct", norm_p.columns)
        self.assertTrue(norm_p.iloc[0]["is_correct"])

        # Packer DF with alias columns
        raw_packer = pd.DataFrame({
            "Total Cycle Time": [25.5, 34.0],
            "Retrieval Sec": [3.2, 4.1],
            "Work Duration": [22.3, 29.9],
            "Complexity": ["c1", "c2"],
            "Rework": ["No", "Yes"],
        })
        norm_pk = normalize_packer_df(raw_packer)
        self.assertIsNotNone(norm_pk)
        self.assertEqual(len(norm_pk), 2)
        self.assertEqual(norm_pk.iloc[0]["complexity_band"], "C1")
        self.assertFalse(norm_pk.iloc[0]["is_rework"])
        self.assertTrue(norm_pk.iloc[1]["is_rework"])

    def test_csv_telemetry_ingestion_from_raw_dir(self):
        """Integration test: ingest existing CSV telemetry from data/raw/."""
        self.assertTrue(os.path.isdir(DEFAULT_RAW_DIR), f"Raw dir {DEFAULT_RAW_DIR} does not exist")
        csv_files = glob.glob(os.path.join(DEFAULT_RAW_DIR, "*.csv"))
        self.assertGreaterEqual(len(csv_files), 2, "Expected at least 2 telemetry CSVs in data/raw/")

        # Execute analysis pipeline in no-report mode
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_report = os.path.join(tmpdir, "test_report.md")
            # Ingest from DEFAULT_RAW_DIR without throwing exceptions
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                analyze_all(
                    workbook_path=DEFAULT_WORKBOOK,
                    raw_dir=DEFAULT_RAW_DIR,
                    report_path=temp_report,
                    no_report=False
                )
            self.assertTrue(os.path.isfile(temp_report))
            with open(temp_report, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("STACK N STOCK", content.upper())
            self.assertIn("Picker P90 Cycle Time", content)

    def test_markdown_report_generation_structure(self):
        """Verify markdown report structure, SLA badges, and ergonomic sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "generated_report.md")

            picker_res = {
                "total_picks": 50,
                "valid_count": 49,
                "accuracy": 98.0,
                "mean_time": 4.150,
                "p50": 4.120,
                "p90": 4.850,
                "p95": 5.020,
                "std_dev": 0.420,
                "min_time": 3.100,
                "max_time": 5.400,
                "pass_5s": 94.0,
                "p90_pass": True,
                "df_slot_stats": pd.DataFrame([
                    {"Slot ID": "S1", "Trials": 10, "Mean (s)": 4.1, "P50 (s)": 4.0, "P90 (s)": 4.4, "Compliance <=5s (%)": 100.0},
                    {"Slot ID": "S2", "Trials": 10, "Mean (s)": 3.9, "P50 (s)": 3.8, "P90 (s)": 4.2, "Compliance <=5s (%)": 100.0}
                ]),
                "df_mod_stats": pd.DataFrame([
                    {"Module Type": "4-Slot", "Trials": 50, "Mean (s)": 4.15, "P90 (s)": 4.85, "Compliance <=5s (%)": 94.0}
                ]),
            }

            packer_res = {
                "total_packs": 20,
                "valid_count": 20,
                "rework_count": 0,
                "accuracy": 100.0,
                "rework_rate": 0.0,
                "mean_retrieval": 3.50,
                "mean_work": 25.00,
                "mean_total": 28.50,
                "p50_total": 27.00,
                "p90_total": 35.00,
                "df_comp_stats": pd.DataFrame([
                    {"Complexity Band": "C1", "Trials": 10, "Avg Retrieval (s)": 3.2, "Avg Work (s)": 15.0, "Avg Total (s)": 18.2, "P90 Total (s)": 20.0},
                    {"Complexity Band": "C2", "Trials": 10, "Avg Retrieval (s)": 3.8, "Avg Work (s)": 35.0, "Avg Total (s)": 38.8, "P90 Total (s)": 42.0}
                ]),
            }

            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                generate_markdown_report(report_path, "Automated Test Suite Synthetic Data", picker_res, packer_res, None)

            self.assertTrue(os.path.isfile(report_path))
            with open(report_path, "r", encoding="utf-8") as f:
                report_text = f.read()

            # Verify mandatory sections and badges
            self.assertIn("# Stack n Stock — Pick & Pack Study Performance & Ergonomics Report", report_text)
            self.assertIn("1. Executive Summary & Protocol Compliance", report_text)
            self.assertIn("PASS (P90 &le; 5.00s)", report_text)
            self.assertIn("2. Picker Cycle-Time & Ergonomic Performance", report_text)
            self.assertIn("Slot-Level Accessibility & Ergonomic Heatmap", report_text)
            self.assertIn("3. Packer Workflow & Complexity Breakdown", report_text)
            self.assertIn("5. Engineering & Ergonomic Recommendations", report_text)


class QuietPortalRequestHandler(PortalRequestHandler):
    """Subclass of PortalRequestHandler that suppresses console noise during tests."""

    def log_message(self, format, *args):
        pass  # Suppress HTTP access logging

    def handle_save_csv(self):
        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            super().handle_save_csv()


class TestStudyPortal(unittest.TestCase):
    """Integration tests for portal/launch_portal.py HTTP server & /api/save_csv."""

    @classmethod
    def setUpClass(cls):
        """Launch test HTTP server on an available dynamic port."""
        cls.temp_dir = tempfile.mkdtemp(prefix="sns_portal_test_")
        # Direct launch_portal to save into our isolated temp_dir
        cls.original_data_dir = portal_server.DATA_RAW_DIR
        portal_server.DATA_RAW_DIR = cls.temp_dir

        cls.port = find_available_port(8950)
        cls.server = HTTPServer(("127.0.0.1", cls.port), QuietPortalRequestHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        """Shutdown HTTP server and remove temp directory."""
        cls.server.shutdown()
        cls.server.server_close()
        portal_server.DATA_RAW_DIR = cls.original_data_dir
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_api_save_csv_json_payload_persistence(self):
        """Verify POST /api/save_csv saves JSON payload with timestamp and returns 200 OK."""
        test_csv_data = "trial_id,module_type,slot_id,cycle_time_s,correct\n1,4-Slot,S1,3.95,Yes\n2,4-Slot,S2,4.12,Yes\n"
        payload = {
            "csv": test_csv_data,
            "filename": "study_export_test.csv"
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/save_csv",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["status"], "success")
            self.assertIn("filename", body)
            self.assertTrue(body["filename"].startswith("study_export_test_"))
            self.assertTrue(body["filename"].endswith(".csv"))
            self.assertEqual(body["bytes_written"], len(test_csv_data))

            # Verify actual file persistence on disk
            saved_file_path = body["filepath"]
            self.assertTrue(os.path.isfile(saved_file_path))
            with open(saved_file_path, "r", encoding="utf-8") as f:
                saved_content = f.read()
            self.assertEqual(saved_content, test_csv_data)

    def test_api_save_csv_empty_body_rejection(self):
        """Verify POST /api/save_csv rejects empty CSV body with HTTP 400 Bad Request."""
        payload = {"csv": "   ", "filename": "empty_test.csv"}
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/save_csv",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)

        self.assertEqual(ctx.exception.code, 400)
        err_body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(err_body["status"], "error")
        self.assertIn("empty", err_body["message"].lower())

    def test_api_save_csv_plain_text_fallback(self):
        """Verify POST /api/save_csv supports plain-text raw body and X-Filename header."""
        raw_csv = "operator_id,slot_id,cycle_time_s\nOP-01,S3,3.75\n"
        req = urllib.request.Request(
            f"{self.base_url}/api/save_csv",
            data=raw_csv.encode("utf-8"),
            headers={
                "Content-Type": "text/plain",
                "X-Filename": "fallback_raw.csv"
            }
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["status"], "success")
            self.assertTrue(body["filename"].startswith("fallback_raw_"))

            saved_path = body["filepath"]
            self.assertTrue(os.path.isfile(saved_path))
            with open(saved_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), raw_csv)

    def test_cors_options_preflight(self):
        """Verify OPTIONS pre-flight request returns 200 OK and appropriate CORS headers."""
        req = urllib.request.Request(f"{self.base_url}/api/save_csv", method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.headers)
            self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    def test_portal_root_get_route(self):
        """Verify GET / routes to sns_study_portal.html with 200 OK."""
        req = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8", errors="replace")
            # Verify html content contains Study Portal title/elements
            self.assertIn("Stack n Stock", content)


if __name__ == "__main__":
    unittest.main()
