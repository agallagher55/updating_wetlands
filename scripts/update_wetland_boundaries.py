"""
Update Wetland Boundaries Script for ArcGIS Pro
------------------------------------------------
This script creates a new wetland feature class from NSTDB data while preserving
existing Canadian Wetland Classification System classes and feat_codes.

The output is a LOCAL feature class in the scratch geodatabase that is ready
for TRUNCATE and LOAD operations into the production SDE feature class.

Key Features:
- Preserves existing WETLAND classifications via spatial join
- Maintains original feat_codes in Original_Code field
- Flags new vs existing wetlands with IS_NEW field (0=Existing, 1=New)
- Tracks source wetland IDs for traceability (Source_OBJECTID)
- Generates lookup table for feat_code to WETLAND mapping

Output Schema - Key Fields:
- WETLAND: Canadian Wetland Classification (from existing data or assigned)
- Original_Code: NSTDB feat_code (e.g., 'WASW40', 'WALK40') - PRESERVED FROM SOURCE
- IS_NEW: 0 = Existing wetland with updated boundary
           1 = New wetland not in previous dataset
- Update_Status: Text description ("Existing" or "New")
- Update_Date: Timestamp of when this update was run
- Source_OBJECTID: OBJECTID from original wetland feature (NULL for new)
- feat_code: Original NSTDB field
- feat_desc: NSTDB feature description
- SHAPE: Updated geometry from NSTDB

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

# Output location (local geodatabase - ready for truncate/load to SDE)
OUTPUT_NAME = "Wetlands_Updated"  # Name for final output feature class in SCRATCH_GDB
LOOKUP_TABLE_NAME = "Wetland_NSTDB_Lookup"  # Lookup table for feat_code to WETLAND mapping

# Note: The output will be created in SCRATCH_GDB and can be used to:
# 1. Review/QA the updated data
# 2. Truncate and load into EXISTING_WETLANDS feature class in SDE

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

    # Create field mapping to explicitly control which fields are transferred
    # This prevents field name conflicts and ensures proper attribute transfer
    log("  Creating field mapping for spatial join...")

    # Create FieldMappings object
    field_mappings = arcpy.FieldMappings()

    # Add all fields from NSTDB (target)
    field_mappings.addTable(nstdb_layer)

    # Add specific fields from existing wetlands (join)
    # Create field map for WETLAND
    fm_wetland = arcpy.FieldMap()
    fm_wetland.addInputField(EXISTING_WETLANDS, EXISTING_CLASS_FIELD)
    wetland_field = fm_wetland.outputField
    wetland_field.name = "WETLAND_Join"  # Rename to avoid conflict
    wetland_field.aliasName = "WETLAND (from existing)"
    fm_wetland.outputField = wetland_field
    field_mappings.addFieldMap(fm_wetland)

    # Create field map for HECTARES
    fm_hectares = arcpy.FieldMap()
    fm_hectares.addInputField(EXISTING_WETLANDS, "HECTARES")
    hectares_field = fm_hectares.outputField
    hectares_field.name = "HECTARES_Join"
    hectares_field.aliasName = "HECTARES (from existing)"
    fm_hectares.outputField = hectares_field
    field_mappings.addFieldMap(fm_hectares)

    # Create field map for OBJECTID from existing wetlands
    fm_objectid = arcpy.FieldMap()
    fm_objectid.addInputField(EXISTING_WETLANDS, "OBJECTID")
    objectid_field = fm_objectid.outputField
    objectid_field.name = "Source_OID"
    objectid_field.aliasName = "Source OBJECTID"
    objectid_field.type = "Integer"
    fm_objectid.outputField = objectid_field
    field_mappings.addFieldMap(fm_objectid)

    log("  Field mapping created with explicit field names")

    # Spatial join: new geometry gets classification from largest overlapping old polygon
    # arcpy.SpatialJoin_analysis(
    #     target_features=nstdb_layer,
    #     join_features=EXISTING_WETLANDS,
    #     out_feature_class=output_joined,
    #     join_operation="JOIN_ONE_TO_ONE",
    #     join_type="KEEP_ALL",
    #     match_option="LARGEST_OVERLAP"
    # )
    arcpy.SpatialJoin_analysis(
        target_features=nstdb_layer,
        join_features=EXISTING_WETLANDS,
        out_feature_class=output_joined,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=field_mappings,
        match_option="LARGEST_OVERLAP"
    )

    count = int(arcpy.GetCount_management(output_joined)[0])
    log(f"Spatial join complete. {count} features in output.")

    return output_joined


def detect_joined_field_names(joined_layer):
    """
    Detect the actual field names after spatial join.
    With explicit field mapping, we know the field names, but this validates they exist.
    """
    log("Detecting field names from spatial join...")

    all_fields = [f.name for f in arcpy.ListFields(joined_layer)]

    # With explicit field mapping, we know the field names:
    # - WETLAND_Join: WETLAND classification from existing wetlands
    # - HECTARES_Join: HECTARES from existing wetlands
    # - Source_OID: OBJECTID from existing wetlands

    wetland_field_candidates = [
        "WETLAND_Join",            # Our explicit field mapping name
        EXISTING_CLASS_FIELD,      # Fallback if no field mapping
        f"{EXISTING_CLASS_FIELD}_1",   # Old rename pattern
    ]

    joined_wetland_field = None
    for candidate in wetland_field_candidates:
        if candidate in all_fields:
            joined_wetland_field = candidate
            log(f"  Found WETLAND field: {candidate}")
            break

    if not joined_wetland_field:
        log(f"  WARNING: Could not find WETLAND field. Checked: {wetland_field_candidates}")
        log(f"  Available fields: {all_fields}")

    # Find the source OBJECTID field from joined data (EXISTING_WETLANDS)
    # JOIN_FID = OBJECTID from join_features (the existing wetlands)
    source_oid_candidates = [
        "JOIN_FID",      # OBJECTID from EXISTING_WETLANDS - this is what we want!
        "TARGET_FID",    # OBJECTID from filtered NSTDB (not what we want)
        "OBJECTID_1",
    ]

    source_oid_field = None
    for candidate in source_oid_candidates:

        if candidate in all_fields:
            source_oid_field = candidate
            log(f"  Found source OBJECTID field: {candidate}")
            break

    if not source_oid_field:
        log(f"  WARNING: Could not find source OBJECTID field")

    # Check for HECTARES field
    hectares_field_candidates = [
        "HECTARES_Join",    # Our explicit field mapping name
        "HECTARES",
        "HECTARES_1"
    ]

    hectares_field = None
    for candidate in hectares_field_candidates:
        if candidate in all_fields:
            hectares_field = candidate
            log(f"  Found HECTARES field: {candidate}")
            break

    # Check for Join_Count
    has_join_count = "Join_Count" in all_fields
    if has_join_count:
        log(f"  Found Join_Count field (indicates match status)")

    return {
        'wetland_field': joined_wetland_field,
        'source_oid_field': source_oid_field,
        'hectares_field': hectares_field,
        'has_join_count': has_join_count,
        'all_fields': all_fields
    }


def generate_lookup_table(joined_layer, field_mapping):
    """
    Generate a lookup table showing the relationship between
    NSTDB feat_code/feat_desc and existing WETLAND classifications.

    Args:
        joined_layer: The spatially joined feature class
        field_mapping: Dictionary from detect_joined_field_names() with actual field names
    """
    log("Generating lookup table from spatial join results...")

    # Get the actual WETLAND field name from spatial join
    joined_wetland_field = field_mapping.get('wetland_field', EXISTING_CLASS_FIELD)

    # Dictionary to store: feat_code -> {feat_desc, wetland_counts}
    lookup_data = defaultdict(lambda: {
        'feat_desc': None,
        'wetland_counts': defaultdict(int),
        'total_count': 0
    })

    # Read the joined data using the correct field name
    fields = [NSTDB_CODE_FIELD, NSTDB_DESC_FIELD, joined_wetland_field]

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

    # Helper function to safely add fields
    def safe_add_field(layer, field_name, field_type, **kwargs):
        """Add field only if it doesn't exist, or delete and recreate if it does."""
        existing_fields = [f.name for f in arcpy.ListFields(layer)]
        if field_name in existing_fields:
            log(f"  Field '{field_name}' already exists, skipping")
            return False
        else:
            arcpy.AddField_management(layer, field_name, field_type, **kwargs)
            return True

    # Add output WETLAND field (final classification)
    if safe_add_field(joined_layer, EXISTING_CLASS_FIELD, "TEXT", field_length=50):
        log(f"  Added {EXISTING_CLASS_FIELD} field (output wetland classification)")

    if safe_add_field(joined_layer, "Previous_WETLAND", "TEXT", field_length=50):
        log("  Added Previous_WETLAND field (original wetland classification for tracking changes)")

    if safe_add_field(joined_layer, "Update_Status", "TEXT", field_length=20):
        log("  Added Update_Status field")

    if safe_add_field(joined_layer, "IS_NEW", "SHORT"):
        log("  Added IS_NEW field (0=Existing, 1=New)")

    if safe_add_field(joined_layer, "Update_Date", "DATE"):
        log("  Added Update_Date field")

    if safe_add_field(joined_layer, "Original_Code", "TEXT", field_length=20):
        log("  Added Original_Code field")

    if safe_add_field(joined_layer, "Source_OBJECTID", "LONG"):
        log("  Added Source_OBJECTID field (original wetland ID for traceability)")

    if "Previous_WETLAND" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Previous_WETLAND", "TEXT", field_length=24)
        log("  Added Previous_WETLAND field (tracks existing WETLAND classification)")

    log("Fields added.")


