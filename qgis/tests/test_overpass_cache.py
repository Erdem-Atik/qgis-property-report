"""Unit tests for the Overpass disk cache (no network, no PyQGIS).

Run: docker compose run --rm qgis python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from report import osm, overpass_cache  # noqa: E402

VALID = {"version": 0.6, "osm3s": {"timestamp_osm_base": "2026-11-01T00:00:00Z"},
         "elements": [{"type": "node", "id": 1, "lat": 36.2, "lon": 29.6,
                       "tags": {"amenity": "cafe", "name": "Test Cafe"}}]}


def fake_response(status=200, payload=None, text=None):
    r = mock.Mock()
    r.status_code = status
    r.text = text if text is not None else json.dumps(payload)
    if payload is None:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = payload
    return r


class OverpassCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"OVERPASS_CACHE_DIR": self.tmp.name})
        self.env.start()
        self.query = osm.build_overpass_query(36.2018, 29.6377)
        # Never sleep between retries in tests.
        self.sleep = mock.patch.object(osm.time, "sleep")
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.env.stop()
        self.tmp.cleanup()

    def _post(self, *responses):
        session = mock.Mock()
        session.post.side_effect = list(responses)
        return mock.patch.object(osm, "_session", return_value=session), session

    def test_key_is_sha256_of_query(self):
        path = overpass_cache.cache_path(self.query)
        self.assertEqual(os.path.dirname(path), self.tmp.name)
        self.assertRegex(os.path.basename(path), r"^[0-9a-f]{64}\.json$")

    def test_miss_fetches_and_stores(self):
        patcher, session = self._post(fake_response(200, VALID))
        with patcher:
            data, from_cache = osm.fetch_overpass(self.query)
        self.assertFalse(from_cache)
        self.assertEqual(data, VALID)
        self.assertEqual(session.post.call_count, 1)
        self.assertTrue(os.path.isfile(overpass_cache.cache_path(self.query)))
        # no temp files left behind
        self.assertEqual(os.listdir(self.tmp.name),
                         [os.path.basename(overpass_cache.cache_path(self.query))])

    def test_hit_does_not_touch_network(self):
        overpass_cache.save(self.query, VALID)
        session = mock.Mock()
        session.post.side_effect = AssertionError("network must not be used on a cache hit")
        with mock.patch.object(osm, "_session", return_value=session), \
                self.assertLogs("report.overpass_cache", "INFO") as logs:
            data, from_cache = osm.fetch_overpass(self.query)
        self.assertTrue(from_cache)
        self.assertEqual(data, VALID)
        self.assertTrue(any("cache hit" in m for m in logs.output))

    def test_hit_is_independent_of_mirror(self):
        # Mirror A answers and fills the cache ...
        patcher, _ = self._post(requests.ConnectionError(), fake_response(200, VALID))
        with patcher:
            osm.fetch_overpass(self.query)
        # ... a later run with a different endpoint list still hits the same file.
        with mock.patch.object(osm, "OVERPASS_URLS", ["https://other.example/api/interpreter"]):
            self.assertIsNotNone(overpass_cache.load(self.query))

    def test_bad_responses_are_never_cached(self):
        bad = [
            fake_response(406, text="Not Acceptable"),
            fake_response(200, payload=None, text=""),            # empty body
            fake_response(200, payload=None, text="<html>"),      # broken / non-JSON
            fake_response(200, {"version": 0.6}),                  # no 'elements'
            requests.Timeout(),
        ]
        for resp in bad:
            with self.subTest(resp=resp):
                with mock.patch.object(osm, "OVERPASS_URLS", ["https://a.example/api"]):
                    patcher, _ = self._post(*([resp] * 3))
                    with patcher, self.assertRaises(osm.OsmError):
                        osm.fetch_overpass(self.query)
                self.assertFalse(os.path.exists(overpass_cache.cache_path(self.query)))

    def test_save_rejects_invalid_data(self):
        with self.assertRaises(ValueError):
            overpass_cache.save(self.query, {"remark": "no elements"})
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_corrupt_cache_file_is_a_miss(self):
        os.makedirs(self.tmp.name, exist_ok=True)
        with open(overpass_cache.cache_path(self.query), "w") as fh:
            fh.write('{"elements": [')  # truncated
        self.assertIsNone(overpass_cache.load(self.query))


if __name__ == "__main__":
    unittest.main()
