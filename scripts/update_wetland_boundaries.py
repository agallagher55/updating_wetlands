"""
Update Wetland Boundaries Script for ArcGIS Pro
------------------------------------------------
This script updates wetland polygon boundaries from new NSTDB data while 
preserving existing Canadian Wetland Classification System classes.

Also generates a LOOKUP TABLE showing which NSTDB feat_codes map to which
WETLAND classifications based on spatial overlap with existing data.

Author: Generated for HRM Wetland Update
Date: January 2026
"""

import arcpy
import os
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================================================

SCRATCH_GDB = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb"
SDE = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde"

# Input datasets
EXISTING_WETLANDS = os.path.join(SDE, "SDEADM.NAT_wetland_freshwater")  # Your current wetland data
NSTDB_WATER_FEATURES = os.path.join(SCRATCH_GDB, "geo_export_HRM")  # Downloaded NSTDB

# Output location
OUTPUT_NAME = "Wetlands_Updated"  # Name for final output feature class
LOOKUP_TABLE_NAME = "Wetland_NSTDB_Lookup"  # Lookup table for feat_code to WETLAND mapping

# Field names (adjust if your data uses different names)
EXISTING_CLASS_FIELD = "WETLAND"  # Field containing wetland classification in your data
NSTDB_CODE_FIELD = "feat_code"  # Feature code field in NSTDB
NSTDB_DESC_FIELD = "feat_desc"  # Feature description field in NSTDB

# NSTDB feature codes to include (add or remove as needed)
RELEVANT_FEAT_CODES = [
    'WASW40',    # Swamp Area polygon
    'WALK40',    # Lake Water polygon
    'WARV40',    # River Water Area polygon
    'WARS40',    # Reservoir Water polygon
    'WACO40',    # Coast Water Area polygon
    'WACB40',    # Cranberry Bog polygon
    'WACORV40',  # Coast River Water polygon
    'WARVLK40',  # River Lake Water polygon
    'WACA40',    # Canal Water polygon
    'WAFI40',    # Fish Ladder Water polygon
    'WAFU40',    # Flume Water polygon
    'WARA40',    # Rapids polygon
]

# Default classification mapping for new polygons (FEAT_CODE -> Wetland_Class)
# This will be updated/validated based on the lookup table generated
DEFAULT_CLASS_MAPPING = {
    'WASW40': 'Swamp',
    'WACB40': 'Bog or Fen',
    'WALK40': 'Water',
    'WARV40': 'Water',
    'WARS40': 'Water',
    'WACO40': 'Water',
    'WACORV40': 'Water',
    'WARVLK40': 'Water',
    'WACA40': 'Water',
    'WAFI40': 'Water',
    'WAFU40': 'Water',
    'WARA40': 'Water',
}

# ============================================================================
# SCRIPT - DO NOT MODIFY BELOW UNLESS NECESSARY
# ============================================================================

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def check_inputs():
    """Verify input datasets exist and have required fields."""
    log("Checking input datasets...")

    if not arcpy.Exists(EXISTING_WETLANDS):
        raise FileNotFoundError(f"Existing wetlands not found: {EXISTING_WETLANDS}")

    if not arcpy.Exists(NSTDB_WATER_FEATURES):
        raise FileNotFoundError(f"NSTDB data not found: {NSTDB_WATER_FEATURES}")

    # Check for required fields
    existing_fields = [f.name for f in arcpy.ListFields(EXISTING_WETLANDS)]
    if EXISTING_CLASS_FIELD not in existing_fields:
        raise ValueError(f"Field '{EXISTING_CLASS_FIELD}' not found in existing wetlands. "
                        f"Available fields: {existing_fields}")

    nstdb_fields = [f.name for f in arcpy.ListFields(NSTDB_WATER_FEATURES)]
    if NSTDB_CODE_FIELD not in nstdb_fields:
        raise ValueError(f"Field '{NSTDB_CODE_FIELD}' not found in NSTDB data. "
                        f"Available fields: {nstdb_fields}")

    log("Input validation passed.")


