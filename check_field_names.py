"""
Field Name Diagnostic Script
-----------------------------
Run this in ArcGIS Pro Python window to check actual field names
"""

import arcpy

# Configuration
EXISTING_WETLANDS = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde\SDEADM.NAT_wetland_freshwater"
WETLANDS_UPDATED = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Updated"

print("=" * 80)
print("FIELD NAME DIAGNOSTIC")
print("=" * 80)

# Check existing wetlands fields
print("\n1. EXISTING WETLANDS FIELDS:")
print("-" * 80)
for field in arcpy.ListFields(EXISTING_WETLANDS):
    field_type = field.type
    field_name = field.name
    field_alias = field.aliasName
    if "wetland" in field_name.lower() or "wetland" in field_alias.lower() or "class" in field_name.lower():
        print(f"  ** {field_name:<30} (alias: {field_alias:<30}) [{field_type}]")
    else:
        print(f"     {field_name:<30} (alias: {field_alias:<30}) [{field_type}]")

# Check updated wetlands fields
print("\n2. WETLANDS_UPDATED FIELDS (after spatial join):")
print("-" * 80)
for field in arcpy.ListFields(WETLANDS_UPDATED):
    field_type = field.type
    field_name = field.name
    field_alias = field.aliasName
    if "wetland" in field_name.lower() or "class" in field_name.lower():
        print(f"  ** {field_name:<30} (alias: {field_alias:<30}) [{field_type}]")
    else:
        print(f"     {field_name:<30} (alias: {field_alias:<30}) [{field_type}]")

# Check a specific feature
print("\n3. SAMPLE FEATURE VALUES (OBJECTID 6972):")
print("-" * 80)
with arcpy.da.SearchCursor(WETLANDS_UPDATED,
                          ["OBJECTID", "*"],
                          where_clause="OBJECTID = 6972") as cursor:
    fields_list = cursor.fields
    for row in cursor:
        for i, field_name in enumerate(fields_list):
            if "wetland" in field_name.lower() or "class" in field_name.lower() or \
               "join" in field_name.lower() or "target" in field_name.lower() or \
               "hectare" in field_name.lower():
                print(f"  ** {field_name}: {row[i]}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

# Find the actual wetland classification field
wetland_fields = []
for field in arcpy.ListFields(EXISTING_WETLANDS):
    if "wetland" in field.name.lower() or "class" in field.name.lower():
        if field.type == "String":
            wetland_fields.append(field.name)

if wetland_fields:
    print(f"\nPossible wetland classification fields in existing data:")
    for f in wetland_fields:
        print(f"  - {f}")
    print(f"\nUpdate your script configuration:")
    print(f'  EXISTING_CLASS_FIELD = "{wetland_fields[0]}"')
else:
    print("\n⚠️  Could not find a text field with 'wetland' or 'class' in the name")

print("\n" + "=" * 80)
