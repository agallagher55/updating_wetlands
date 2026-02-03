"""
Spatial Join Result Inspector
------------------------------
Run this to see what the spatial join actually produced
"""

import arcpy

# Configuration - check the intermediate joined layer
JOINED_LAYER = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Joined"

if not arcpy.Exists(JOINED_LAYER):
    print(f"ERROR: {JOINED_LAYER} does not exist.")
    print("Run the main script first, or check the path.")
    exit()

print("=" * 80)
print("SPATIAL JOIN RESULT INSPECTION")
print("=" * 80)

# List ALL fields in the joined layer
print("\nALL FIELDS IN JOINED LAYER:")
print("-" * 80)
all_fields = arcpy.ListFields(JOINED_LAYER)
for i, field in enumerate(all_fields, 1):
    marker = "**" if any(x in field.name.lower() for x in ["wetland", "class", "join", "target", "hectare"]) else "  "
    print(f"{marker} {i:2d}. {field.name:<30} [{field.type:<15}] alias: {field.aliasName}")

# Check specific feature (OBJECTID 6972)
print("\n" + "=" * 80)
print("FEATURE OBJECTID 6972 - ALL FIELD VALUES:")
print("=" * 80)

try:
    with arcpy.da.SearchCursor(JOINED_LAYER,
                              ["OBJECTID", "*"],
                              where_clause="OBJECTID = 6972") as cursor:
        fields_list = cursor.fields
        for row in cursor:
            print(f"\nOBJECTID: {row[0]}")
            print("-" * 80)
            for i, field_name in enumerate(fields_list):
                # Skip geometry fields
                if field_name.startswith("Shape") and field_name != "Shape_Length" and field_name != "Shape_Area":
                    continue

                value = row[i]
                if value is None:
                    value_str = "<NULL>"
                else:
                    value_str = str(value)[:100]  # Limit length

                # Highlight important fields
                if any(x in field_name.lower() for x in ["wetland", "class", "join", "target", "hectare", "feat_code"]):
                    print(f"  ** {field_name:<30} = {value_str}")
                else:
                    print(f"     {field_name:<30} = {value_str}")
            break
except Exception as e:
    print(f"ERROR reading feature: {e}")

# Count features by Join_Count
print("\n" + "=" * 80)
print("JOIN_COUNT DISTRIBUTION:")
print("=" * 80)
join_counts = {}
with arcpy.da.SearchCursor(JOINED_LAYER, ["Join_Count"]) as cursor:
    for row in cursor:
        count = row[0] if row[0] is not None else 0
        join_counts[count] = join_counts.get(count, 0) + 1

for count, features in sorted(join_counts.items()):
    status = "NO MATCH" if count == 0 else f"MATCHED ({count} overlap)"
    print(f"  Join_Count = {count}: {features:,} features ({status})")

print("\n" + "=" * 80)
