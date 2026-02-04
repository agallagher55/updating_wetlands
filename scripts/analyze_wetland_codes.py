"""
Analyze Wetland Feature Codes and Descriptions
-----------------------------------------------
This script analyzes:
1. feat_code/feat_desc values from geo_export_HRM (NSTDB source data)
2. Existing WETLAND values from NAT_wetland_feature
3. The values present in Wetlands_Updated and Wetlands_New outputs

Goal: Determine appropriate WETLAND descriptions for new wetland features.
"""

import arcpy
import os
from collections import Counter

# ============================================================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================================================

SCRATCH_GDB = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb"
SDE = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde"

# Data sources
NSTDB_SOURCE = os.path.join(SCRATCH_GDB, "geo_export_HRM")
NAT_WETLAND_FEATURE = os.path.join(SDE, "SDEADM.NAT_wetland_feature")
NAT_WETLAND_FRESHWATER = os.path.join(SDE, "SDEADM.NAT_wetland_freshwater")

# Output feature classes from net_new_wetland_update.py
WETLANDS_UPDATED = os.path.join(SCRATCH_GDB, "Wetlands_Updated")
WETLANDS_NEW = os.path.join(SCRATCH_GDB, "Wetlands_New")

# Relevant feature codes from net_new_wetland_update.py
RELEVANT_FEAT_CODES = [
    "WASW40",    # Swamp
    "WALK40",    # Lake
    "WARV40",    # River
    "WARS40",    # River/Stream
    "WACO40",    # Coastal
    "WACB40",    # Coastal/Beach
    "WACORV40",  # Coastal/River
    "WARVLK40",  # River/Lake
    "WACA40",    # Canal
    "WAFI40",    # Filled
    "WAFU40",    # Functional
    "WARA40",    # Rapid
]


def print_separator(title):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def analyze_nstdb_source():
    """Analyze all feat_code/feat_desc combinations in the NSTDB source."""
    print_separator("NSTDB SOURCE DATA (geo_export_HRM)")

    if not arcpy.Exists(NSTDB_SOURCE):
        print(f"ERROR: Source not found: {NSTDB_SOURCE}")
        return {}

    # Get all unique feat_code/feat_desc combinations
    code_desc_combos = {}
    total_count = 0
    relevant_count = 0

    fields = ["feat_code", "feat_desc"]
    with arcpy.da.SearchCursor(NSTDB_SOURCE, fields) as cursor:
        for row in cursor:
            feat_code, feat_desc = row
            total_count += 1

            if feat_code not in code_desc_combos:
                code_desc_combos[feat_code] = {"desc": feat_desc, "count": 0}
            code_desc_combos[feat_code]["count"] += 1

            if feat_code in RELEVANT_FEAT_CODES:
                relevant_count += 1

    print(f"\nTotal features in source: {total_count}")
    print(f"Features matching RELEVANT_FEAT_CODES: {relevant_count}")

    print("\n--- All feat_code/feat_desc combinations ---")
    print(f"{'feat_code':<15} {'count':>8}   {'feat_desc'}")
    print("-" * 70)

    for code in sorted(code_desc_combos.keys()):
        info = code_desc_combos[code]
        relevant_marker = " *" if code in RELEVANT_FEAT_CODES else ""
        print(f"{code:<15} {info['count']:>8}   {info['desc']}{relevant_marker}")

    print("\n* = Included in RELEVANT_FEAT_CODES")

    # Show only relevant codes
    print("\n--- RELEVANT feat_code/feat_desc (used for wetland filtering) ---")
    print(f"{'feat_code':<15} {'count':>8}   {'feat_desc'}")
    print("-" * 70)

    relevant_combos = {}
    for code in RELEVANT_FEAT_CODES:
        if code in code_desc_combos:
            info = code_desc_combos[code]
            print(f"{code:<15} {info['count']:>8}   {info['desc']}")
            relevant_combos[code] = info
        else:
            print(f"{code:<15} {'N/A':>8}   (code not found in source)")

    return relevant_combos


def analyze_nat_wetland_feature():
    """Analyze existing WETLAND values in NAT_wetland_feature."""
    print_separator("NAT_wetland_feature - Existing WETLAND Descriptions")

    if not arcpy.Exists(NAT_WETLAND_FEATURE):
        print(f"ERROR: Dataset not found: {NAT_WETLAND_FEATURE}")
        return {}

    # List all fields to understand the schema
    print("\nFields in NAT_wetland_feature:")
    fields_info = arcpy.ListFields(NAT_WETLAND_FEATURE)
    for f in fields_info:
        print(f"  - {f.name} ({f.type}, length={f.length})")

    # Get unique WETLAND values
    wetland_values = Counter()

    if any(f.name == "WETLAND" for f in fields_info):
        with arcpy.da.SearchCursor(NAT_WETLAND_FEATURE, ["WETLAND"]) as cursor:
            for row in cursor:
                wetland_values[row[0]] += 1

        print("\n--- Unique WETLAND values ---")
        print(f"{'WETLAND':<40} {'count':>8}")
        print("-" * 50)
        for value, count in sorted(wetland_values.items(), key=lambda x: (-x[1], str(x[0]))):
            print(f"{str(value):<40} {count:>8}")
    else:
        print("\nWARNING: WETLAND field not found in NAT_wetland_feature")

    return dict(wetland_values)


