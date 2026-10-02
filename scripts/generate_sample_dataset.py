#!/usr/bin/env python3
"""
Stack n Stock — Sample Dataset Generator
Generates representative, statistically calibrated sample CSV datasets for both
Picker (100 trials) and Packer (60 trials) and writes them to data/raw/.
"""

import os
import sys
import random
import argparse
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")


def generate_picker_dataset(n_trials=100, seed=42):
    """
    Generates representative Picker trials:
    - Calibrated to target P90 <= 5.00s compliance (~90% <= 5.0s, mean ~4.1s).
    - Balanced across 4-Slot (50 trials) and 6-Slot (50 trials) modules.
    - Slot-level ergonomic variation (ergonomically optimal slots vs reach penalty slots).
    - Realistic accuracy (~97-98%) and system latency.
    """
    random.seed(seed)
    records = []
    base_time = datetime(2026, 9, 24, 9, 0, 0)

    operators = ["OP-01", "OP-02", "OP-03"]
    skus = ["SKU-A", "SKU-B", "SKU-C", "SKU-D", "SKU-E", "SKU-F"]
    delay_reasons = ["D01: Barcode Read Delay", "D02: Label Defect", "E01: Dropped Item", "P01: Re-scan Item"]

    # Slot ergonomic difficulty biases (added to base cycle time)
    slot_biases = {
        "4-Slot": {"S1": 0.15, "S2": -0.25, "S3": -0.10, "S4": 0.20},
        "6-Slot": {"S1": 0.25, "S2": -0.30, "S3": 0.10, "S4": 0.15, "S5": -0.20, "S6": 0.35}
    }

    trial_counter = 1
    # 50 trials for 4-Slot, 50 trials for 6-Slot
    module_allocation = [("4-Slot", 50), ("6-Slot", 50)]

    curr_time = base_time
    for mod_type, count in module_allocation:
        slots = list(slot_biases[mod_type].keys())
        session_id = "SESS-01" if mod_type == "4-Slot" else "SESS-02"

        for i in range(count):
            op = random.choice(operators)
            slot = slots[i % len(slots)] # balanced slot rotation
            sku = random.choice(skus)
            qty = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]

            # Base normal distribution around 4.05s, std 0.55s + slot bias
            raw_time = random.gauss(4.05, 0.52) + slot_biases[mod_type][slot]
            # Occasional mild hesitation (5% of picks)
            if random.random() < 0.05:
                raw_time += random.uniform(0.6, 1.4)
            cycle_time = max(2.85, round(raw_time, 3))

            # 98% accuracy
            is_correct = random.random() >= 0.02
            correct_str = "Yes" if is_correct else "No"

            delay_code = ""
            if not is_correct:
                delay_code = random.choice(["E01: Mis-pick SKU", "E02: Quantity Mismatch"])
            elif cycle_time > 5.2 and random.random() < 0.4:
                delay_code = random.choice(delay_reasons)

            system_latency = round(random.uniform(0.12, 0.21), 3)
            notes = f"CAM_{trial_counter:04d}"

            records.append({
                "trial_id": trial_counter,
                "session_id": session_id,
                "operator_id": op,
                "role": "picker",
                "module_type": mod_type,
                "slot_id": slot,
                "sku_qty": f"{sku} / {qty}",
                "cycle_time_s": cycle_time,
                "correct": correct_str,
                "delay_code": delay_code,
                "system_latency_s": system_latency,
                "notes": notes,
                "timestamp": curr_time.isoformat()
            })

            curr_time += timedelta(seconds=cycle_time + random.uniform(2.5, 4.0))
            trial_counter += 1

    return records


