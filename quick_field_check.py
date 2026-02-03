"""
Quick Field Name Check - Run this in ArcGIS Pro Python window
"""
import arcpy

# Check existing wetlands
fc = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde\SDEADM.NAT_wetland_freshwater"

print("Checking field names in existing wetlands...")
print("\nText fields that might contain wetland classification:")
for field in arcpy.ListFields(fc):
    if field.type == "String":
        print(f"  Field Name: '{field.name}'  |  Alias: '{field.aliasName}'")

# Check for the specific field
if "WETLAND" in [f.name for f in arcpy.ListFields(fc)]:
    print("\n✓ Field 'WETLAND' exists")
elif "Wetland_Class" in [f.name for f in arcpy.ListFields(fc)]:
    print("\n⚠️  Field is 'Wetland_Class', not 'WETLAND'")
    print("   Update EXISTING_CLASS_FIELD = 'Wetland_Class' in your script")
else:
    print("\n❌ 'WETLAND' field not found!")
    print("   Check the list above for the correct field name")