def analyze_nat_wetland_freshwater():
    """Analyze existing WETLAND values in NAT_wetland_freshwater (the source for matching)."""
    print_separator("NAT_wetland_freshwater - Existing WETLAND Values")

    if not arcpy.Exists(NAT_WETLAND_FRESHWATER):
        print(f"ERROR: Dataset not found: {NAT_WETLAND_FRESHWATER}")
        return {}

    # List all fields
    print("\nFields in NAT_wetland_freshwater:")
    fields_info = arcpy.ListFields(NAT_WETLAND_FRESHWATER)
    for f in fields_info:
        print(f"  - {f.name} ({f.type}, length={f.length})")

    # Get unique WETLAND values
    wetland_values = Counter()

    if any(f.name == "WETLAND" for f in fields_info):
        with arcpy.da.SearchCursor(NAT_WETLAND_FRESHWATER, ["WETLAND"]) as cursor:
            for row in cursor:
                wetland_values[row[0]] += 1

        print("\n--- Unique WETLAND values ---")
        print(f"{'WETLAND':<40} {'count':>8}")
        print("-" * 50)
        for value, count in sorted(wetland_values.items(), key=lambda x: (-x[1], str(x[0]))):
            print(f"{str(value):<40} {count:>8}")
    else:
        print("\nWARNING: WETLAND field not found in NAT_wetland_freshwater")

    return dict(wetland_values)


def analyze_wetlands_updated():
    """Analyze the Wetlands_Updated output to see feat_code distribution."""
    print_separator("Wetlands_Updated - Output Analysis")

    if not arcpy.Exists(WETLANDS_UPDATED):
        print(f"WARNING: Output not found: {WETLANDS_UPDATED}")
        print("Run net_new_wetland_update.py first to generate this output.")
        return

    # List fields
    print("\nFields in Wetlands_Updated:")
    fields_info = arcpy.ListFields(WETLANDS_UPDATED)
    for f in fields_info:
        print(f"  - {f.name} ({f.type})")

    # Analyze by Update_Status
    status_by_code = {}
    total_new = 0
    total_existing = 0

    search_fields = ["feat_code", "feat_desc", "Update_Status", "WETLAND", "IS_NEW"]

    # Check which fields exist
    available_fields = [f.name for f in fields_info]
    fields_to_use = [f for f in search_fields if f in available_fields]

    print(f"\nUsing fields: {fields_to_use}")

    with arcpy.da.SearchCursor(WETLANDS_UPDATED, fields_to_use) as cursor:
        for row in cursor:
            data = dict(zip(fields_to_use, row))
            feat_code = data.get("feat_code", "Unknown")
            feat_desc = data.get("feat_desc", "Unknown")
            status = data.get("Update_Status", "Unknown")
            wetland = data.get("WETLAND", None)
            is_new = data.get("IS_NEW", None)

            if feat_code not in status_by_code:
                status_by_code[feat_code] = {
                    "desc": feat_desc,
                    "new": 0,
                    "existing": 0,
                    "wetland_values": Counter()
                }

            if is_new == 1 or status == "New":
                status_by_code[feat_code]["new"] += 1
                total_new += 1
            else:
                status_by_code[feat_code]["existing"] += 1
                total_existing += 1

            if wetland:
                status_by_code[feat_code]["wetland_values"][wetland] += 1

    print(f"\nTotal features: {total_new + total_existing}")
    print(f"  - New (IS_NEW=1): {total_new}")
    print(f"  - Existing (matched): {total_existing}")

    print("\n--- feat_code breakdown by status ---")
    print(f"{'feat_code':<15} {'New':>8} {'Existing':>10} {'feat_desc':<30}")
    print("-" * 70)

    for code in sorted(status_by_code.keys()):
        info = status_by_code[code]
        print(f"{code:<15} {info['new']:>8} {info['existing']:>10} {info['desc']:<30}")

    # Show what WETLAND values are associated with each feat_code (for existing matches)
    print("\n--- WETLAND values assigned to each feat_code (from matched features) ---")
    for code in sorted(status_by_code.keys()):
        info = status_by_code[code]
        if info["wetland_values"]:
            print(f"\n{code} ({info['desc']}):")
            for wetland_val, count in sorted(info["wetland_values"].items(), key=lambda x: -x[1]):
                print(f"    {wetland_val}: {count}")
        elif info["new"] > 0:
            print(f"\n{code} ({info['desc']}): ** ALL NEW - NO WETLAND VALUE **")

    return status_by_code