def filter_nstdb():
    """Filter NSTDB to only relevant wetland/water feature codes."""
    log("Filtering NSTDB to relevant feature codes...")

    # Build SQL where clause
    codes_str = "', '".join(RELEVANT_FEAT_CODES)
    where_clause = f"{NSTDB_CODE_FIELD} IN ('{codes_str}')"

    output_filtered = os.path.join(SCRATCH_GDB, "NSTDB_Filtered")

    if arcpy.Exists(output_filtered):
        arcpy.Delete_management(output_filtered)

    arcpy.Select_analysis(
        in_features=NSTDB_WATER_FEATURES,
        out_feature_class=output_filtered,
        where_clause=where_clause
    )

    count = int(arcpy.GetCount_management(output_filtered)[0])
    log(f"Filtered to {count} features.")

    return output_filtered


def check_coordinate_systems(nstdb_filtered):
    """Check and project if coordinate systems don't match."""
    log("Checking coordinate systems...")

    existing_sr = arcpy.Describe(EXISTING_WETLANDS).spatialReference
    nstdb_sr = arcpy.Describe(nstdb_filtered).spatialReference

    if existing_sr.factoryCode != nstdb_sr.factoryCode:
        log(f"Projecting NSTDB from {nstdb_sr.name} to {existing_sr.name}...")

        output_projected = os.path.join(SCRATCH_GDB, "NSTDB_Projected")

        if arcpy.Exists(output_projected):
            arcpy.Delete_management(output_projected)

        arcpy.Project_management(
            in_dataset=nstdb_filtered,
            out_dataset=output_projected,
            out_coor_system=existing_sr
        )
        return output_projected
    else:
        log("Coordinate systems match.")
        return nstdb_filtered


def spatial_join_classifications(nstdb_layer):
    """Transfer existing wetland classifications to new NSTDB geometry."""
    log("Performing spatial join to transfer classifications...")

    output_joined = os.path.join(SCRATCH_GDB, "Wetlands_Joined")

    if arcpy.Exists(output_joined):
        arcpy.Delete_management(output_joined)

    # Spatial join: new geometry gets classification from largest overlapping old polygon
    arcpy.SpatialJoin_analysis(
        target_features=nstdb_layer,
        join_features=EXISTING_WETLANDS,
        out_feature_class=output_joined,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="LARGEST_OVERLAP"
    )

    count = int(arcpy.GetCount_management(output_joined)[0])
    log(f"Spatial join complete. {count} features in output.")

    return output_joined


