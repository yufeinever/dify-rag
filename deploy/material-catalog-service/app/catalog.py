from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .models import AssetRecord, now_iso, recommend_preprocessing, relative_to_root


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS material_assets (
    path TEXT PRIMARY KEY,
    relative_path TEXT NOT NULL,
    root TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    sha256 TEXT,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_changed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_material_assets_status ON material_assets(status);
CREATE INDEX IF NOT EXISTS idx_material_assets_extension ON material_assets(extension);
CREATE INDEX IF NOT EXISTS idx_material_assets_fingerprint ON material_assets(fingerprint);
"""


class MaterialCatalog:
    """Incremental file catalog for the Dify material volume.

    The catalog writes only its own SQLite file. Source files are opened read-only and never modified. A file version is
    incremented when size, mtime, or content hash changes.
    """

    app_root: Path
    db_path: Path
    max_hash_bytes: int
    max_scan_files: int

    def __init__(self, app_root: Path, db_path: Path, max_hash_bytes: int, max_scan_files: int) -> None:
        self.app_root = app_root.resolve()
        self.db_path = db_path
        self.max_hash_bytes = max_hash_bytes
        self.max_scan_files = max_scan_files
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def resolve_roots(self, root_names: Iterable[str]) -> list[tuple[str, Path]]:
        resolved: list[tuple[str, Path]] = []
        for root_name in root_names:
            candidate = (self.app_root / root_name).resolve()
            if candidate != self.app_root and self.app_root not in candidate.parents:
                raise ValueError(f"scan root escapes app root: {root_name}")
            if candidate.exists():
                resolved.append((root_name, candidate))
        return resolved

    def sync(self, root_names: Iterable[str]) -> dict[str, object]:
        seen: set[str] = set()
        scanned = 0
        inserted = 0
        modified = 0
        unchanged = 0
        skipped = 0
        now = now_iso()
        roots = self.resolve_roots(root_names)

        with self._connect() as conn:
            existing = {row["path"]: row for row in conn.execute("SELECT * FROM material_assets")}
            for root_name, root_path in roots:
                for path in self._iter_files(root_path):
                    if scanned >= self.max_scan_files:
                        skipped += 1
                        continue
                    scanned += 1
                    try:
                        record = self._record_for_path(path, root_name, now)
                    except OSError:
                        skipped += 1
                        continue
                    seen.add(record["path"])
                    old = existing.get(record["path"])
                    if old is None:
                        self._upsert(conn, record)
                        inserted += 1
                        continue
                    version = int(old["version"])
                    changed = (
                        int(old["size"]) != record["size"]
                        or float(old["mtime"]) != record["mtime"]
                        or old["fingerprint"] != record["fingerprint"]
                    )
                    record["first_seen_at"] = old["first_seen_at"]
                    if changed:
                        record["status"] = "modified"
                        record["version"] = version + 1
                        record["last_changed_at"] = now
                        modified += 1
                    else:
                        record["status"] = "present"
                        record["version"] = version
                        record["last_changed_at"] = old["last_changed_at"]
                        unchanged += 1
                    self._upsert(conn, record)

            missing = 0
            for path, old in existing.items():
                if path not in seen and old["status"] != "missing":
                    conn.execute(
                        "UPDATE material_assets SET status = ?, last_seen_at = ? WHERE path = ?",
                        ("missing", now, path),
                    )
                    missing += 1

        return {
            "status": "ok",
            "roots": [name for name, _ in roots],
            "scanned": scanned,
            "inserted": inserted,
            "modified": modified,
            "unchanged": unchanged,
            "missing": missing,
            "skipped": skipped,
            "synced_at": now,
        }

    def roots_summary(self, root_names: Iterable[str]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for root_name, root_path in self.resolve_roots(root_names):
            files = 0
            total_size = 0
            for path in self._iter_files(root_path):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                files += 1
                total_size += stat.st_size
            result.append(
                {
                    "root": root_name,
                    "path": str(root_path),
                    "relative_path": relative_to_root(root_path, self.app_root) if root_path != self.app_root else ".",
                    "files": files,
                    "bytes": total_size,
                }
            )
        return result

    def profile(self, limit: int = 100) -> dict[str, object]:
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM material_assets ORDER BY last_seen_at DESC LIMIT ?", (limit,))]
            all_rows = [dict(row) for row in conn.execute("SELECT * FROM material_assets")]
        by_extension = Counter(row["extension"] or "(none)" for row in all_rows if row["status"] != "missing")
        by_status = Counter(row["status"] for row in all_rows)
        bytes_by_extension: dict[str, int] = defaultdict(int)
        fingerprints: dict[str, list[str]] = defaultdict(list)
        recommendations: dict[str, dict[str, object]] = {}
        for row in all_rows:
            if row["status"] == "missing":
                continue
            ext = row["extension"] or "(none)"
            bytes_by_extension[ext] += int(row["size"])
            fingerprints[row["fingerprint"]].append(row["relative_path"])
            recommendations[ext] = recommend_preprocessing(row["extension"], int(row["size"]))
        duplicate_groups = [paths for paths in fingerprints.values() if len(paths) > 1]
        return {
            "total_assets": len(all_rows),
            "active_assets": sum(1 for row in all_rows if row["status"] != "missing"),
            "by_extension": dict(by_extension),
            "bytes_by_extension": dict(bytes_by_extension),
            "by_status": dict(by_status),
            "duplicate_groups": duplicate_groups[:20],
            "preprocessing_recommendations": list(recommendations.values()),
            "recent_assets": rows,
        }

    def changes(self, limit: int = 100) -> dict[str, object]:
        with self._connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM material_assets WHERE status IN ('new', 'modified', 'missing') "
                    "ORDER BY last_changed_at DESC LIMIT ?",
                    (limit,),
                )
            ]
        return {"changes": rows, "count": len(rows)}

    def search_files(self, query: str | None = None, extension: str | None = None, limit: int = 50) -> dict[str, object]:
        limit = min(max(limit, 1), 500)
        clauses = ["status != 'missing'"]
        params: list[object] = []
        if query:
            clauses.append("(name LIKE ? OR relative_path LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            clauses.append("extension = ?")
            params.append(ext.lower())
        params.append(limit)
        sql = "SELECT * FROM material_assets WHERE " + " AND ".join(clauses) + " ORDER BY last_seen_at DESC LIMIT ?"
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, tuple(params))]
        return {"files": rows, "count": len(rows)}

    def _iter_files(self, root_path: Path) -> Iterable[Path]:
        if root_path.is_file():
            yield root_path
            return
        for path in root_path.rglob("*"):
            if path.is_file():
                yield path

    def _record_for_path(self, path: Path, root_name: str, now: str) -> AssetRecord:
        stat = path.stat()
        sha256 = self._sha256(path, stat.st_size)
        fingerprint = sha256 or f"size:{stat.st_size}:mtime:{stat.st_mtime_ns}"
        return {
            "path": str(path.resolve()),
            "relative_path": relative_to_root(path, self.app_root),
            "root": root_name,
            "name": path.name,
            "extension": path.suffix.lower(),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "sha256": sha256,
            "fingerprint": fingerprint,
            "status": "new",
            "version": 1,
            "first_seen_at": now,
            "last_seen_at": now,
            "last_changed_at": now,
        }

    def _sha256(self, path: Path, size: int) -> str | None:
        if size > self.max_hash_bytes:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _upsert(self, conn: sqlite3.Connection, record: AssetRecord) -> None:
        conn.execute(
            """
            INSERT INTO material_assets (
                path, relative_path, root, name, extension, size, mtime, sha256, fingerprint, status, version,
                first_seen_at, last_seen_at, last_changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                relative_path=excluded.relative_path,
                root=excluded.root,
                name=excluded.name,
                extension=excluded.extension,
                size=excluded.size,
                mtime=excluded.mtime,
                sha256=excluded.sha256,
                fingerprint=excluded.fingerprint,
                status=excluded.status,
                version=excluded.version,
                first_seen_at=excluded.first_seen_at,
                last_seen_at=excluded.last_seen_at,
                last_changed_at=excluded.last_changed_at
            """,
            (
                record["path"],
                record["relative_path"],
                record["root"],
                record["name"],
                record["extension"],
                record["size"],
                record["mtime"],
                record.get("sha256"),
                record["fingerprint"],
                record["status"],
                record["version"],
                record["first_seen_at"],
                record["last_seen_at"],
                record["last_changed_at"],
            ),
        )