def analyze_wetlands_new():
    """Analyze the Wetlands_New output (only new features)."""
    print_separator("Wetlands_New - New Features Only")

    if not arcpy.Exists(WETLANDS_NEW):
        print(f"WARNING: Output not found: {WETLANDS_NEW}")
        print("Run net_new_wetland_update.py first to generate this output.")
        return

    # Count by feat_code
    code_counts = Counter()
    code_descs = {}

    with arcpy.da.SearchCursor(WETLANDS_NEW, ["feat_code", "feat_desc"]) as cursor:
        for row in cursor:
            code_counts[row[0]] += 1
            code_descs[row[0]] = row[1]

    print(f"\nTotal new wetland features: {sum(code_counts.values())}")
    print("\n--- New features by feat_code ---")
    print(f"{'feat_code':<15} {'count':>8}   {'feat_desc'}")
    print("-" * 70)

    for code, count in sorted(code_counts.items(), key=lambda x: -x[1]):
        desc = code_descs.get(code, "Unknown")
        print(f"{code:<15} {count:>8}   {desc}")

    return dict(code_counts)


def suggest_wetland_mappings(nstdb_codes, existing_wetlands):
    """Suggest WETLAND description mappings based on analysis."""
    print_separator("SUGGESTED WETLAND MAPPINGS")

    print("""
Based on the analysis, here are suggested mappings from NSTDB feat_code to WETLAND descriptions.

These should be reviewed and adjusted based on:
1. The actual wetland type definitions in your data standards
2. How existing wetlands were classified
3. Business rules for wetland categorization

IMPORTANT: The feat_desc from NSTDB describes what the feature IS (e.g., "Swamp"),
which may or may not align directly with the WETLAND descriptions used in NAT_wetland_feature.
""")

    # Common wetland type mappings based on NSTDB codes
    suggested_mappings = {
        "WASW40": "Swamp",           # Swamp - most direct mapping
        "WALK40": None,              # Lake - may not be a wetland type
        "WARV40": None,              # River - may not be a wetland type
        "WARS40": None,              # River/Stream - may not be a wetland type
        "WACO40": "Coastal Wetland", # Coastal
        "WACB40": "Coastal Wetland", # Coastal/Beach
        "WACORV40": "Coastal Wetland", # Coastal/River
        "WARVLK40": None,            # River/Lake - may not be a wetland type
        "WACA40": None,              # Canal - man-made, may not be wetland
        "WAFI40": None,              # Filled - unclear
        "WAFU40": None,              # Functional - unclear
        "WARA40": None,              # Rapid - may not be wetland type
    }

    print("\n--- Suggested Mappings (REVIEW REQUIRED) ---")
    print(f"{'feat_code':<15} {'feat_desc':<25} {'Suggested WETLAND':<25}")
    print("-" * 70)

    for code in RELEVANT_FEAT_CODES:
        if code in nstdb_codes:
            desc = nstdb_codes[code].get("desc", "Unknown")
        else:
            desc = "Not in source"

        suggested = suggested_mappings.get(code, "NEEDS REVIEW")
        if suggested is None:
            suggested = "** EXCLUDE? **"

        print(f"{code:<15} {desc:<25} {suggested:<25}")

    print("""
NEXT STEPS:
1. Review the existing WETLAND values in NAT_wetland_feature
2. Determine which feat_codes should actually be included as wetlands
3. Define the WETLAND description for each included feat_code
4. Update net_new_wetland_update.py to populate WETLAND based on feat_code
""")


def main():
    print("=" * 70)
    print(" WETLAND FEATURE CODE ANALYSIS")
    print(" Analyzing feat_code/feat_desc for WETLAND field population")
    print("=" * 70)

    # Run all analyses
    nstdb_codes = analyze_nstdb_source()
    nat_feature_wetlands = analyze_nat_wetland_feature()
    nat_freshwater_wetlands = analyze_nat_wetland_freshwater()
    updated_analysis = analyze_wetlands_updated()
    new_analysis = analyze_wetlands_new()

    # Combine existing wetland values for reference
    all_existing_wetlands = set(nat_feature_wetlands.keys()) | set(nat_freshwater_wetlands.keys())

    # Provide suggestions
    suggest_wetland_mappings(nstdb_codes, all_existing_wetlands)

    print("\n" + "=" * 70)
    print(" ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
