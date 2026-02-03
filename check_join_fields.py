"""
Check Spatial Join Fields - Find the correct join field
"""
import arcpy

WETLANDS_UPDATED = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Updated"

print("=" * 80)
print("FIELDS IN WETLANDS_UPDATED")
print("=" * 80)

# List all fields
all_fields = [f.name for f in arcpy.ListFields(WETLANDS_UPDATED)]

# Look for fields that might indicate which existing wetland was matched
join_fields = []
for field_name in all_fields:
    if any(x in field_name.upper() for x in ["TARGET", "JOIN", "FID", "OBJECTID_"]):
        join_fields.append(field_name)

print("\nFields that might indicate the matched existing wetland:")
for field in join_fields:
    print(f"  - {field}")

# Check OBJECTID 6972 specifically
print("\n" + "=" * 80)
print("OBJECTID 6972 - ALL JOIN-RELATED FIELD VALUES:")
print("=" * 80)

fields_to_check = ["OBJECTID"] + join_fields + ["WETLAND", "feat_code", "Join_Count", "IS_NEW", "Source_OBJECTID"]
fields_to_check = [f for f in fields_to_check if f in all_fields]

with arcpy.da.SearchCursor(WETLANDS_UPDATED, fields_to_check, where_clause="OBJECTID = 6972") as cursor:
    for row in cursor:
        for i, field_name in enumerate(fields_to_check):
            print(f"  {field_name}: {row[i]}")

print("\n" + "=" * 80)
