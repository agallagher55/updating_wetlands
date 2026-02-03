# Spatial Join Fix - Explicit Field Mapping

## Problem Solved

Features were being incorrectly marked as `IS_NEW = 1` with wrong WETLAND classifications (e.g., "Swamp" instead of "Marsh") and NULL HECTARES values, even when they clearly overlapped with existing wetlands.

## Root Cause

The spatial join was not using explicit field mapping, causing ArcGIS to:
- Create ambiguous or conflicting field names
- Not properly transfer attributes from existing wetlands
- Leave WETLAND and HECTARES fields unpopulated or incorrectly populated

Your manual spatial join worked because it specified explicit `field_mapping` parameter.

## The Fix

### 1. Added Explicit Field Mapping to Spatial Join

```python
def spatial_join_classifications(nstdb_layer):
    # Create FieldMappings object
    field_mappings = arcpy.FieldMappings()

    # Add all fields from NSTDB (target)
    field_mappings.addTable(nstdb_layer)

    # Explicitly map fields from existing wetlands:
    # - WETLAND → WETLAND_Join
    # - HECTARES → HECTARES_Join
    # - OBJECTID → Source_OID

    arcpy.SpatialJoin_analysis(
        target_features=nstdb_layer,
        join_features=EXISTING_WETLANDS,
        out_feature_class=output_joined,
        field_mapping=field_mappings,  # ← KEY FIX
        match_option="LARGEST_OVERLAP"
    )
```

### 2. New Field Names (Predictable & Conflict-Free)

| Old (Ambiguous) | New (Explicit) | Purpose |
|-----------------|----------------|---------|
| WETLAND or WETLAND_1 | **WETLAND_Join** | Classification from existing wetlands |
| HECTARES or NULL | **HECTARES_Join** | Area from existing wetlands |
| TARGET_FID (wrong!) | **Source_OID** | OBJECTID of matched existing wetland |

### 3. Updated Field Detection

The `detect_joined_field_names()` function now looks for:
1. `WETLAND_Join` (our explicit name)
2. `Source_OID` (our explicit name)
3. `HECTARES_Join` (our explicit name)
4. Falls back to old patterns for compatibility

## Output Schema

### Intermediate Layer (Wetlands_Joined)

After spatial join, the intermediate layer has:

| Field | Source | Description |
|-------|--------|-------------|
| OBJECTID | Auto | Feature ID |
| feat_code | NSTDB | Feature code (e.g., WASW40) |
| feat_desc | NSTDB | Feature description |
| **WETLAND_Join** | Existing wetlands | Classification from matched wetland |
| **HECTARES_Join** | Existing wetlands | Area from matched wetland |
| **Source_OID** | Existing wetlands | OBJECTID of matched wetland |
| Join_Count | Auto | Number of matches (1 = matched, 0 = new) |

### Final Output (Wetlands_Updated)

After processing, the final output has:

| Field | Description | Example Values |
|-------|-------------|----------------|
| **WETLAND** | Final classification | "Marsh", "Swamp", "Water" |
| **Original_Code** | NSTDB feat_code | "WASW40", "WALK40" |
| **IS_NEW** | 0=Existing, 1=New | 0, 1 |
| **Source_OBJECTID** | Original wetland OBJECTID | 31146, NULL for new |
| **Update_Status** | Text status | "Existing", "New" |
| **Update_Date** | Processing timestamp | 2026-02-03 |

## How It Works Now

### For Existing Wetlands (with Match):

```
1. NSTDB feature overlaps existing wetland OBJECTID 31146 (Marsh)
2. Spatial join transfers:
   - WETLAND_Join = "Marsh"
   - HECTARES_Join = 1.61711
   - Source_OID = 31146
   - Join_Count = 1
3. Script detects WETLAND_Join has value → marks as Existing
4. Output:
   - WETLAND = "Marsh" (copied from WETLAND_Join)
   - IS_NEW = 0
   - Source_OBJECTID = 31146
   - Update_Status = "Existing"
```

### For New Wetlands (no Match):

```
1. NSTDB feature doesn't overlap any existing wetland
2. Spatial join leaves:
   - WETLAND_Join = NULL
   - HECTARES_Join = NULL
   - Source_OID = NULL
   - Join_Count = 0
3. Script detects WETLAND_Join is NULL → marks as New
4. Assigns classification based on feat_code:
   - WASW40 → "Swamp"
   - WALK40 → "Water"
5. Output:
   - WETLAND = "Swamp" (assigned from feat_code)
   - IS_NEW = 1
   - Source_OBJECTID = NULL
   - Update_Status = "New"
```

