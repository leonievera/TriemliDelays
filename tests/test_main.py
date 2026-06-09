from datetime import datetime, timezone
import unittest

from cleaning import clean_stationboard
from reporting import calculate_report


class CleanStationboardTests(unittest.TestCase):
    def test_cleans_valid_tram_14_rows_and_defaults_missing_delay(self):
        payload = {
            "stop": {"id": "8503610", "name": "Zürich, Triemli"},
            "connections": [
                {
                    "time": "2026-06-08 09:13:00",
                    "type": "tram",
                    "line": "14",
                    "*Z": "001234",
                    "terminal": {"id": "8587348", "name": "Zürich, Bahnhofplatz/HB"},
                }
            ],
        }

        observations = clean_stationboard(
            payload,
            snapshot_time=datetime(2026, 6, 8, 7, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].delay_minutes, 0)
        self.assertFalse(observations[0].delayed)
        self.assertEqual(observations[0].run_id, "001234")

    def test_parses_positive_dep_delay_and_marks_delayed(self):
        payload = {
            "connections": [
                {
                    "time": "2026-06-08 09:13:00",
                    "type": "tram",
                    "line": "14",
                    "*Z": "001234",
                    "dep_delay": "+3",
                }
            ],
        }

        observations = clean_stationboard(payload)

        self.assertEqual(observations[0].delay_minutes, 3)
        self.assertTrue(observations[0].delayed)

    def test_filters_wrong_line_wrong_type_and_missing_required_fields(self):
        payload = {
            "connections": [
                {"time": "2026-06-08 09:13:00", "type": "tram", "line": "13", "*Z": "1"},
                {"time": "2026-06-08 09:13:00", "type": "bus", "line": "14", "*Z": "2"},
                {"type": "tram", "line": "14", "*Z": "3"},
                {"time": "2026-06-08 09:13:00", "type": "tram", "line": "14"},
            ]
        }

        self.assertEqual(clean_stationboard(payload), [])


class DelayReportTests(unittest.TestCase):
    def test_calculates_zero_rows(self):
        report = calculate_report([])

        self.assertEqual(report.observed_departures, 0)
        self.assertEqual(report.delayed_departures, 0)
        self.assertEqual(report.delayed_percentage, 0.0)

    def test_calculates_mixed_delay_percentage(self):
        report = calculate_report([(1, True), (2, False), (3, True), (4, False)])

        self.assertEqual(report.observed_departures, 4)
        self.assertEqual(report.delayed_departures, 2)
        self.assertEqual(report.delayed_percentage, 50.0)

    def test_calculates_no_delays_and_all_delays(self):
        self.assertEqual(calculate_report([(1, False), (2, False)]).delayed_percentage, 0.0)
        self.assertEqual(calculate_report([(1, True), (2, True)]).delayed_percentage, 100.0)


if __name__ == "__main__":
    unittest.main()
