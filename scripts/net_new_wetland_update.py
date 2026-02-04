"""
Net New Wetland Update Script for ArcGIS Pro
-------------------------------------------
Creates three outputs:
1) Wetlands_Updated: NSTDB features that match existing wetlands (updated geometry),
   plus net-new NSTDB features, with IS_NEW/Update_Status fields.
2) Wetlands_New: subset of Wetlands_Updated where IS_NEW = 1.
3) Wetlands_Missing: existing wetlands not found in NSTDB.

The WETLAND value from NAT_wetland_freshwater is preserved for matched features.
"""

import arcpy
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================================================

SCRATCH_GDB = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb"
SDE = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde"

# Input datasets
EXISTING_WETLANDS = os.path.join(SDE, "SDEADM.NAT_wetland_freshwater")
NSTDB_WATER_FEATURES = os.path.join(SCRATCH_GDB, "geo_export_HRM")

# Output names
OUTPUT_UPDATED = "Wetlands_Updated"
OUTPUT_NEW = "Wetlands_New"
OUTPUT_MISSING = "Wetlands_Missing"

# Field names
EXISTING_CLASS_FIELD = "WETLAND"
NSTDB_CODE_FIELD = "feat_code"
NSTDB_DESC_FIELD = "feat_desc"

# NSTDB feature codes to include
RELEVANT_FEAT_CODES = [
    "WASW40",
    "WALK40",
    "WARV40",
    "WARS40",
    "WACO40",
    "WACB40",
    "WACORV40",
    "WARVLK40",
    "WACA40",
    "WAFI40",
    "WAFU40",
    "WARA40",
]

# Mapping from NSTDB feat_code to WETLAND description for new features.
# These values align with NAT_wetland_freshwater WETLAND field values.
FEAT_CODE_TO_WETLAND = {
    "WASW40": "Swamp",
    "WALK40": "Lake",
    "WARV40": "River",
    "WARS40": "River",
    "WACO40": "Coastal",
    "WACB40": "Coastal",
    "WACORV40": "Coastal",
    "WARVLK40": "Lake",
    "WACA40": "Canal",
    "WAFI40": "Filled",
    "WAFU40": "Functional",
    "WARA40": "Rapid",
}


def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def check_inputs():
    log("Checking input datasets...")
    if not arcpy.Exists(EXISTING_WETLANDS):
        raise FileNotFoundError(f"Existing wetlands not found: {EXISTING_WETLANDS}")
    if not arcpy.Exists(NSTDB_WATER_FEATURES):
        raise FileNotFoundError(f"NSTDB data not found: {NSTDB_WATER_FEATURES}")

    existing_fields = [f.name for f in arcpy.ListFields(EXISTING_WETLANDS)]
    if EXISTING_CLASS_FIELD not in existing_fields:
        raise ValueError(
            f"Field '{EXISTING_CLASS_FIELD}' not found in existing wetlands. "
            f"Available fields: {existing_fields}"
        )
    nstdb_fields = [f.name for f in arcpy.ListFields(NSTDB_WATER_FEATURES)]
    for field_name in (NSTDB_CODE_FIELD, NSTDB_DESC_FIELD):
        if field_name not in nstdb_fields:
            raise ValueError(
                f"Field '{field_name}' not found in NSTDB data. Available fields: {nstdb_fields}"
            )

    log("Input validation passed.")


def filter_nstdb():
    log("Filtering NSTDB to relevant feature codes...")
    codes_str = "', '".join(RELEVANT_FEAT_CODES)
    where_clause = f"{NSTDB_CODE_FIELD} IN ('{codes_str}')"
    output_filtered = os.path.join(SCRATCH_GDB, "NSTDB_Filtered")

    if arcpy.Exists(output_filtered):
        arcpy.Delete_management(output_filtered)

    arcpy.Select_analysis(
        in_features=NSTDB_WATER_FEATURES,
        out_feature_class=output_filtered,
        where_clause=where_clause,
    )

    count = int(arcpy.GetCount_management(output_filtered)[0])
    log(f"Filtered to {count} features.")
    return output_filtered


def ensure_matching_spatial_ref(nstdb_filtered):
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
            out_coor_system=existing_sr,
        )
        return output_projected

    log("Coordinate systems match.")
    return nstdb_filtered


def spatial_join_nstdb_to_existing(nstdb_layer):
    log("Spatial join: NSTDB -> Existing wetlands")
    output_joined = os.path.join(SCRATCH_GDB, "Wetlands_Joined")
    if arcpy.Exists(output_joined):
        arcpy.Delete_management(output_joined)

    field_mappings = arcpy.FieldMappings()
    field_mappings.addTable(nstdb_layer)

    fm_wetland = arcpy.FieldMap()
    fm_wetland.addInputField(EXISTING_WETLANDS, EXISTING_CLASS_FIELD)
    wetland_field = fm_wetland.outputField
    wetland_field.name = "WETLAND_Join"
    wetland_field.aliasName = "WETLAND (from existing)"
    fm_wetland.outputField = wetland_field
    field_mappings.addFieldMap(fm_wetland)

    fm_objectid = arcpy.FieldMap()
    fm_objectid.addInputField(EXISTING_WETLANDS, "OBJECTID")
    objectid_field = fm_objectid.outputField
    objectid_field.name = "Source_OID"
    objectid_field.aliasName = "Source OBJECTID"
    objectid_field.type = "Integer"
    fm_objectid.outputField = objectid_field
    field_mappings.addFieldMap(fm_objectid)

    arcpy.SpatialJoin_analysis(
        target_features=nstdb_layer,
        join_features=EXISTING_WETLANDS,
        out_feature_class=output_joined,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=field_mappings,
        match_option="LARGEST_OVERLAP",
    )

    return output_joined


