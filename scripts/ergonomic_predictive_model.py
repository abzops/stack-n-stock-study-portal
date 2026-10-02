"""
Stack n Stock — Ergonomic & Biomechanical Predictive Kinematics Model
Calculates predicted micro-motion times (Fitts' Law, Hick's Law) and fatigue decay curves.
"""

import math
from typing import Dict, Any

class ErgonomicKinematicsModel:
    def __init__(
        self,
        module_type: str = "6-Slot",
        bin_angle_deg: float = 20.0,
        working_height_mm: float = 950.0,
        confirmation_tech: str = "light_curtain" # "screen_tap", "mechanical_button", "light_curtain"
    ):
        self.module_type = module_type
        self.bin_angle_deg = bin_angle_deg
        self.working_height_mm = working_height_mm
        self.confirmation_tech = confirmation_tech

    def compute_reaction_time(self) -> float:
        """Hick-Hyman Law: RT = a + b * log2(N)"""
        n_candidates = 4 if self.module_type == "4-Slot" else 6
        a = 0.180  # Base sensory visual reaction
        b = 0.080  # Cognitive choice slope
        return a + b * math.log2(n_candidates)

    def compute_reach_acquisition_time(self, slot_id: str) -> float:
        """Fitts' Law: MT = a_m + b_m * log2(2D / W)"""
        a_m = 0.250
        b_m = 0.350

        # Aperture dimensions
        if self.module_type == "4-Slot":
            w = 280.0  # mm
            depth_map = {"S1": 560.0, "S2": 560.0, "S3": 410.0, "S4": 410.0}
        else:
            w = 185.0  # mm (narrower 6-slot mouth)
            depth_map = {
                "S1": 620.0, "S2": 620.0, "S3": 620.0,
                "S4": 420.0, "S5": 420.0, "S6": 660.0  # S6 extended lateral reach
            }

        nominal_dist = depth_map.get(slot_id, 500.0)
        
        # Tilt angle correction: higher tilt brings rear slots closer
        angle_delta = self.bin_angle_deg - 20.0
        effective_dist = nominal_dist - (angle_delta * 12.0) # ~12mm forward reach recovery per degree tilt
        effective_dist = max(350.0, effective_dist)

        id_bits = math.log2((2.0 * effective_dist) / w)
        return a_m + b_m * id_bits

    def compute_transfer_deposit_time(self) -> float:
        """Arm transfer from bin interior to order tote"""
        return 1.320

    def compute_confirmation_time(self) -> float:
        """Latency incurred to signal pick completion (T5 - T4)"""
        tech_latencies = {
            "screen_tap": 0.720,
            "mechanical_button": 0.520,
            "capacitive_bar": 0.220,
            "light_curtain": 0.085, # Automatic optical gating
        }
        return tech_latencies.get(self.confirmation_tech, 0.250)

    def compute_system_transition_delay(self) -> float:
        """PLC bus and PTL illumination latency (T6 - T5)"""
        return 0.095 # Optimized PLC interrupt cycle

    def simulate_pick_cycle(self, slot_id: str) -> Dict[str, float]:
        t_reaction = self.compute_reaction_time()
        t_reach = self.compute_reach_acquisition_time(slot_id)
        t_transfer = self.compute_transfer_deposit_time()
        t_confirm = self.compute_confirmation_time()
        t_system = self.compute_system_transition_delay()

        t_human = t_reaction + t_reach + t_transfer + t_confirm
        t_total = t_human + t_system

        return {
            "slot_id": slot_id,
            "t_reaction": round(t_reaction, 3),
            "t_reach": round(t_reach, 3),
            "t_transfer": round(t_transfer, 3),
            "t_confirm": round(t_confirm, 3),
            "t_human": round(t_human, 3),
            "t_system": round(t_system, 3),
            "t_total": round(t_total, 3)
        }

    def predict_module_distribution(self) -> Dict[str, Any]:
        slots = ["S1", "S2", "S3", "S4"] if self.module_type == "4-Slot" else ["S1", "S2", "S3", "S4", "S5", "S6"]
        slot_results = [self.simulate_pick_cycle(s) for s in slots]
        
        totals = [r["t_human"] for r in slot_results]
        totals_sorted = sorted(totals)

        median_cycle = totals_sorted[len(totals_sorted) // 2]
        # P90 approximation across slots (incorporating typical +/- 0.4s human variance)
        p90_cycle = totals_sorted[-1] + 0.350

        return {
            "module_type": self.module_type,
            "bin_angle_deg": self.bin_angle_deg,
            "confirmation_tech": self.confirmation_tech,
            "median_cycle_s": round(median_cycle, 3),
            "p90_cycle_s": round(p90_cycle, 3),
            "p90_target_s": 5.000,
            "meets_p90_sla": p90_cycle <= 5.000,
            "slot_breakdown": slot_results
        }

if __name__ == "__main__":
    print("=" * 70)
    print("STACK N STOCK — BIOMECHANICAL PREDICTIVE MODEL")
    print("=" * 70)
    
    # 1. Baseline: 6-Slot with Mechanical Button
    baseline_model = ErgonomicKinematicsModel(
        module_type="6-Slot", bin_angle_deg=20.0, confirmation_tech="mechanical_button"
    )
    res_base = baseline_model.predict_module_distribution()
    print(f"[Baseline 6-Slot + Button]       P50={res_base['median_cycle_s']:.3f}s | P90={res_base['p90_cycle_s']:.3f}s | SLA: {'PASS' if res_base['meets_p90_sla'] else 'FAIL'}")

    # 2. Optimized: 6-Slot with 22.5 deg tilt + Optical Light Curtain
    opt_model = ErgonomicKinematicsModel(
        module_type="6-Slot", bin_angle_deg=22.5, confirmation_tech="light_curtain"
    )
    res_opt = opt_model.predict_module_distribution()
    print(f"[Optimized 6-Slot + Light Curtain] P50={res_opt['median_cycle_s']:.3f}s | P90={res_opt['p90_cycle_s']:.3f}s | SLA: {'PASS' if res_opt['meets_p90_sla'] else 'FAIL'}")

    print("\n--- Optimized Slot-by-Slot Breakdown ---")
    for s in res_opt["slot_breakdown"]:
        print(f"Slot {s['slot_id']} -> Reaction: {s['t_reaction']}s | Reach: {s['t_reach']}s | Transfer: {s['t_transfer']}s | Confirm: {s['t_confirm']}s | Total: {s['t_human']}s")
