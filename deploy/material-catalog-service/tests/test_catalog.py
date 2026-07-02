import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.catalog import MaterialCatalog


class MaterialCatalogTests(unittest.TestCase):
    def test_catalog_sync_tracks_new_modified_and_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_root = tmp_path / "dify-app"
            storage = app_root / "storage"
            storage.mkdir(parents=True)
            material = storage / "brief.txt"
            material.write_text("first", encoding="utf-8")

            catalog = MaterialCatalog(app_root, tmp_path / "catalog.sqlite", max_hash_bytes=1024 * 1024, max_scan_files=100)
            first = catalog.sync(["storage"])
            self.assertEqual(first["inserted"], 1)
            profile = catalog.profile()
            self.assertEqual(profile["by_extension"], {".txt": 1})

            material.write_text("second", encoding="utf-8")
            second = catalog.sync(["storage"])
            self.assertEqual(second["modified"], 1)
            changes = catalog.changes()
            self.assertEqual(changes["changes"][0]["version"], 2)

            material.unlink()
            third = catalog.sync(["storage"])
            self.assertEqual(third["missing"], 1)

    def test_catalog_rejects_roots_outside_app_root(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_root = tmp_path / "dify-app"
            app_root.mkdir()
            catalog = MaterialCatalog(app_root, tmp_path / "catalog.sqlite", max_hash_bytes=1024, max_scan_files=100)

            with self.assertRaisesRegex(ValueError, "escapes app root"):
                catalog.sync(["../outside"])


if __name__ == "__main__":
    unittest.main()
