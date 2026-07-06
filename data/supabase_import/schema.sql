-- ============================================================
-- Kerala Schools — Supabase schema
-- Normalized from a single 1,149-column CSV into 4 tables.
-- ============================================================

create table schools (
  school_code             bigint primary key,
  udise_code              bigint,
  hss_code                text,
  vhse_code               text,
  name                    text not null,
  type                    text,            -- Government / Aided / Unaided Recognised
  level                   text,            -- e.g. '1 - 4', '8 - 12'
  established_year        int,
  address                 text,
  pin_code                int,
  district                text,
  sub_district            text,
  education_district      text,
  assembly_constituency   text,
  parliament_constituency text,
  latitude                double precision,
  longitude               double precision,
  is_coastal_area         boolean,
  is_hilly_area           boolean,
  principal_name          text,
  head_master_name        text,
  description             text,
  source_url              text,
  hse_start_year          int
);

create index idx_schools_district on schools (district);
create index idx_schools_type on schools (type);
create index idx_schools_geo on schools (latitude, longitude);

-- ------------------------------------------------------------
create table school_contacts (
  id          bigserial primary key,
  school_code bigint references schools(school_code) on delete cascade,
  section     text,   -- General / HS / HSE / LP / UP
  email       text,
  phone       text
);

create index idx_contacts_school on school_contacts (school_code);

-- ------------------------------------------------------------
create table school_facilities (
  school_code                                    bigint primary key references schools(school_code) on delete cascade,
  total_area_acre                                text,
  survey_number_s                                text,
  land_obtained_for_establishing_school           text,
  land_protected_by                              text,
  building_type                                  text,
  building_plinth_area                           text,
  building_ownership                             text,
  library                                        text,
  electrification                                text,
  solar_power                                    text,
  drinking_water                                 text,
  net_connectivity                               text,
  total_class_room                               int,
  multi_media_room                               text,
  total_smart_class_room                         int,
  little_kites                                   text,
  total_staff_room                               int,
  computer_lab                                   text,
  science_lab                                    text,
  total_no_of_computers_available_in_the_school  int,
  total_no_of_printers_available_in_the_school   int,
  first_aid_room                                 text,
  public_addressing_system                       text,
  kitchen                                        text,
  cctv                                           text,
  store_book_stationary                          text,
  tv_hall                                        text,
  canteen                                        text,
  rainwater_harvesting                           text,
  play_ground                                    text,
  waste_management_system                        text,
  autism_park                                    text,
  dining_hall                                    text,
  auditorium                                     text,
  indoor_stadium                                 text,
  students_police                                text,
  music_class_room                               text,
  activities                                     text,
  agricultural_activity                          text,
  toilet                                         text,
  she_toilet                                     text,
  no_of_toilets_for_boys                         int,
  no_of_toilets_for_girls                        int,
  no_of_urinals_for_boys                         int,
  no_of_urinals_for_girls                        int,
  parking_space                                  text,
  garden                                         text,
  transportation                                 text,
  hostel_facility                                text,
  bio_gas                                        text,
  incinerator_facility                           text
);

-- ------------------------------------------------------------
-- 517 distinct sanctioned-post titles, long format instead of
-- one column per title. sanctioned_posts = highest slot number
-- seen for that title at that school (i.e. how many posts of
-- that type are sanctioned).
create table school_staff_positions (
  id               bigserial primary key,
  school_code      bigint references schools(school_code) on delete cascade,
  position_title   text not null,
  sanctioned_posts int not null default 1
);

create index idx_staff_school on school_staff_positions (school_code);
create index idx_staff_title on school_staff_positions (position_title);

-- ------------------------------------------------------------
-- Optional: enable RLS once you decide on access rules, e.g.:
-- alter table schools enable row level security;
-- create policy "public read" on schools for select using (true);