def generate_packer_dataset(n_trials=60, seed=101):
    """
    Generates representative Packer trials:
    - 60 total trials distributed across complexity bands C1 (40%), C2 (40%), C3 (20%).
    - Accurate P2-P0 retrieval times (2.5 - 5.5s) and P7-P2 packaging work times.
    - Realistic rework rates and packaging delay tags.
    """
    random.seed(seed)
    records = []
    base_time = datetime(2026, 9, 24, 13, 30, 0)

    operators = ["OP-01", "OP-02", "OP-03"]
    bands_distribution = (
        [("C1", "1-2 items / Mailer bag", 2)] * 24 +
        [("C2", "3-5 items / Standard box", 4)] * 24 +
        [("C3", "6+ items / Fragile dunnage", 7)] * 12
    )
    random.shuffle(bands_distribution)

    curr_time = base_time
    trial_counter = 1

    for band, desc, typical_items in bands_distribution:
        op = random.choice(operators)
        mod_type = random.choice(["4-Slot", "6-Slot"])
        max_slot = 4 if mod_type == "4-Slot" else 6
        slot = f"S{random.randint(1, max_slot)}"

        # Retrieval P2-P0
        retrieval = round(max(2.2, random.gauss(3.6, 0.45)), 2)

        # Work P7-P2 based on complexity band
        if band == "C1":
            work = round(max(9.5, random.gauss(15.5, 2.2)), 2)
            items = random.choice([1, 2])
        elif band == "C2":
            work = round(max(20.0, random.gauss(29.8, 3.8)), 2)
            items = random.randint(3, 5)
        else: # C3
            work = round(max(42.0, random.gauss(58.5, 7.5)), 2)
            items = random.randint(6, 9)

        total_cycle = round(retrieval + work, 2)

        # Accuracy & Rework
        is_correct = random.random() >= 0.02
        is_rework = random.random() < 0.05
        correct_str = "Yes" if is_correct else "No"
        rework_str = "Yes" if is_rework else "No"

        delay_code = ""
        if is_rework:
            delay_code = "K03: Package Reseal / Rework"
        elif not is_correct:
            delay_code = "K02: Verification Issue / Missing SKU"
        elif random.random() < 0.08:
            delay_code = random.choice(["K01: Material Wait", "S02: Printer Delay"])

        notes = f"Band {band} - {desc}"
        if delay_code:
            notes += f" ({delay_code})"

        records.append({
            "trial_id": trial_counter,
            "session_id": "PACK-SESS-01",
            "operator_id": op,
            "role": "packer",
            "module_type": mod_type,
            "slot_id": slot,
            "complexity_band": band,
            "items_count": items,
            "retrieval_time_s": retrieval,
            "work_time_s": work,
            "total_cycle_time_s": total_cycle,
            "correct": correct_str,
            "rework": rework_str,
            "delay_code": delay_code,
            "notes": notes,
            "timestamp": curr_time.isoformat()
        })

        curr_time += timedelta(seconds=total_cycle + random.uniform(5.0, 10.0))
        trial_counter += 1

    return records


def write_csv(filepath, records, fieldnames):
    """Write list of dict records to CSV."""
    import csv
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f" -> Created CSV: {filepath} ({len(records)} rows, {os.path.getsize(filepath)} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Generate sample Pick & Pack study datasets")
    parser.add_argument("--picker-trials", type=int, default=100, help="Number of picker trials (default: 100)")
    parser.add_argument("--packer-trials", type=int, default=60, help="Number of packer trials (default: 60)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--timestamp", action="store_true", help="Add timestamp to generated filenames")
    args = parser.parse_args()

    os.makedirs(DATA_RAW_DIR, exist_ok=True)

    time_tag = f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}" if args.timestamp else ""

    picker_file = os.path.join(DATA_RAW_DIR, f"picker_trials_sample_100{time_tag}.csv")
    packer_file = os.path.join(DATA_RAW_DIR, f"packer_trials_sample_60{time_tag}.csv")

    print("=" * 70)
    print("   STACK N STOCK — SAMPLE STUDY DATASET GENERATOR")
    print("=" * 70)
    print(f"Target Directory : {DATA_RAW_DIR}")
    print(f"Picker Trials    : {args.picker_trials}")
    print(f"Packer Trials    : {args.packer_trials}")
    print(f"Random Seed      : {args.seed}")
    print("-" * 70)

    # 1. Picker Dataset
    picker_data = generate_picker_dataset(n_trials=args.picker_trials, seed=args.seed)
    picker_fields = [
        "trial_id", "session_id", "operator_id", "role", "module_type", "slot_id",
        "sku_qty", "cycle_time_s", "correct", "delay_code", "system_latency_s",
        "notes", "timestamp"
    ]
    write_csv(picker_file, picker_data, picker_fields)

    # 2. Packer Dataset
    packer_data = generate_packer_dataset(n_trials=args.packer_trials, seed=args.seed + 59)
    packer_fields = [
        "trial_id", "session_id", "operator_id", "role", "module_type", "slot_id",
        "complexity_band", "items_count", "retrieval_time_s", "work_time_s",
        "total_cycle_time_s", "correct", "rework", "delay_code", "notes", "timestamp"
    ]
    write_csv(packer_file, packer_data, packer_fields)

    print("=" * 70)
    print("Sample datasets generated successfully in data/raw/!")
    print("=" * 70)


if __name__ == "__main__":
    main()
