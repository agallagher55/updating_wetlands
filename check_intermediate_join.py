"""
Check Wetlands_Joined intermediate layer - this has all spatial join fields
"""
import arcpy

JOINED = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Joined"

if not arcpy.Exists(JOINED):
    print("ERROR: Wetlands_Joined does not exist. Run the main script first.")
    exit()

print("=" * 80)
print("ALL FIELDS IN WETLANDS_JOINED (intermediate layer)")
print("=" * 80)

all_fields = arcpy.ListFields(JOINED)
for i, field in enumerate(all_fields, 1):
    print(f"{i:3d}. {field.name:<30} [{field.type:<12}] alias: {field.aliasName}")

print("\n" + "=" * 80)
print("OBJECTID 6972 - ALL FIELD VALUES (first 50 fields):")
print("=" * 80)

# Get field names (limit to avoid too much output)
field_names = [f.name for f in all_fields if not f.type == "Geometry"][:50]

with arcpy.da.SearchCursor(JOINED, field_names, where_clause="OBJECTID = 6972") as cursor:
    for row in cursor:
        for i, field_name in enumerate(field_names):
            value = row[i]
            if value is None:
                value = "<NULL>"
            # Highlight important fields
            if any(x in field_name.upper() for x in ["WETLAND", "OBJECTID", "TARGET", "JOIN", "HECTARE", "FEAT"]):
                print(f"  ** {field_name:<30} = {value}")
            else:
                print(f"     {field_name:<30} = {value}")

print("=" * 80)
