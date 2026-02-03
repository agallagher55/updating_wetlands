"""
Find which existing wetland has WETLAND='Swamp' and HECTARES=NULL
that might be incorrectly matched to our NSTDB feature
"""
import arcpy

EXISTING_WETLANDS = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde\SDEADM.NAT_wetland_freshwater"
WETLANDS_UPDATED = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Updated"

print("=" * 80)
print("FINDING EXISTING WETLANDS WITH WETLAND='Swamp' AND HECTARES=NULL")
print("=" * 80)

# Find all existing wetlands with these characteristics
swamp_null_wetlands = []
with arcpy.da.SearchCursor(EXISTING_WETLANDS,
                          ["OBJECTID", "WETLAND", "HECTARES", "Shape@"]) as cursor:
    for row in cursor:
        objectid = row[0]
        wetland = row[1]
        hectares = row[2]
        shape = row[3]

        if wetland == "Swamp" and (hectares is None or hectares == 0):
            swamp_null_wetlands.append({
                'objectid': objectid,
                'wetland': wetland,
                'hectares': hectares,
                'shape': shape
            })

print(f"\nFound {len(swamp_null_wetlands)} existing wetlands with WETLAND='Swamp' and NULL/0 HECTARES:")
for w in swamp_null_wetlands[:10]:  # Show first 10
    print(f"  OBJECTID: {w['objectid']}, HECTARES: {w['hectares']}")

# Now check if any of these overlap with OBJECTID 6972 in Wetlands_Updated
print("\n" + "=" * 80)
print("CHECKING WHICH OF THESE OVERLAP WITH OBJECTID 6972")
print("=" * 80)

# Get the problem feature from Wetlands_Updated
problem_feature = None
with arcpy.da.SearchCursor(WETLANDS_UPDATED,
                          ["OBJECTID", "Shape@"],
                          where_clause="OBJECTID = 6972") as cursor:
    for row in cursor:
        problem_feature = row[1]
        break

if problem_feature:
    overlaps = []
    for w in swamp_null_wetlands:
        if problem_feature.overlaps(w['shape']) or \
           problem_feature.contains(w['shape']) or \
           w['shape'].contains(problem_feature) or \
           problem_feature.equals(w['shape']):

            intersection = problem_feature.intersect(w['shape'], 4)
            overlap_pct = (intersection.area / problem_feature.area) * 100

            overlaps.append({
                'objectid': w['objectid'],
                'overlap_pct': overlap_pct,
                'area': w['shape'].area
            })

    if overlaps:
        print(f"\n✓ Found {len(overlaps)} Swamp (NULL hectares) wetland(s) that overlap:")
        for o in sorted(overlaps, key=lambda x: x['overlap_pct'], reverse=True):
            print(f"  OBJECTID: {o['objectid']}, Overlap: {o['overlap_pct']:.1f}%")
        print("\n** This explains why WETLAND='Swamp' in the output!")
        print("** The spatial join matched to this Swamp wetland instead of the Marsh (31146)")
    else:
        print("\n❌ NO Swamp (NULL hectares) wetlands overlap with this feature")
        print("   This is very strange - the spatial join result doesn't match reality")
else:
    print("ERROR: Could not find OBJECTID 6972 in Wetlands_Updated")

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print("Your troubleshooting showed 71% overlap with OBJECTID 31146 (Marsh)")
print("But spatial join assigned WETLAND='Swamp' and HECTARES=NULL")
print("\nThis suggests the spatial join matched to a DIFFERENT existing wetland")
print("than the one with the largest overlap. Possible reasons:")
print("  1. Spatial join happened BEFORE coordinate projection")
print("  2. LARGEST_OVERLAP isn't working as expected")
print("  3. Geometry/topology issues causing incorrect matching")
print("=" * 80)
