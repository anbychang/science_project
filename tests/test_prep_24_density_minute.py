"""Check MSIS weather and centered-minute density summaries."""

import math
import sqlite3
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.calculation.density.calc_msis_p2_4 import (
    ap_drivers,
    calculate_msis_density,
    solar_drivers,
)
from satellite_orbit.phase2.prep_24_density_minute import (
    ALGORITHM_VERSION,
    DensityContext,
    create_tables,
    minute_rows,
    paired_day,
    store_coverage,
)


class MsisDriverTest(unittest.TestCase):
    """Input: synthetic weather records. Output: causal MSIS driver decisions."""

    def test_previous_day_flux_and_trailing_observed_mean(self):
        """Input: 81 observed days before sample. Output: previous and trailing flux."""
        day = date(2024, 5, 10)
        flux = {day - timedelta(days=offset): float(100 + offset)
                for offset in range(1, 82)}
        drivers = solar_drivers(day, flux)
        self.assertEqual((drivers["f107_day_utc"], drivers["f107_sfu"],
                          drivers["f107a_sfu"], drivers["f107a_observed_days"]),
                         ("2024-05-09", 101.0, 141.0, 81))

    def test_missing_previous_day_cannot_use_current_day_flux(self):
        """Input: current flux but missing previous day. Output: no model drivers."""
        day = date(2024, 5, 10)
        flux = {day - timedelta(days=offset): 100.0
                for offset in range(2, 83)}
        flux[day] = 200.0
        self.assertIsNone(solar_drivers(day, flux))

    def test_missing_one_of_81_days_rejects_solar_drivers(self):
        """Input: 80 of 81 trailing days. Output: no incomplete solar mean."""
        day = date(2024, 5, 10)
        flux = {day - timedelta(days=offset): 100.0 for offset in range(1, 81)}
        self.assertIsNone(solar_drivers(day, flux))

    def test_ap_uses_last_completed_slot(self):
        """Input: 12:01 UTC sample. Output: 09:00-12:00 ap, not 12:00-15:00."""
        sample_time = datetime(2024, 5, 10, 12, 1, tzinfo=timezone.utc)
        first = datetime(2024, 5, 7, tzinfo=timezone.utc)
        slots = {first + timedelta(hours=3 * index): float(index)
                 for index in range(32)}
        drivers = ap_drivers(sample_time, slots)
        self.assertEqual(drivers["ap_values"][1], slots[datetime(2024, 5, 10, 9,
                                                                     tzinfo=timezone.utc)])
        self.assertEqual(drivers["ap_last_slot_end_time_us"],
                         int(datetime(2024, 5, 10, 12, tzinfo=timezone.utc).timestamp()
                             * 1_000_000))

    def test_msis_returns_one_density_per_aligned_sample(self):
        """Input: one positioned sample and complete drivers. Output: positive SI density."""
        sample = {"time_us": 1691041110000000, "longitude_deg": 126.0,
                  "latitude_deg": 12.0, "altitude_m": 485_000.0}
        drivers = {"f107_sfu": 150.0, "f107a_sfu": 150.0, "ap_values": [4.0] * 7}
        result = calculate_msis_density([sample], [drivers])
        self.assertTrue(math.isfinite(result[0]) and result[0] > 0)


class DensityMinuteTest(unittest.TestCase):
    """Input: positioned paired samples. Output: centered minute summaries."""

    def test_minute_ratio_uses_ratio_of_means(self):
        """Input: two paired samples. Output: ln(mean L2 / mean MSIS)."""
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE storm_minute_feature_v3 "
                       "(storm_id TEXT,source_time_us INTEGER,orbit_id INTEGER)")
            db.executemany("INSERT INTO storm_minute_feature_v3 VALUES ('S',?,1)",
                           [(60_000_000,), (120_000_000,)])
            totals = {("S", 60_000_000): {
                "l2_count": 2, "pair_count": 2, "orbitmean_count": 2,
                "l2_sum": 12.0, "msis_sum": 8.0, "orbitmean_sum": 22.0,
            }}
            create_tables(db)
            db.executemany("INSERT INTO storm_density_1min_v3 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           minute_rows(db, totals))
            rows = db.execute(
                "SELECT rho_l2_kg_m3,rho_msis_kg_m3,rho_l2_orbitmean_kg_m3,"
                "log_ratio_obs FROM storm_density_1min_v3 ORDER BY source_time_us"
            ).fetchall()
        self.assertEqual(rows[0], (6.0, 4.0, 11.0, math.log(1.5)))
        self.assertEqual(rows[1], (None, None, None, None))

    def test_native_samples_map_to_centered_minute(self):
        """Input: samples at 00:30 and 01:00. Output: both in the 01:00 row."""
        samples = [{"time_us": time_us, "rho_l2_kg_m3": density,
                    "rho_l2_orbitmean_kg_m3": orbitmean}
                   for time_us, density, orbitmean in
                   [(30_000_000, 4.0, 10.0), (60_000_000, 8.0, 12.0)]]
        orbit = {"storm_id": "S", "orbit_id": 1, "orbit_end_time_us": 120_000_000}
        context = DensityContext([orbit], [0], {("S", 60_000_000)}, {})
        with patch("satellite_orbit.phase2.prep_24_density_minute.load_dnsapod",
                   return_value={"raw_count": 2, "samples": samples}), patch(
                       "satellite_orbit.phase2.prep_24_density_minute.sample_drivers",
                       return_value={"ap_values": [4.0] * 7}), patch(
                       "satellite_orbit.phase2.prep_24_density_minute.calculate_msis_density",
                       return_value=[2.0, 6.0]):
            result = paired_day(Path("unused.ZIP"), context)
        self.assertEqual(result["minutes"][("S", 60_000_000)]["pair_count"], 2)
        self.assertEqual(result["minutes"][("S", 60_000_000)]["orbitmean_sum"], 22.0)


class CoverageTest(unittest.TestCase):
    """Input: native sample counts. Output: 80% orbit/event decisions."""

    def test_four_of_five_valid_orbits_pass_event_threshold(self):
        """Input: four qualified orbits out of five. Output: used event."""
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE storm_event_full_orbit_v3 "
                       "(storm_id TEXT,t0_time_us INTEGER,symh_min_nt INTEGER,"
                       "compound INTEGER,n_orbits INTEGER)")
            db.execute("INSERT INTO storm_event_full_orbit_v3 VALUES ('S',0,-110,0,5)")
            db.execute("CREATE TABLE storm_event_orbit_v3 "
                       "(storm_id TEXT,orbit_id INTEGER,orbit_start_time_us INTEGER,"
                       "orbit_end_time_us INTEGER)")
            db.executemany("INSERT INTO storm_event_orbit_v3 VALUES ('S',?,?,?)",
                           [(index, index * 300_000_000, (index + 1) * 300_000_000)
                            for index in range(5)])
            create_tables(db)
            totals = {("S", index): {"l2_count": 8, "pair_count": 8}
                      for index in range(4)}
            store_coverage(db, totals)
            result = db.execute("SELECT n_valid_orbits,status FROM storm_catalog_v3").fetchone()
        self.assertEqual(result, (4, "used"))


if __name__ == "__main__":
    unittest.main()