## Testing the Fix

### 1. Re-run the Script

Delete old output and re-run:

```python
# Delete old outputs
arcpy.Delete_management(r"T:\...\scratch.gdb\Wetlands_Updated")
arcpy.Delete_management(r"T:\...\scratch.gdb\Wetlands_Joined")

# Run the updated script
exec(open(r'path\to\update_wetland_boundaries.py').read())
```

### 2. Check OBJECTID 6972

Should now show:
- `WETLAND = "Marsh"` (not "Swamp"!)
- `HECTARES_Join = 1.61711` (not NULL!)
- `Source_OID = 31146` (correct match!)
- `IS_NEW = 0` (not 1!)

### 3. Verify Field Names in Wetlands_Joined

```python
for f in arcpy.ListFields("Wetlands_Joined"):
    if any(x in f.name for x in ["WETLAND", "HECTARES", "Source"]):
        print(f"{f.name}: {f.aliasName}")
```

Should see:
- `WETLAND_Join: WETLAND (from existing)`
- `HECTARES_Join: HECTARES (from existing)`
- `Source_OID: Source OBJECTID`

### 4. Check IS_NEW Distribution

```python
# Count by IS_NEW
with arcpy.da.SearchCursor("Wetlands_Updated", ["IS_NEW"]) as cursor:
    counts = {0: 0, 1: 0}
    for row in cursor:
        counts[row[0]] += 1
    print(f"Existing (IS_NEW=0): {counts[0]:,}")
    print(f"New (IS_NEW=1): {counts[1]:,}")
```

You should see **significantly fewer** "New" features than before.

## Additional Script: find_missing_wetlands.py

### Purpose

Identifies existing wetlands that are **NOT** in the new NSTDB data. These will be **deleted** if you do a truncate/load.

### Usage

```python
exec(open(r'T:\...\find_missing_wetlands.py').read())
```

### Output

- Feature class: `Missing_Existing_Wetlands`
- Contains: All existing wetlands with no corresponding NSTDB feature
- Summary: Count by WETLAND class, total area

### Review Steps

1. Open `Missing_Existing_Wetlands` in ArcGIS Pro
2. Identify why each is missing:
   - Legitimate deletion (wetland no longer exists)
   - Reclassification (changed to different type)
   - Data quality issue (should still be included)
3. Decide:
   - Document deletions for stakeholder review
   - Manually add back critical wetlands
   - Flag for field verification

## Comparison: Before vs After

### Before Fix:

```
Spatial Join:
  WETLAND (from NSTDB) = NULL
  WETLAND_1 (from existing) = "Marsh" ← Script couldn't find this field!

Script Logic:
  Reads WETLAND field → finds NULL
  Marks as IS_NEW = 1 (New)
  Assigns "Swamp" from WASW40 feat_code

Result: ❌ Incorrect
  WETLAND = "Swamp"
  IS_NEW = 1
  Source_OBJECTID = NULL
```

### After Fix:

```
Spatial Join:
  WETLAND_Join = "Marsh" ← Explicit field mapping
  Source_OID = 31146

Script Logic:
  Reads WETLAND_Join → finds "Marsh"
  Marks as IS_NEW = 0 (Existing)
  Copies "Marsh" to output WETLAND field

Result: ✓ Correct
  WETLAND = "Marsh"
  IS_NEW = 0
  Source_OBJECTID = 31146
```

## Key Benefits

✅ **Accurate IS_NEW flagging** - Features correctly identified as existing vs new
✅ **Preserved classifications** - Marsh stays Marsh, not changed to Swamp
✅ **Proper traceability** - Source_OBJECTID correctly populated
✅ **HECTARES transfer** - Area values properly transferred
✅ **Predictable fields** - No more ambiguous WETLAND_1, OBJECTID_1, etc.
✅ **Missing wetlands report** - Know what's being removed before you load

## Migration Notes

**No manual migration needed.** Just:
1. Delete old `Wetlands_Updated` and `Wetlands_Joined` layers
2. Re-run the updated script
3. Review new IS_NEW counts (should be much more accurate)
4. Run `find_missing_wetlands.py` to see what's being removed
5. Proceed with QA and truncate/load workflow

---

**Changes committed to:** `claude/update-wetlands-data-WUMMg`
**Files modified:**
- `scripts/update_wetland_boundaries.py` - Fixed spatial join with explicit field mapping
- `find_missing_wetlands.py` - New script to identify wetlands being removed
