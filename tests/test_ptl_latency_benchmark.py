"""
Unit tests for Stack n Stock PTL Controller Hardware Latency Benchmark
Validates signal chain stages, statistical calculations, and SLA compliance (T6 - T5 <= 120ms).
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.ptl_latency_benchmark import PTLLatencyBenchmark, SignalChainConfig, SLA_MAX_P90_LATENCY_MS


def test_signal_chain_execution_1000_cycles():
    """Verify that benchmark executes exactly 1,000 cycles with all stages populated."""
    bench = PTLLatencyBenchmark(seed=42)
    df = bench.run_benchmark(n_cycles=1000, debounce_ms=8.0)

    assert len(df) == 1000
    expected_columns = [
        "cycle_id", "sensor_isr_ms", "debounce_ms", "plc_scan_ms",
        "fieldbus_proto", "fieldbus_ms", "led_driver_ms", "transition_latency_t6_t5_ms"
    ]
    for col in expected_columns:
        assert col in df.columns

    # Verify stage summation matches total
    calculated_sum = (
        df["sensor_isr_ms"] +
        df["debounce_ms"] +
        df["plc_scan_ms"] +
        df["fieldbus_ms"] +
        df["led_driver_ms"]
    )
    np.testing.assert_allclose(df["transition_latency_t6_t5_ms"].values, calculated_sum.values, atol=0.01)


def test_sla_latency_target_compliance():
    """Verify that P90 system latency is strictly <= 120.0 ms with healthy headroom."""
    bench = PTLLatencyBenchmark(seed=42)
    bench.run_benchmark(n_cycles=1000, debounce_ms=8.0)
    stats = bench.stats

    assert stats["sla_verified"] is True
    assert stats["p90_ms"] <= SLA_MAX_P90_LATENCY_MS
    # Optimized stack should have substantial margin (> 50ms)
    assert stats["margin_to_sla_ms"] > 50.0
    # Every single cycle must remain well below the 120ms limit
    assert stats["max_ms"] < SLA_MAX_P90_LATENCY_MS


def test_debounce_filtering_optimization_delta():
    """Verify that lowering debounce from 20ms to 8ms yields a 12ms latency improvement."""
    bench_legacy = PTLLatencyBenchmark(seed=100)
    bench_legacy.run_benchmark(n_cycles=500, debounce_ms=20.0)

    bench_opt = PTLLatencyBenchmark(seed=100)
    bench_opt.run_benchmark(n_cycles=500, debounce_ms=8.0)

    delta_mean = bench_legacy.stats["mean_ms"] - bench_opt.stats["mean_ms"]
    delta_debounce = bench_legacy.stats["stage_breakdown"]["debounce_ms"]["mean_ms"] - bench_opt.stats["stage_breakdown"]["debounce_ms"]["mean_ms"]

    # Debounce reduction should be approximately 12.0 ms
    assert abs(delta_debounce - 12.0) < 0.5
    assert abs(delta_mean - 12.0) < 0.5


def test_fieldbus_bounds_and_protocols():
    """Verify that industrial fieldbus latency stays within 12.0 ms to 18.0 ms."""
    for proto in ["ethercat", "modbus_tcp", "mixed"]:
        bench = PTLLatencyBenchmark(seed=123)
        df = bench.run_benchmark(n_cycles=200, fieldbus_protocol=proto)
        fb_times = df["fieldbus_ms"].values
        assert np.all(fb_times >= 12.0)
        assert np.all(fb_times <= 18.0)


def test_jitter_metrics_calculation():
    """Verify that jitter metrics (peak-to-peak and percentile) are properly computed."""
    bench = PTLLatencyBenchmark(seed=42)
    bench.run_benchmark(n_cycles=1000)
    stats = bench.stats

    expected_p2p = round(stats["max_ms"] - stats["min_ms"], 2)
    expected_pct_jitter = round(stats["p95_ms"] - stats["median_p50_ms"], 2)

    assert abs(stats["peak_to_peak_jitter_ms"] - expected_p2p) < 0.01
    assert abs(stats["percentile_jitter_p95_p50_ms"] - expected_pct_jitter) < 0.01
