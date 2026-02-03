"""
Troubleshooting Script: Why is a feature marked as "New"?
---------------------------------------------------------
This script helps diagnose why features are incorrectly marked as new
when they should be existing wetlands.

Run this in ArcGIS Pro Python window to investigate spatial join issues.
"""

import arcpy

# Configuration - UPDATE THESE
WETLANDS_UPDATED = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\data\scratch.gdb\Wetlands_Updated"
EXISTING_WETLANDS = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde\SDEADM.NAT_wetland_freshwater"
PROBLEM_OBJECTID = 6972  # The OBJECTID from Wetlands_Updated that's marked as "New"

# Investigation
print("=" * 80)
print("SPATIAL JOIN INVESTIGATION")
print("=" * 80)

# Get the problem feature
problem_feature = None
with arcpy.da.SearchCursor(WETLANDS_UPDATED,
                          ["OBJECTID", "Shape@", "WETLAND", "IS_NEW", "feat_code", "Join_Count"],
                          where_clause=f"OBJECTID = {PROBLEM_OBJECTID}") as cursor:
    for row in cursor:
        problem_feature = {
            'objectid': row[0],
            'shape': row[1],
            'wetland': row[2],
            'is_new': row[3],
            'feat_code': row[4],
            'join_count': row[5]
        }
        print(f"\nProblem Feature (OBJECTID {row[0]}):")
        print(f"  WETLAND: {row[2]}")
        print(f"  IS_NEW: {row[3]}")
        print(f"  feat_code: {row[4]}")
        print(f"  Join_Count: {row[5]}")
        print(f"  Area: {row[1].area:,.2f} sq meters")

if not problem_feature:
    print(f"ERROR: Could not find feature with OBJECTID {PROBLEM_OBJECTID}")
    exit()

print("\n" + "-" * 80)
print("CHECKING FOR OVERLAPPING EXISTING WETLANDS:")
print("-" * 80)

# Find all existing wetlands that overlap this feature
overlap_count = 0
with arcpy.da.SearchCursor(EXISTING_WETLANDS,
                          ["OBJECTID", "WETLAND", "HECTARES", "Shape@"]) as cursor:
    for row in cursor:
        existing_shape = row[3]

        # Check if they intersect
        if problem_feature['shape'].overlaps(existing_shape) or \
           problem_feature['shape'].contains(existing_shape) or \
           existing_shape.contains(problem_feature['shape']) or \
           problem_feature['shape'].equals(existing_shape):

            # Calculate overlap
            intersection = problem_feature['shape'].intersect(existing_shape, 4)  # 4 = geometry
            overlap_area = intersection.area
            overlap_pct = (overlap_area / problem_feature['shape'].area) * 100

            overlap_count += 1
            print(f"\n  Match #{overlap_count}:")
            print(f"    Existing OBJECTID: {row[0]}")
            print(f"    WETLAND: {row[1]}")
            print(f"    HECTARES: {row[2]}")
            print(f"    Overlap Area: {overlap_area:,.2f} sq meters")
            print(f"    Overlap %: {overlap_pct:.1f}% of new feature")
            print(f"    Existing Area: {existing_shape.area:,.2f} sq meters")

if overlap_count == 0:
    print("\n  ❌ NO OVERLAPPING EXISTING WETLANDS FOUND!")
    print("  This explains why it's marked as 'New'")
    print("\n  Possible reasons:")
    print("    - This is genuinely a new wetland in NSTDB")
    print("    - Coordinate system mismatch")
    print("    - Existing wetland was deleted/removed from source data")
else:
    print(f"\n  Found {overlap_count} overlapping existing wetland(s)")
    print("\n  If Join_Count > 0 but still marked as 'New', possible reasons:")
    print("    - WETLAND field from spatial join was NULL/empty")
    print("    - Spatial join matched but classification didn't transfer")
    print("    - Script logic issue with field name matching")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

if problem_feature['join_count'] and problem_feature['join_count'] > 0:
    print("  • Join_Count > 0 suggests spatial join found a match")
    print("  • But feature is still marked as 'New'")
    print("  • Check if WETLAND field from existing data was NULL")
    print(f"  • Current WETLAND value: '{problem_feature['wetland']}'")
    print("  • This looks like a DEFAULT assignment (from feat_code mapping)")
    print("\n  ACTION: Review the existing wetland data - does the overlapping")
    print("          feature have a NULL or empty WETLAND field?")
elif overlap_count > 0:
    print("  • Overlapping wetlands exist but spatial join didn't match")
    print("  • Possible reasons:")
    print("    - Overlap % too small for 'LARGEST_OVERLAP' logic")
    print("    - Multiple overlaps causing ambiguous match")
    print("    - Coordinate system issue")
    print("\n  ACTION: Consider adjusting spatial join match_option or threshold")
else:
    print("  • No overlapping existing wetlands found")
    print("  • This feature is correctly marked as 'New'")
    print("\n  ACTION: Verify this is genuinely a new wetland in NSTDB data")

print("=" * 80)
