# Kerala Schools → Supabase Import

Your original CSV had 1,149 columns (one per staff-position type) because the
source export put every "job title + slot number" in its own column. That's
unworkable in Postgres, so it's been split into 4 normalized tables.

## Files
- `schema.sql` — run this first in the Supabase SQL editor to create the tables.
- `schools.csv` — 12,910 rows, core school info (1 row per school).
- `school_contacts.csv` — 14,899 rows, section emails/phones (General/HS/HSE/LP/UP).
- `school_facilities.csv` — 12,910 rows, the 51 numbered facility fields (1 row per school).
- `school_staff_positions.csv` — 53,748 rows. Long format: school_code, position_title,
  sanctioned_posts. (Note: the original per-position columns didn't actually contain staff
  names — the cell value just repeated the column header, marking that a post exists. So
  this table records *how many posts of each title are sanctioned* per school, not names.)

## Import steps (Supabase dashboard)
1. SQL Editor → paste & run `schema.sql`.
2. Table Editor → for each table, use "Insert → Import data from CSV" and upload the
   matching CSV (schools.csv → schools, etc.). Import in this order: schools first
   (everything else has a foreign key to it), then the other three in any order.
3. Spot check: `select count(*) from schools;` should return 12910.

## Why this structure
- `schools` — one clean row per school, easy to query/filter/map.
- `school_contacts` — was 10 sparse columns, now rows; add a new section type without
  a schema change.
- `school_facilities` — kept as columns since these are genuinely 1-per-school
  attributes (not repeating groups).
- `school_staff_positions` — was ~1,064 sparse columns; now a tall table you can query like:
  `select position_title, sum(sanctioned_posts) from school_staff_positions
   where school_code = 25802 group by position_title;`
  or aggregate across the whole state, by district (join schools), etc.

## Note
One row in the original CSV was missing a `School Code` entirely and was dropped
across all four output tables (it had no name either, looked like a blank/corrupt row).
