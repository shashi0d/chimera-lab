"""Explicit rule_id -> check map for the real chimera_data.json (D1-02).

The real rules carry no machine-readable check, so every executable rule is
listed here by hand, with the check that runs it and the severity of a hit.
Rules not listed are data-integrity or mythology-record rules (how the data
file itself must be written); they do not apply to a fusion and are reported
as "unmapped" in the rules_check step, never silently dropped.

Checks live in app/pipeline/steps/rules_check.py. "pair" checks run in the
rules_check step on the two parents; "plan" checks run after the compile step,
on the fusion the planner chose (body plan + part donors).
"""

from __future__ import annotations

# rule_id: (check name, severity of a hit)
RULE_CHECKS: dict[str, tuple[str, str]] = {
    # --- A1 anatomy and body plans
    "R-A1-01": ("plan_body_plan_allowed", "warning"),
    "R-A1-02": ("covering_from_donor", "warning"),
    "R-A1-03": ("covering_conflict", "info"),
    "R-A1-04": ("winged_needs_winged_parent", "warning"),
    "R-A1-05": ("finned_needs_finned_parent", "warning"),
    "R-A1-06": ("serpentine_needs_serpentine_parent", "warning"),
    "R-A1-07": ("shell_needs_shelled_parent", "warning"),
    "R-A1-P01": ("serpentine_with_quadruped", "warning"),
    "R-A1-P03": ("shell_with_fur", "info"),
    # --- A2 scaling
    "R-A2-03": ("mass_ratio_1000", "warning"),
    # --- A3 real hybrids
    "R-A3-07": ("real_hybrid_direction", "info"),
    "R-A3-P01": ("parents_same_species", "info"),
    # --- A4 locomotion and activity
    "R-A4-01": ("movement_has_donor", "warning"),
    "R-A4-02": ("fly_needs_flying_parent", "warning"),
    "R-A4-03": ("swim_needs_swimming_parent", "warning"),
    "R-A4-07": ("fly_and_swim_parents", "info"),
    "R-A4-08": ("walk_needs_walking_parent", "warning"),
    "R-A4-18": ("walk_and_swim_parents", "info"),
    "R-A4-19": ("climb_needs_climbing_parent", "warning"),
    "R-A4-20": ("burrow_needs_burrowing_parent", "warning"),
    "R-A4-21": ("glide_needs_gliding_parent", "warning"),
    "R-A4-22": ("movement_has_donor", "warning"),
    "R-A4-P03": ("active_time_conflict", "info"),
    "R-A4-P04": ("active_time_unrecorded", "info"),
    # --- A5 habitat and climate
    "R-A5-01": ("habitat_overlap", "warning"),
    "R-A5-02": ("climate_overlap", "warning"),
    "R-A5-03": ("realm_conflict", "warning"),
    "R-A5-04": ("polar_needs_polar_parent", "warning"),
    "R-A5-05": ("salinity_conflict", "info"),
    "R-A5-06": ("desert_needs_desert_parent", "warning"),
    "R-A5-08": ("tundra_with_tropical", "info"),
    "R-A5-10": ("wetland_parent", "info"),
    "R-A5-23": ("salinity_conflict", "info"),
    "R-A5-25": ("wetland_parent", "info"),
    "R-A5-P08": ("broad_climate_parent", "info"),
    # --- A6 diet and metabolism
    "R-A6-01": ("diet_from_donor", "warning"),
    "R-A6-02": ("diet_conflict", "info"),
    "R-A6-08": ("carnivore_needs_carnivore_parent", "warning"),
    "R-A6-15": ("metabolic_rate_implausible", "info"),
    "R-A6-P01": ("carnivore_piscivore_parent", "info"),
    # --- A8 fusion viability
    "R-A8-02": ("body_plan_mismatch", "warning"),
    "R-A8-03": ("habitat_overlap", "warning"),
    "R-A8-04": ("mass_ratio_1000", "warning"),
    "R-A8-06": ("blank_parent_traits", "info"),
}