def generate_lookup_table(joined_layer):
    """
    Generate a lookup table showing the relationship between
    NSTDB feat_code/feat_desc and existing WETLAND classifications.
    """
    log("Generating lookup table from spatial join results...")

    # Dictionary to store: feat_code -> {feat_desc, wetland_counts}
    lookup_data = defaultdict(lambda: {
        'feat_desc': None,
        'wetland_counts': defaultdict(int),
        'total_count': 0
    })

    # Read the joined data
    fields = [NSTDB_CODE_FIELD, NSTDB_DESC_FIELD, EXISTING_CLASS_FIELD]

    with arcpy.da.SearchCursor(joined_layer, fields) as cursor:
        for row in cursor:
            feat_code = row[0]
            feat_desc = row[1]
            wetland_class = row[2] if row[2] else "No Match"

            lookup_data[feat_code]['feat_desc'] = feat_desc
            lookup_data[feat_code]['wetland_counts'][wetland_class] += 1
            lookup_data[feat_code]['total_count'] += 1

    # Create lookup table
    lookup_table = os.path.join(SCRATCH_GDB, LOOKUP_TABLE_NAME)

    if arcpy.Exists(lookup_table):
        arcpy.Delete_management(lookup_table)

    arcpy.CreateTable_management(SCRATCH_GDB, LOOKUP_TABLE_NAME)

    # Add fields
    arcpy.AddField_management(lookup_table, "feat_code", "TEXT", field_length=20)
    arcpy.AddField_management(lookup_table, "feat_desc", "TEXT", field_length=100)
    arcpy.AddField_management(lookup_table, "WETLAND_Primary", "TEXT", field_length=50)
    arcpy.AddField_management(lookup_table, "WETLAND_Match_Pct", "DOUBLE")
    arcpy.AddField_management(lookup_table, "Total_Count", "LONG")
    arcpy.AddField_management(lookup_table, "Matched_Count", "LONG")
    arcpy.AddField_management(lookup_table, "New_Count", "LONG")
    arcpy.AddField_management(lookup_table, "All_WETLAND_Values", "TEXT", field_length=255)

    # Insert rows
    insert_fields = [
        "feat_code", "feat_desc", "WETLAND_Primary", "WETLAND_Match_Pct",
        "Total_Count", "Matched_Count", "New_Count", "All_WETLAND_Values"
    ]

    with arcpy.da.InsertCursor(lookup_table, insert_fields) as cursor:
        for feat_code, data in sorted(lookup_data.items()):
            feat_desc = data['feat_desc']
            wetland_counts = data['wetland_counts']
            total = data['total_count']

            # Find primary (most common) wetland class (excluding "No Match")
            matched_counts = {k: v for k, v in wetland_counts.items() if k != "No Match"}

            if matched_counts:
                primary_wetland = max(matched_counts, key=matched_counts.get)
                primary_count = matched_counts[primary_wetland]
                match_pct = (primary_count / total) * 100
            else:
                primary_wetland = "No Match"
                match_pct = 0

            matched_total = sum(matched_counts.values())
            new_count = wetland_counts.get("No Match", 0)

            # Build string of all wetland values with counts
            all_values = "; ".join([f"{k}: {v}" for k, v in sorted(wetland_counts.items())])

            cursor.insertRow([
                feat_code,
                feat_desc,
                primary_wetland,
                round(match_pct, 1),
                total,
                matched_total,
                new_count,
                all_values
            ])

    log(f"Lookup table created: {lookup_table}")

    # Print summary
    log("\n" + "=" * 80)
    log("LOOKUP TABLE SUMMARY")
    log("=" * 80)
    log(f"{'FEAT_CODE':<12} {'FEAT_DESC':<30} {'PRIMARY WETLAND':<15} {'MATCH %':<10} {'TOTAL':<8}")
    log("-" * 80)

    for feat_code, data in sorted(lookup_data.items()):
        feat_desc = data['feat_desc'][:28] if data['feat_desc'] else "N/A"
        wetland_counts = data['wetland_counts']
        total = data['total_count']

        matched_counts = {k: v for k, v in wetland_counts.items() if k != "No Match"}
        if matched_counts:
            primary_wetland = max(matched_counts, key=matched_counts.get)
            match_pct = (matched_counts[primary_wetland] / total) * 100
        else:
            primary_wetland = "No Match"
            match_pct = 0

        log(f"{feat_code:<12} {feat_desc:<30} {primary_wetland:<15} {match_pct:>6.1f}%    {total:<8}")

    log("=" * 80 + "\n")

    return lookup_table, lookup_data


def add_update_fields(joined_layer):
    """Add fields for tracking update status and QA."""
    log("Adding update tracking fields...")

    existing_fields = [f.name for f in arcpy.ListFields(joined_layer)]

    if "Update_Status" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Update_Status", "TEXT", field_length=20)

    if "Update_Date" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Update_Date", "DATE")

    if "Original_Code" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Original_Code", "TEXT", field_length=20)

    log("Fields added.")


def calculate_fields_and_assign_classes(joined_layer, lookup_data):
    """
    Calculate update status and assign WETLAND classes to all features.
    Uses the lookup_data to determine the best WETLAND class for each feat_code.
    """
    log("Calculating fields and assigning WETLAND classes...")

    # Build a mapping from feat_code to primary wetland class based on lookup
    feat_to_wetland = {}
    for feat_code, data in lookup_data.items():
        wetland_counts = data['wetland_counts']
        matched_counts = {k: v for k, v in wetland_counts.items() if k != "No Match"}

        if matched_counts:
            # Use the most common wetland class from existing data
            feat_to_wetland[feat_code] = max(matched_counts, key=matched_counts.get)
        else:
            # Fall back to default mapping
            feat_to_wetland[feat_code] = DEFAULT_CLASS_MAPPING.get(feat_code, "Needs Review")

    # Update records using UpdateCursor
    fields = [
        NSTDB_CODE_FIELD,       # 0
        EXISTING_CLASS_FIELD,   # 1 - WETLAND
        "Update_Status",        # 2
        "Update_Date",          # 3
        "Original_Code"         # 4
    ]

    now = datetime.now()
    existing_count = 0
    new_count = 0

    with arcpy.da.UpdateCursor(joined_layer, fields) as cursor:
        for row in cursor:
            feat_code = row[0]
            current_wetland = row[1]

            # Copy feat_code to Original_Code
            row[4] = feat_code

            # Set update date
            row[3] = now

            # Determine status and assign WETLAND class
            if current_wetland and str(current_wetland).strip() and str(current_wetland) != 'None':
                # Existing - has a match from spatial join
                row[2] = "Existing"
                existing_count += 1
                # Keep the existing wetland class (already populated from spatial join)
            else:
                # New - no match from spatial join
                row[2] = "New"
                new_count += 1
                # Assign WETLAND class based on lookup or default
                row[1] = feat_to_wetland.get(feat_code, DEFAULT_CLASS_MAPPING.get(feat_code, "Needs Review"))

            cursor.updateRow(row)

    log(f"Status calculated: {existing_count} existing, {new_count} new polygons.")