def spatial_join_existing_to_nstdb(nstdb_layer):
    log("Spatial join: Existing wetlands -> NSTDB")
    output_joined = os.path.join(SCRATCH_GDB, "Existing_Joined")
    if arcpy.Exists(output_joined):
        arcpy.Delete_management(output_joined)

    arcpy.SpatialJoin_analysis(
        target_features=EXISTING_WETLANDS,
        join_features=nstdb_layer,
        out_feature_class=output_joined,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="LARGEST_OVERLAP",
    )

    return output_joined


def add_update_fields(joined_layer):
    existing_fields = [f.name for f in arcpy.ListFields(joined_layer)]
    if "Update_Status" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Update_Status", "TEXT", field_length=20)
    if "IS_NEW" not in existing_fields:
        arcpy.AddField_management(joined_layer, "IS_NEW", "SHORT")
    if "Update_Date" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Update_Date", "DATE")
    if "Previous_WETLAND" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Previous_WETLAND", "TEXT", field_length=50)
    if "Original_Code" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Original_Code", "TEXT", field_length=20)
    if "Source_OBJECTID" not in existing_fields:
        arcpy.AddField_management(joined_layer, "Source_OBJECTID", "LONG")
    if EXISTING_CLASS_FIELD not in existing_fields:
        arcpy.AddField_management(joined_layer, EXISTING_CLASS_FIELD, "TEXT", field_length=50)


def populate_update_fields(joined_layer):
    log("Populating update fields for NSTDB -> Existing join...")
    fields = [
        NSTDB_CODE_FIELD,
        "WETLAND_Join",
        EXISTING_CLASS_FIELD,
        "Update_Status",
        "Update_Date",
        "Original_Code",
        "IS_NEW",
        "Source_OBJECTID",
        "Previous_WETLAND",
        "Source_OID",
        "Join_Count",
    ]

    now = datetime.now()
    new_count = 0
    existing_count = 0
    wetland_assigned = 0
    wetland_missing = 0

    with arcpy.da.UpdateCursor(joined_layer, fields) as cursor:
        for row in cursor:
            feat_code = row[0]
            joined_wetland = row[1]
            join_count = row[10]
            source_oid = row[9]

            row[5] = feat_code
            row[4] = now
            row[8] = joined_wetland if joined_wetland else None
            row[7] = source_oid if source_oid else None

            if join_count == 0:
                row[6] = 1
                row[3] = "New"
                # Assign WETLAND description based on feat_code lookup
                wetland_value = FEAT_CODE_TO_WETLAND.get(feat_code)
                row[2] = wetland_value
                row[7] = None
                new_count += 1
                if wetland_value:
                    wetland_assigned += 1
                else:
                    wetland_missing += 1
                    log(f"WARNING: No WETLAND mapping for feat_code '{feat_code}'")
            else:
                row[6] = 0
                row[3] = "Existing"
                row[2] = joined_wetland
                existing_count += 1

            cursor.updateRow(row)

    log(f"Processed {new_count + existing_count} features:")
    log(f"  - New features: {new_count} (WETLAND assigned: {wetland_assigned}, missing: {wetland_missing})")
    log(f"  - Existing features: {existing_count}")


def write_outputs(joined_layer, existing_joined):
    log("Writing output feature classes...")
    updated_output = os.path.join(SCRATCH_GDB, OUTPUT_UPDATED)
    new_output = os.path.join(SCRATCH_GDB, OUTPUT_NEW)
    missing_output = os.path.join(SCRATCH_GDB, OUTPUT_MISSING)

    for output in (updated_output, new_output, missing_output):
        if arcpy.Exists(output):
            arcpy.Delete_management(output)

    arcpy.CopyFeatures_management(joined_layer, updated_output)
    arcpy.Select_analysis(
        in_features=updated_output,
        out_feature_class=new_output,
        where_clause="IS_NEW = 1",
    )
    arcpy.Select_analysis(
        in_features=existing_joined,
        out_feature_class=missing_output,
        where_clause="Join_Count = 0",
    )

    log(f"Updated output: {updated_output}")
    log(f"Net new output: {new_output}")
    log(f"Missing output: {missing_output}")


def main():
    log("=" * 60)
    log("NET NEW WETLAND UPDATE")
    log("=" * 60)
    arcpy.env.overwriteOutput = True

    check_inputs()
    nstdb_filtered = filter_nstdb()
    nstdb_projected = ensure_matching_spatial_ref(nstdb_filtered)

    joined_layer = spatial_join_nstdb_to_existing(nstdb_projected)
    add_update_fields(joined_layer)
    populate_update_fields(joined_layer)

    existing_joined = spatial_join_existing_to_nstdb(nstdb_projected)
    write_outputs(joined_layer, existing_joined)

    log("Script completed successfully.")


if __name__ == "__main__":
    main()
