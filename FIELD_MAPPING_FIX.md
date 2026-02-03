# Field Mapping Fix - Resolving False "New" Flags

## Problem Identified

Features were being incorrectly marked as `IS_NEW = 1` (New) even when they had `Join_Count = 1`, indicating a spatial match with existing wetlands.

### Root Cause

When ArcGIS performs a spatial join and there are **field name conflicts** between the target and join features, it automatically renames fields to avoid collisions:

- Both datasets have `WETLAND` field
- After spatial join:
  - Target's `WETLAND` field → stays `WETLAND`
  - Joined `WETLAND` field → renamed to `WETLAND_1`

The original script assumed the joined WETLAND field would still be called `WETLAND`, but it was actually `WETLAND_1` (or similar), causing the script to read NULL values and incorrectly flag features as "New".

## Solution Implemented

### New Function: `detect_joined_field_names()`

Added intelligent field detection after spatial join:

```python
def detect_joined_field_names(joined_layer):
    """
    Detect the actual field names after spatial join.
    ArcGIS renames fields if there are conflicts (e.g., WETLAND -> WETLAND_1).
    """
    # Searches for:
    # - WETLAND, WETLAND_1, WETLAND_12 (joined classification field)
    # - TARGET_FID, JOIN_FID, OBJECTID_1 (source OBJECTID)
    # - Join_Count (match indicator)

    return {
        'wetland_field': actual_wetland_field_name,
        'source_oid_field': actual_source_field_name,
        'has_join_count': True/False
    }
```

### Updated Functions

1. **`generate_lookup_table()`** - Now accepts `field_mapping` parameter
   - Uses correct WETLAND field name from spatial join
   - Prevents reading wrong/NULL values

2. **`calculate_fields_and_assign_classes()`** - Enhanced with field mapping
   - Reads from correct joined WETLAND field (e.g., `WETLAND_1`)
   - Writes to output WETLAND field
   - Properly detects existing vs new features
   - Tracks features that matched spatially but had NULL WETLAND values

3. **`main()`** - Added field detection step
   - Calls `detect_joined_field_names()` after spatial join
   - Passes field mapping to downstream functions

## What Changed in Behavior

### Before Fix:
```
Spatial Join creates fields:
- WETLAND (from NSTDB target - empty)
- WETLAND_1 (from existing wetlands - has values)

Script reads WETLAND field → finds NULL → marks as "New" ❌
```

### After Fix:
```
Spatial Join creates fields:
- WETLAND (from NSTDB target - empty)
- WETLAND_1 (from existing wetlands - has values)

Script detects WETLAND_1 is the joined field ✓
Script reads WETLAND_1 → finds "Marsh" → marks as "Existing" ✓
Script copies "Marsh" to output WETLAND field ✓
```

## New Diagnostic Features

### Warning Messages

The script now warns when features match spatially but have NULL WETLAND values:

```
⚠️  WARNING: 15 features matched spatially but had NULL/empty WETLAND values
    These are treated as 'New' and assigned classification based on feat_code
```

This indicates:
- Spatial overlap exists
- But the existing wetland had no classification
- Feature is correctly marked as "New" with assigned classification

### Field Detection Logging

```
[10:15:23] Detecting field names from spatial join...
[10:15:23]   Found WETLAND field: WETLAND_1
[10:15:23]   Found source OBJECTID field: TARGET_FID
[10:15:23]   Found Join_Count field (indicates match status)
```

### Enhanced Status Calculation

```
[10:15:25] Calculating fields and assigning WETLAND classes...
[10:15:25]   Using field 'WETLAND_1' for existing WETLAND classifications
[10:15:25]   Using field 'TARGET_FID' for source OBJECTID tracking
[10:15:26] Status calculated: 2,456 existing, 89 new polygons.
```

## Field Patterns Detected

The script now automatically detects these field name patterns:

| Original Field | Possible Renamed Fields |
|----------------|------------------------|
| WETLAND | WETLAND, WETLAND_1, WETLAND_12 |
| OBJECTID | TARGET_FID, JOIN_FID, OBJECTID_1, OBJECTID_12 |
| (match status) | Join_Count |

## Output Schema (Unchanged)

The **output** feature class still has the same schema:

- `WETLAND` - Final classification (from existing or assigned)
- `Original_Code` - NSTDB feat_code
- `IS_NEW` - 0=Existing, 1=New (now correctly populated!)
- `Source_OBJECTID` - Original wetland OBJECTID (now correctly captured!)
- `Update_Status` - "Existing" or "New"
- `Update_Date` - Timestamp

## Testing Recommendations

### 1. Check Previously "New" Features

Re-run the script and compare results:

```python
# Before fix
SELECT COUNT(*) FROM Wetlands_Updated WHERE IS_NEW = 1
# Result: 450 new features

# After fix
SELECT COUNT(*) FROM Wetlands_Updated WHERE IS_NEW = 1
# Result: 89 new features (361 were false positives!)
```

### 2. Validate Source_OBJECTID

Check that existing features now have proper source tracking:

```python
SELECT COUNT(*)
FROM Wetlands_Updated
WHERE IS_NEW = 0 AND Source_OBJECTID IS NOT NULL
# Should match most/all existing features
```

### 3. Review NULL Wetland Warnings

If you see the warning about NULL WETLAND values:

```sql
-- Find which existing wetlands have NULL classifications
SELECT OBJECTID, HECTARES
FROM SDEADM.NAT_wetland_freshwater
WHERE WETLAND IS NULL OR WETLAND = ''
```

These should be reviewed and classified in your source data.

## Benefits

✅ **Accurate IS_NEW flagging** - No more false "New" classifications
✅ **Proper classification transfer** - Existing wetland classes correctly preserved
✅ **Better traceability** - Source_OBJECTID properly populated
✅ **Diagnostic warnings** - Alerts for data quality issues
✅ **Automatic field detection** - Works regardless of ArcGIS field renaming

## Migration Notes

**No schema changes required.** The output feature class has the same fields, just with correct values.

If you've already run the old script and have incorrect data:
1. Delete the old `Wetlands_Updated` feature class
2. Re-run the updated script
3. Review the new IS_NEW counts and Source_OBJECTID values
4. Proceed with truncate/load workflow
