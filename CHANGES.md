# Wetland Update Script Changes

## Summary
Updated `update_wetland_boundaries.py` to create a local geodatabase feature class ready for **truncate and load** operations, with clear flagging of new vs existing wetlands.

## Key Changes

### 1. **IS_NEW Flag Field** (NEW)
- Added `IS_NEW` field (SHORT type)
- Values:
  - `0` = Existing wetland with updated boundary
  - `1` = New wetland not in previous dataset
- Makes it easy to filter/query new wetlands

### 2. **Source_OBJECTID Field** (NEW)
- Added `Source_OBJECTID` field (LONG type)
- Tracks the original OBJECTID from existing wetlands
- Provides traceability back to source data
- NULL for new wetlands

### 3. **Enhanced Output Documentation**
- Updated script header with clear description of output schema
- All key fields documented with their purpose
- Clear indication this is for truncate/load operations

### 4. **Improved Summary Report**
- Added IS_NEW counts to summary output
- Shows breakdown of existing vs new features
- Provides total feature count

### 5. **Truncate/Load Instructions**
- Added "NEXT STEPS" section to output
- Includes example queries for QA
- Step-by-step truncate and load commands
- Reminds user to backup before loading

## Output Feature Class Fields

| Field Name | Type | Description |
|------------|------|-------------|
| **WETLAND** | TEXT | Canadian Wetland Classification (preserved from existing or assigned) |
| **Original_Code** | TEXT | NSTDB feat_code (e.g., 'WASW40', 'WALK40') - **PRESERVED** |
| **IS_NEW** | SHORT | 0=Existing, 1=New wetland |
| **Update_Status** | TEXT | "Existing" or "New" (text version) |
| **Update_Date** | DATE | Timestamp of update |
| **Source_OBJECTID** | LONG | Original wetland OBJECTID (NULL for new) |
| feat_code | TEXT | NSTDB feature code (same as Original_Code) |
| feat_desc | TEXT | NSTDB feature description |
| SHAPE | GEOMETRY | Updated geometry from NSTDB |

## Workflow

### Current Process:
1. ✅ Read existing wetlands from SDE
2. ✅ Read new NSTDB boundaries
3. ✅ Spatial join to match existing wetlands
4. ✅ Preserve WETLAND classifications for matched features
5. ✅ Assign classifications to new features based on feat_code
6. ✅ Flag each feature as new or existing (IS_NEW)
7. ✅ Output to **local scratch.gdb** (NOT SDE)
8. ✅ Generate lookup table showing feat_code → WETLAND mapping

### Next Steps (Manual):
1. Review output feature class for QA
2. Validate new wetlands (IS_NEW = 1)
3. Check any "Needs Review" classifications
4. Backup production SDE feature class
5. Truncate production table
6. Append local feature class to production

## Key Preservation Points

### ✅ Maintained:
- **All feat_codes** preserved in `Original_Code` field
- **Existing WETLAND classifications** transferred via spatial join
- **Traceability** via Source_OBJECTID field
- **Lookup table** for feat_code → WETLAND mapping

### ✅ New Features:
- Clear **IS_NEW flag** for filtering
- Ready for **truncate/load** workflow
- Enhanced **documentation** and **QA instructions**

## Query Examples

```python
# Find all new wetlands
arcpy.Select_analysis(
    "Wetlands_Updated",
    "New_Wetlands_Only",
    "IS_NEW = 1"
)

# Find existing wetlands with updated boundaries
arcpy.Select_analysis(
    "Wetlands_Updated",
    "Existing_Wetlands_Only",
    "IS_NEW = 0"
)

# Find specific feat_code
arcpy.Select_analysis(
    "Wetlands_Updated",
    "Swamps_Only",
    "Original_Code = 'WASW40'"
)

# Find features needing review
arcpy.Select_analysis(
    "Wetlands_Updated",
    "Needs_Review",
    "WETLAND = 'Needs Review'"
)
```

## Notes

- The script outputs to `SCRATCH_GDB` (local geodatabase)
- Does **NOT** modify the SDE feature class directly
- Includes both `update_wetland_boundaries.py` and `update_wetland_boundaries_JAN28.py` - only the first has been updated
- Consider updating or removing the JAN28 version to avoid confusion
