"""
Find Existing Wetlands NOT in New NSTDB Data
---------------------------------------------
Identifies wetlands from NAT_wetland_freshwater that don't have a
corresponding feature in the new geo_export_HRM data.

These are wetlands that will be DELETED if you do a truncate/load.
"""

import arcpy
from collections import defaultdict

# Configuration
EXISTING_WETLANDS = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde\SDEADM.NAT_wetland_freshwater"
NEW_NSTDB = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\geo_export_HRM"
SCRATCH_GDB = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb"

# Output for missing wetlands
OUTPUT_MISSING = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Missing_Existing_Wetlands"

# Relevant NSTDB feature codes (should match your script)
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

print("=" * 80)
print("FINDING EXISTING WETLANDS NOT IN NEW NSTDB DATA")
print("=" * 80)

# Filter new NSTDB to relevant codes
print("\nFiltering NSTDB to relevant feature codes...")
codes_str = "', '".join(RELEVANT_FEAT_CODES)
where_clause = f"feat_code IN ('{codes_str}')"

nstdb_filtered = SCRATCH_GDB + "\\NSTDB_Filtered_Temp"
if arcpy.Exists(nstdb_filtered):
    arcpy.Delete_management(nstdb_filtered)

arcpy.Select_analysis(
    in_features=NEW_NSTDB,
    out_feature_class=nstdb_filtered,
    where_clause=where_clause
)

nstdb_count = int(arcpy.GetCount_management(nstdb_filtered)[0])
existing_count = int(arcpy.GetCount_management(EXISTING_WETLANDS)[0])

print(f"  Existing wetlands: {existing_count:,}")
print(f"  New NSTDB features (filtered): {nstdb_count:,}")

# Check coordinate systems and project if needed
print("\nChecking coordinate systems...")
existing_sr = arcpy.Describe(EXISTING_WETLANDS).spatialReference
nstdb_sr = arcpy.Describe(nstdb_filtered).spatialReference

if existing_sr.factoryCode != nstdb_sr.factoryCode:
    print(f"  Projecting NSTDB from {nstdb_sr.name} to {existing_sr.name}...")
    nstdb_projected = SCRATCH_GDB + "\\NSTDB_Projected_Temp"
    if arcpy.Exists(nstdb_projected):
        arcpy.Delete_management(nstdb_projected)

    arcpy.Project_management(
        in_dataset=nstdb_filtered,
        out_dataset=nstdb_projected,
        out_coor_system=existing_sr
    )
    nstdb_to_use = nstdb_projected
else:
    print("  Coordinate systems match.")
    nstdb_to_use = nstdb_filtered

# Spatial join from EXISTING to NEW (reverse direction)
# This will identify which existing wetlands have NO match in new data
print("\nPerforming spatial join (existing → new) to find unmatched wetlands...")
joined_temp = SCRATCH_GDB + "\\Existing_To_New_Join_Temp"
if arcpy.Exists(joined_temp):
    arcpy.Delete_management(joined_temp)

arcpy.SpatialJoin_analysis(
    target_features=EXISTING_WETLANDS,
    join_features=nstdb_to_use,
    out_feature_class=joined_temp,
    join_operation="JOIN_ONE_TO_ONE",
    join_type="KEEP_ALL",
    match_option="LARGEST_OVERLAP"
)

# Select features where Join_Count = 0 (no match in new data)
print("\nIdentifying wetlands with NO match in new NSTDB data...")

if arcpy.Exists(OUTPUT_MISSING):
    arcpy.Delete_management(OUTPUT_MISSING)

arcpy.Select_analysis(
    in_features=joined_temp,
    out_feature_class=OUTPUT_MISSING,
    where_clause="Join_Count = 0"
)

missing_count = int(arcpy.GetCount_management(OUTPUT_MISSING)[0])

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)
print(f"Total existing wetlands: {existing_count:,}")
print(f"Existing wetlands NOT in new NSTDB: {missing_count:,}")
print(f"Match rate: {((existing_count - missing_count) / existing_count * 100):.1f}%")

if missing_count > 0:
    print(f"\n⚠️  WARNING: {missing_count:,} existing wetlands will be LOST if you truncate/load!")
    print(f"\nMissing wetlands saved to:")
    print(f"  {OUTPUT_MISSING}")

    # Summary by WETLAND class
    print("\n" + "-" * 80)
    print("MISSING WETLANDS BY CLASS:")
    print("-" * 80)

    wetland_counts = defaultdict(int)
    total_area = 0

    with arcpy.da.SearchCursor(OUTPUT_MISSING, ["WETLAND", "HECTARES"]) as cursor:
        for row in cursor:
            wetland_class = row[0] if row[0] else "Unknown"
            hectares = row[1] if row[1] else 0
            wetland_counts[wetland_class] += 1
            total_area += hectares

    for wetland_class, count in sorted(wetland_counts.items()):
        print(f"  {wetland_class}: {count:,} features")

    print(f"\nTotal area of missing wetlands: {total_area:,.2f} hectares")

    print("\n" + "-" * 80)
    print("NEXT STEPS:")
    print("-" * 80)
    print("1. Review the missing wetlands feature class in ArcGIS Pro")
    print("2. Determine if these are:")
    print("   a. Legitimate deletions (wetland no longer exists)")
    print("   b. Classification changes (wetland reclassified to different type)")
    print("   c. Data quality issues (should still be included)")
    print("3. Consider:")
    print("   - Manually adding back critical wetlands")
    print("   - Flagging for field verification")
    print("   - Documenting deletions for stakeholder review")
else:
    print("\n✓ All existing wetlands have matches in new NSTDB data")
    print("  No wetlands will be lost in the update")

# Cleanup temp files
print("\nCleaning up temporary files...")
for temp_file in [nstdb_filtered, joined_temp]:
    if arcpy.Exists(temp_file):
        arcpy.Delete_management(temp_file)

if 'nstdb_projected' in locals() and arcpy.Exists(nstdb_projected):
    arcpy.Delete_management(nstdb_projected)

print("\n" + "=" * 80)
print("COMPLETE")
print("=" * 80)