def calculate_fields_and_assign_classes(joined_layer, lookup_data, field_mapping):
    """
    Calculate update status and assign WETLAND classes to all features.
    For existing wetlands (Join_Count > 0): PRESERVES the existing WETLAND classification from NAT_wetland_freshwater.
    For new wetlands (Join_Count = 0): Assigns WETLAND class based on feat_code lookup.
    Previous_WETLAND always stores the original value from NAT_wetland_freshwater (NULL for new features).

    Args:
        joined_layer: The spatially joined feature class
        lookup_data: Dictionary mapping feat_codes to wetland classifications
        field_mapping: Dictionary from detect_joined_field_names() with actual field names
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

    # Get the actual field names from spatial join
    joined_wetland_field = field_mapping.get('wetland_field')
    source_oid_field = field_mapping.get('source_oid_field')
    has_join_count = field_mapping.get('has_join_count', False)

    if not joined_wetland_field:
        log("  WARNING: Could not find joined WETLAND field. Using EXISTING_CLASS_FIELD.")
        joined_wetland_field = EXISTING_CLASS_FIELD

    log(f"  Using field '{joined_wetland_field}' for existing WETLAND classifications")
    if source_oid_field:
        log(f"  Using field '{source_oid_field}' for source OBJECTID tracking")

    # Build fields list for cursor
    fields = [
        NSTDB_CODE_FIELD,  # 0 - feat_code
        joined_wetland_field,  # 1 - WETLAND (from NAT_wetland_freshwater via spatial join)
        EXISTING_CLASS_FIELD,  # 2 - WETLAND (target field in output)
        "Update_Status",  # 3
        "Update_Date",  # 4
        "Original_Code",  # 5
        "IS_NEW",  # 6
        "Source_OBJECTID",  # 7
        "Previous_WETLAND"  # 8 - Always stores the WETLAND value from NAT_wetland_freshwater
    ]

    # Add source OBJECTID field if found
    if source_oid_field:
        fields.append(source_oid_field)
        source_oid_index = len(fields) - 1
    else:
        source_oid_index = None

    # Add Join_Count if available
    if has_join_count:
        fields.append("Join_Count")
        join_count_index = len(fields) - 1
    else:
        join_count_index = None
        log("  WARNING: Join_Count field not found - cannot reliably determine new vs existing")

    now = datetime.now()
    existing_count = 0
    new_count = 0
    preserved_count = 0

    with arcpy.da.UpdateCursor(joined_layer, fields) as cursor:
        for row in cursor:
            feat_code = row[0]
            joined_wetland = row[1]  # WETLAND value from NAT_wetland_freshwater (via spatial join)
            source_oid = row[source_oid_index] if source_oid_index is not None else None
            join_count = row[join_count_index] if join_count_index is not None else None

            # Copy feat_code to Original_Code
            row[5] = feat_code

            # Set update date
            row[4] = now

            # ALWAYS store the WETLAND value from NAT_wetland_freshwater in Previous_WETLAND
            # This will be None/NULL for new features that didn't match anything
            row[8] = joined_wetland if joined_wetland and str(joined_wetland).strip() and str(joined_wetland) not in [
                'None', '', ' '] else None

            # Determine if this is new or existing based on Join_Count
            if join_count_index is not None:
                # Use Join_Count to determine status
                if join_count == 0:
                    # IS_NEW = 1 (no match found - this is a brand new wetland)
                    row[6] = 1
                    row[3] = "New"
                    row[7] = None  # No source OBJECTID for new features
                    new_count += 1

                    # Assign WETLAND class based on lookup or default
                    assigned_class = feat_to_wetland.get(feat_code,
                                                         DEFAULT_CLASS_MAPPING.get(feat_code, "Needs Review"))
                    row[2] = assigned_class
                else:
                    # IS_NEW = 0 (match found - this is an existing wetland)
                    row[6] = 0
                    row[3] = "Existing"
                    existing_count += 1

                    # PRESERVE the existing WETLAND classification from NAT_wetland_freshwater
                    if joined_wetland and str(joined_wetland).strip() and str(joined_wetland) not in ['None', '', ' ']:
                        # Keep the existing WETLAND value - DO NOT CHANGE IT
                        row[2] = joined_wetland
                        preserved_count += 1
                    else:
                        # Existing wetland but WETLAND was NULL in source - assign based on feat_code
                        assigned_class = feat_to_wetland.get(feat_code, "Needs Review")
                        row[2] = assigned_class
                        log(f"  Note: Existing feature (OID {source_oid}) had NULL WETLAND, assigned '{assigned_class}'")

                    # Capture source OBJECTID (JOIN_FID)
                    if source_oid_index is not None:
                        row[7] = source_oid if source_oid else None
                    else:
                        row[7] = None
            else:
                # Fallback if Join_Count is not available (shouldn't happen with proper spatial join)
                log("  WARNING: Processing without Join_Count - results may be unreliable")
                if joined_wetland and str(joined_wetland).strip() and str(joined_wetland) not in ['None', '', ' ']:
                    row[6] = 0
                    row[3] = "Existing"
                    row[2] = joined_wetland  # Keep existing value
                    row[7] = source_oid if source_oid_index is not None else None
                    existing_count += 1
                    preserved_count += 1
                else:
                    row[6] = 1
                    row[3] = "New"
                    row[2] = feat_to_wetland.get(feat_code, DEFAULT_CLASS_MAPPING.get(feat_code, "Needs Review"))
                    row[7] = None
                    new_count += 1

            cursor.updateRow(row)

    log(f"Status calculated: {existing_count} existing, {new_count} new polygons.")
    log(f"Preserved {preserved_count} existing WETLAND classifications from NAT_wetland_freshwater.")


def generate_summary(joined_layer):
    """Generate summary statistics of the update."""
    log("\n" + "=" * 60)
    log("FINAL OUTPUT SUMMARY")
    log("=" * 60)

    # Count by status
    status_counts = {}
    class_counts = {}
    code_counts = {}
    new_vs_existing = {0: 0, 1: 0}
    needs_review = 0

    fields = ["Update_Status", EXISTING_CLASS_FIELD, "Original_Code", "IS_NEW"]

    with arcpy.da.SearchCursor(joined_layer, fields) as cursor:
        for row in cursor:
            status = row[0] if row[0] else "Unknown"
            wetland_class = row[1] if row[1] else "None"
            feat_code = row[2] if row[2] else "Unknown"
            is_new = row[3] if row[3] is not None else -1

            status_counts[status] = status_counts.get(status, 0) + 1
            class_counts[wetland_class] = class_counts.get(wetland_class, 0) + 1
            code_counts[feat_code] = code_counts.get(feat_code, 0) + 1

            if is_new in [0, 1]:
                new_vs_existing[is_new] += 1

            if wetland_class == "Needs Review":
                needs_review += 1

    total_features = sum(status_counts.values())

    log("\nBy Update Status:")
    for status, count in sorted(status_counts.items()):
        log(f"  {status}: {count}")

    log("\nBy IS_NEW Flag:")
    log(f"  Existing (IS_NEW=0): {new_vs_existing[0]}")
    log(f"  New (IS_NEW=1): {new_vs_existing[1]}")

    log("\nBy WETLAND Class:")
    for wclass, count in sorted(class_counts.items()):
        log(f"  {wclass}: {count}")

    log("\nBy feat_code (Original_Code):")
    for code, count in sorted(code_counts.items()):
        log(f"  {code}: {count}")

    log(f"\nTotal Features: {total_features}")

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

        # Step 5: Detect actual field names after spatial join
        field_mapping = detect_joined_field_names(joined_layer)

        # Step 6: Generate lookup table BEFORE modifying the joined layer
        lookup_table, lookup_data = generate_lookup_table(joined_layer, field_mapping)

        # Step 7: Add tracking fields
        add_update_fields(joined_layer)

        # Step 8: Calculate fields and assign WETLAND classes
        calculate_fields_and_assign_classes(joined_layer, lookup_data, field_mapping)

        # Step 9: Generate summary
        generate_summary(joined_layer)

        # Step 10: Create final output
        final_output = copy_final_output(joined_layer)

        # Step 11: Cleanup (keep joined_layer for now, delete others)
        # intermediate_layers.append(joined_layer)
        # cleanup_intermediate(intermediate_layers)

        log("Script completed successfully!")
        log(f"\nOutput feature class: {final_output}")
        log(f"Lookup table: {lookup_table}")

        log("\n" + "=" * 60)
        log("NEXT STEPS: TRUNCATE AND LOAD")
        log("=" * 60)
        log(f"1. Review the output feature class for QA:")
        log(f"   - Check features where IS_NEW = 1 (new wetlands)")
        log(f"   - Verify WETLAND classifications")
        log(f"   - Review any 'Needs Review' classifications")
        log(f"\n2. Query examples:")
        log(f"   - New wetlands: IS_NEW = 1")
        log(f"   - Existing wetlands: IS_NEW = 0")
        log(f"   - Specific fcode: Original_Code = 'WASW40'")
        log(f"\n3. When ready to load to SDE:")
        log(f"   a. Backup existing data: {EXISTING_WETLANDS}")
        log(f"   b. Truncate: arcpy.TruncateTable_management('{EXISTING_WETLANDS}')")
        log(f"   c. Append: arcpy.Append_management('{final_output}', '{EXISTING_WETLANDS}', 'NO_TEST')")
        log(f"\n4. The Original_Code field preserves all NSTDB feat_codes")
        log("=" * 60)

    except Exception as e:
        log(f"ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