def generate_summary(joined_layer):
    """Generate summary statistics of the update."""
    log("\n" + "=" * 60)
    log("FINAL OUTPUT SUMMARY")
    log("=" * 60)

    # Count by status
    status_counts = {}
    class_counts = {}
    code_counts = {}
    needs_review = 0

    fields = ["Update_Status", EXISTING_CLASS_FIELD, "Original_Code"]

    with arcpy.da.SearchCursor(joined_layer, fields) as cursor:
        for row in cursor:
            status = row[0] if row[0] else "Unknown"
            wetland_class = row[1] if row[1] else "None"
            feat_code = row[2] if row[2] else "Unknown"

            status_counts[status] = status_counts.get(status, 0) + 1
            class_counts[wetland_class] = class_counts.get(wetland_class, 0) + 1
            code_counts[feat_code] = code_counts.get(feat_code, 0) + 1

            if wetland_class == "Needs Review":
                needs_review += 1

    log("\nBy Update Status:")
    for status, count in sorted(status_counts.items()):
        log(f"  {status}: {count}")

    log("\nBy WETLAND Class:")
    for wclass, count in sorted(class_counts.items()):
        log(f"  {wclass}: {count}")

    log("\nBy feat_code:")
    for code, count in sorted(code_counts.items()):
        log(f"  {code}: {count}")

    if needs_review > 0:
        log(f"\n⚠️  WARNING: {needs_review} polygons marked 'Needs Review' - manual classification required.")

    log("=" * 60 + "\n")


def copy_final_output(joined_layer):
    """Copy to final output location with clean name."""
    log("Creating final output...")

    final_output = os.path.join(SCRATCH_GDB, OUTPUT_NAME)

    if arcpy.Exists(final_output):
        arcpy.Delete_management(final_output)

    arcpy.CopyFeatures_management(joined_layer, final_output)

    log(f"Final output: {final_output}")
    return final_output


def cleanup_intermediate(layers_to_delete):
    """Remove intermediate datasets."""
    log("Cleaning up intermediate data...")

    for layer in layers_to_delete:
        if arcpy.Exists(layer):
            try:
                arcpy.Delete_management(layer)
            except:
                pass


def main():
    """Main execution function."""
    log("=" * 60)
    log("WETLAND BOUNDARY UPDATE SCRIPT")
    log("=" * 60)

    arcpy.env.overwriteOutput = True

    intermediate_layers = []

    try:
        # Step 1: Validate inputs
        check_inputs()

        # Step 2: Filter NSTDB to relevant features
        nstdb_filtered = filter_nstdb()
        intermediate_layers.append(nstdb_filtered)

        # Step 3: Check/fix coordinate systems
        nstdb_projected = check_coordinate_systems(nstdb_filtered)
        if nstdb_projected != nstdb_filtered:
            intermediate_layers.append(nstdb_projected)

        # Step 4: Spatial join to transfer classifications
        joined_layer = spatial_join_classifications(nstdb_projected)
        # Don't add to intermediate - we'll use this for final output

        # Step 5: Generate lookup table BEFORE modifying the joined layer
        lookup_table, lookup_data = generate_lookup_table(joined_layer)

        # Step 6: Add tracking fields
        add_update_fields(joined_layer)

        # Step 7: Calculate fields and assign WETLAND classes
        calculate_fields_and_assign_classes(joined_layer, lookup_data)

        # Step 8: Generate summary
        generate_summary(joined_layer)

        # Step 9: Create final output
        final_output = copy_final_output(joined_layer)

        # Step 10: Cleanup (keep joined_layer for now, delete others)
        intermediate_layers.append(joined_layer)
        cleanup_intermediate(intermediate_layers)

        log("Script completed successfully!")
        log(f"Output feature class: {final_output}")
        log(f"Lookup table: {lookup_table}")

    except Exception as e:
        log(f"ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()