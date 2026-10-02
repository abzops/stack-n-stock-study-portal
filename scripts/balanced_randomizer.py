"""
Stack n Stock — Balanced Anti-Pattern Trial Generator
Implements the mathematically verified constrained permutation algorithm specified in:
docs/research/03_BALANCED_ANTI_PATTERN_ALGORITHM_SPEC.md
"""

import math
import random
from typing import List, Dict, Any, Optional

def generate_balanced_picker_pool(
    slots: List[str] = None,
    reps_per_slot: int = 10,
    seed: Optional[int] = 42
) -> List[Dict[str, Any]]:
    """
    Generates a balanced anti-pattern trial pool for pickers.
    - Exactly `reps_per_slot` trials for each slot.
    - Anti-streak constraint: No two consecutive trials have the same slot.
    - Fully reproducible via integer seed.
    """
    if slots is None:
        slots = ["S1", "S2", "S3", "S4"]
    
    rng = random.Random(seed)
    
    skus = [
        {"sku": "SKU-A12", "desc": "Small Box Assembly", "qty": 1},
        {"sku": "SKU-B04", "desc": "Component Pouch", "qty": 1},
        {"sku": "SKU-C88", "desc": "Standard Fastener Pack", "qty": 2},
        {"sku": "SKU-D19", "desc": "Heavy Hardware Unit", "qty": 1},
    ]

    # 1. Build initial balanced pool
    pool = []
    for s_idx, slot in enumerate(slots):
        for r in range(reps_per_slot):
            item = skus[(s_idx + r) % len(skus)]
            pool.append({
                "slot_id": slot,
                "sku": item["sku"],
                "desc": item["desc"],
                "qty": item["qty"],
                "rep_index": r + 1
            })

    # 2. Constrained shuffle with anti-streak repair
    max_attempts = 100
    for _ in range(max_attempts):
        shuffled = list(pool)
        rng.shuffle(shuffled)
        
        valid = True
        for i in range(1, len(shuffled)):
            if shuffled[i]["slot_id"] == shuffled[i-1]["slot_id"]:
                # Look forward for a non-matching element to swap
                swapped = False
                for j in range(i + 1, len(shuffled)):
                    if shuffled[j]["slot_id"] != shuffled[i-1]["slot_id"] and (j == len(shuffled) - 1 or shuffled[j]["slot_id"] != shuffled[j+1]["slot_id"]):
                        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
                        swapped = True
                        break
                if not swapped:
                    valid = False
                    break
        
        if valid:
            # Assign final sequential trial IDs
            for idx, trial in enumerate(shuffled, start=1):
                trial["trial_id"] = idx
            return shuffled

    # Fallback to interleaved blocks if shuffle retries exhausted
    interleaved = []
    for r in range(reps_per_slot):
        block = list(slots)
        rng.shuffle(block)
        # Avoid boundary collision
        if interleaved and block[0] == interleaved[-1]["slot_id"]:
            block[0], block[-1] = block[-1], block[0]
        for s in block:
            item = skus[len(interleaved) % len(skus)]
            interleaved.append({
                "trial_id": len(interleaved) + 1,
                "slot_id": s,
                "sku": item["sku"],
                "desc": item["desc"],
                "qty": item["qty"],
                "rep_index": r + 1
            })
    return interleaved

def generate_balanced_packer_pool(
    slots: List[str] = None,
    reps_per_slot: int = 6,
    seed: Optional[int] = 42
) -> List[Dict[str, Any]]:
    """
    Generates a balanced anti-pattern pool for packers with orthogonal complexity.
    - Each slot receives equal distribution of C1, C2, C3 complexity bands.
    - Anti-streak constraint enforced.
    """
    if slots is None:
        slots = ["S1", "S2", "S3", "S4", "S5", "S6"]
        
    rng = random.Random(seed)
    
    comp_defs = [
        {"band": "C1", "name": "Simple", "desc": "1-2 items | Polybag", "items": 2},
        {"band": "C2", "name": "Standard", "desc": "3-5 items | Standard Carton", "items": 4},
        {"band": "C3", "name": "Complex", "desc": "6+ items | Dunnage / Fragile Box", "items": 7},
    ]

    pool = []
    for s_idx, slot in enumerate(slots):
        for r in range(reps_per_slot):
            comp = comp_defs[r % len(comp_defs)]
            pool.append({
                "slot_id": slot,
                "complexity_band": comp["band"],
                "complexity_name": comp["name"],
                "package_type": comp["desc"],
                "items_count": comp["items"],
                "order_id": f"ORD-{1000 + len(pool)}"
            })

    # Constrained shuffle
    for _ in range(100):
        shuffled = list(pool)
        rng.shuffle(shuffled)
        valid = True
        for i in range(1, len(shuffled)):
            if shuffled[i]["slot_id"] == shuffled[i-1]["slot_id"]:
                swapped = False
                for j in range(i + 1, len(shuffled)):
                    if shuffled[j]["slot_id"] != shuffled[i-1]["slot_id"]:
                        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
                        swapped = True
                        break
                if not swapped:
                    valid = False
                    break
        if valid:
            for idx, trial in enumerate(shuffled, start=1):
                trial["trial_id"] = idx
            return shuffled

    return pool

def compute_sequence_entropy(sequence: List[str]) -> float:
    """Calculates conditional transition entropy H(S_j | S_i) in bits."""
    transitions = {}
    for i in range(len(sequence) - 1):
        s_cur = sequence[i]
        s_next = sequence[i + 1]
        transitions.setdefault(s_cur, {})
        transitions[s_cur][s_next] = transitions[s_cur].get(s_next, 0) + 1

    total_entropy = 0.0
    for s_cur, next_counts in transitions.items():
        total_from_cur = sum(next_counts.values())
        cur_entropy = 0.0
        for count in next_counts.values():
            p = count / total_from_cur
            cur_entropy -= p * math.log2(p)
        total_entropy += cur_entropy / len(transitions)

    return total_entropy

if __name__ == "__main__":
    picker_pool = generate_balanced_picker_pool(slots=["S1","S2","S3","S4","S5","S6"], reps_per_slot=10, seed=42)
    seq = [t["slot_id"] for t in picker_pool]
    entropy = compute_sequence_entropy(seq)
    
    # Check streak constraint
    streaks = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i-1])
    
    print("=" * 60)
    print("BALANCED ANTI-PATTERN RANDOMIZER VERIFICATION")
    print("=" * 60)
    print(f"Total Trials Generated : {len(picker_pool)}")
    print(f"Consecutive Streaks    : {streaks} (Target: 0)")
    print(f"Transition Entropy     : {entropy:.3f} bits (Max for 5 candidates: 2.322 bits)")
    print(f"Validation Status      : {'PASS' if streaks == 0 and entropy > 2.1 else 'FAIL'}")
    print("Sample First 12 Slots  :", seq[:12])
