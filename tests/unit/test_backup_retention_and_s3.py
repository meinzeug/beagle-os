"""Unit tests for Plan 16 Testpflicht items:

  - L212: Retention policy enforcement + audit event (prune_old_snapshots)
  - L211: S3 encrypted backup — chunks stored encrypted (AES-256-GCM)
  - L210: Single-file restore — snapshot index + path traversal protection
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make beagle-host/services importable
_SERVICES = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
_CORE = Path(__file__).resolve().parents[2] / "core"
for _p in (_SERVICES, _CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(tmp_path: Path, clock: list[str]):
    """Return BackupService wired to a temp state file with injectable clock."""
    from backup_service import BackupService  # type: ignore[import]

    idx = [0]

    def _now() -> str:
        v = clock[idx[0] % len(clock)]
        idx[0] += 1
        return v

    return BackupService(state_file=tmp_path / "state.json", utcnow=_now)


def _inject_job(svc, *, job_id: str, scope_type: str, scope_id: str,
                created_at: str, archive: str = "/tmp/fake.tar.gz") -> None:
    """Directly inject a success job into BackupService state for testing."""
    state = svc._load()
    state["jobs"].append({
        "job_id": job_id,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "status": "success",
        "archive": archive,
        "created_at": created_at,
        "started_at": created_at,
        "finished_at": created_at,
    })
    svc._save(state)


# ---------------------------------------------------------------------------
# Retention / prune_old_snapshots  (Plan 16 L212)
# ---------------------------------------------------------------------------

class TestRetentionPruneOldSnapshots(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self._tmp = Path(self._tmpdir)

    def test_old_job_is_pruned_and_returned(self):
        """Jobs older than retention_days are pruned and returned."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        # Create policy with 7-day retention
        svc.update_pool_policy("pool1", {"enabled": True, "retention_days": 7, "target_type": "local", "target_path": str(self._tmp / "backups")})

        # Inject a job that is 8 days old
        _inject_job(svc, job_id="old-job-001", scope_type="pool", scope_id="pool1",
                    created_at="2026-05-02T12:00:00Z")

        with patch.object(svc, "_get_target") as mock_target:
            mock_target.return_value = MagicMock()
            pruned = svc.prune_old_snapshots(scope_type="pool", scope_id="pool1")

        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["job_id"], "old-job-001")

    def test_recent_job_is_kept(self):
        """Jobs within retention_days are NOT pruned."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        svc.update_pool_policy("pool2", {"enabled": True, "retention_days": 7, "target_type": "local", "target_path": str(self._tmp / "backups")})

        # Inject a job that is only 2 days old (within 7-day retention)
        _inject_job(svc, job_id="fresh-job-001", scope_type="pool", scope_id="pool2",
                    created_at="2026-05-08T12:00:00Z")

        with patch.object(svc, "_get_target") as mock_target:
            mock_target.return_value = MagicMock()
            pruned = svc.prune_old_snapshots(scope_type="pool", scope_id="pool2")

        self.assertEqual(pruned, [])

        # Job still in list
        remaining = svc.list_jobs(scope_type="pool", scope_id="pool2")
        self.assertEqual(len(remaining), 1)

    def test_pruned_job_removed_from_state(self):
        """Pruned job is removed from state so it no longer appears in list_jobs."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        svc.update_pool_policy("pool3", {"enabled": True, "retention_days": 3, "target_type": "local", "target_path": str(self._tmp / "backups")})

        _inject_job(svc, job_id="expired-job", scope_type="pool", scope_id="pool3",
                    created_at="2026-05-05T12:00:00Z")  # 5 days old, >3 day retention

        with patch.object(svc, "_get_target") as mock_target:
            mock_target.return_value = MagicMock()
            pruned = svc.prune_old_snapshots()

        self.assertEqual(len(pruned), 1)
        remaining = svc.list_jobs(scope_type="pool", scope_id="pool3")
        self.assertEqual(remaining, [])

    def test_delete_snapshot_called_on_target(self):
        """prune_old_snapshots calls delete_snapshot on the target for each pruned job."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        svc.update_pool_policy("pool4", {"enabled": True, "retention_days": 1, "target_type": "local", "target_path": str(self._tmp / "backups")})

        _inject_job(svc, job_id="to-delete", scope_type="pool", scope_id="pool4",
                    created_at="2026-05-01T00:00:00Z", archive="beagle-backup-pool-pool4-2026.tar.gz")

        mock_tgt = MagicMock()
        with patch.object(svc, "_get_target", return_value=mock_tgt):
            pruned = svc.prune_old_snapshots()

        mock_tgt.delete_snapshot.assert_called_once_with("beagle-backup-pool-pool4-2026.tar.gz")
        self.assertEqual(len(pruned), 1)

    def test_delete_error_does_not_block_pruning(self):
        """If delete_snapshot raises, the job is still removed from state (best-effort)."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        svc.update_pool_policy("pool5", {"enabled": True, "retention_days": 1, "target_type": "local", "target_path": str(self._tmp / "backups")})

        _inject_job(svc, job_id="fail-del", scope_type="pool", scope_id="pool5",
                    created_at="2026-05-01T00:00:00Z")

        mock_tgt = MagicMock()
        mock_tgt.delete_snapshot.side_effect = OSError("disk gone")
        with patch.object(svc, "_get_target", return_value=mock_tgt):
            pruned = svc.prune_old_snapshots()

        self.assertEqual(len(pruned), 1)
        self.assertEqual(svc.list_jobs(), [])

    def test_failed_job_not_pruned(self):
        """Jobs with status != 'success' are never pruned by retention."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        svc.update_pool_policy("pool6", {"enabled": True, "retention_days": 1, "target_type": "local", "target_path": str(self._tmp / "backups")})

        state = svc._load()
        state["jobs"].append({
            "job_id": "error-job",
            "scope_type": "pool",
            "scope_id": "pool6",
            "status": "error",
            "created_at": "2026-01-01T00:00:00Z",
        })
        svc._save(state)

        with patch.object(svc, "_get_target") as mock_target:
            mock_target.return_value = MagicMock()
            pruned = svc.prune_old_snapshots()

        self.assertEqual(pruned, [])
        self.assertEqual(len(svc.list_jobs()), 1)  # error job stays

    def test_scope_filter_preserves_other_scopes(self):
        """Pruning pool1 does not affect pool2 jobs even if pool2 jobs are old."""
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])

        for pid in ("pool-a", "pool-b"):
            svc.update_pool_policy(pid, {"enabled": True, "retention_days": 1, "target_type": "local", "target_path": str(self._tmp)})

        _inject_job(svc, job_id="j-a", scope_type="pool", scope_id="pool-a", created_at="2026-01-01T00:00:00Z")
        _inject_job(svc, job_id="j-b", scope_type="pool", scope_id="pool-b", created_at="2026-01-01T00:00:00Z")

        with patch.object(svc, "_get_target") as mock_tgt:
            mock_tgt.return_value = MagicMock()
            pruned = svc.prune_old_snapshots(scope_type="pool", scope_id="pool-a")

        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["job_id"], "j-a")
        # pool-b job is still there
        remaining = svc.list_jobs(scope_type="pool", scope_id="pool-b")
        self.assertEqual(len(remaining), 1)


# ---------------------------------------------------------------------------
# S3 encrypted backup  (Plan 16 L211)
# ---------------------------------------------------------------------------

class TestS3EncryptedBackup(unittest.TestCase):
    """Test AES-256-GCM client-side encryption in S3BackupTarget.

    boto3 is mocked via patch — no real AWS/Minio access required.
    """

    _VALID_KEY = "a" * 64  # 32 bytes = 256 bits, hex-encoded as 64 chars

    def _make_target(self, enc_key: str | None = None):
        """Construct S3BackupTarget with mocked boto3.client."""
        from core.backup_targets.s3 import S3BackupTarget  # type: ignore[import]

        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            tgt = S3BackupTarget(bucket="test-bucket", encryption_key=enc_key)
        # Replace internal client after construction for fine-grained assertions
        tgt._s3 = MagicMock()
        return tgt

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypting and then decrypting returns original plaintext."""
        tgt = self._make_target(enc_key=self._VALID_KEY)
        plaintext = b"Hello, Beagle backup data!"
        ciphertext = tgt._encrypt(plaintext)
        self.assertNotEqual(ciphertext, plaintext)
        self.assertEqual(tgt._decrypt(ciphertext), plaintext)

    def test_encrypted_data_differs_from_plaintext(self):
        """Encrypted output does not contain the plaintext literally."""
        tgt = self._make_target(enc_key=self._VALID_KEY)
        plaintext = b"secret-vm-disk-data-content"
        ciphertext = tgt._encrypt(plaintext)
        self.assertNotIn(plaintext, ciphertext)

    def test_write_chunk_stores_encrypted_bytes(self):
        """write_chunk uploads AES-GCM-encrypted bytes, not plaintext."""
        tgt = self._make_target(enc_key=self._VALID_KEY)
        plaintext = b"critical backup payload"
        tgt.write_chunk("chunk-001", plaintext)

        put_args = tgt._s3.put_object.call_args
        body: bytes = put_args.kwargs.get("Body") or put_args[1].get("Body") or put_args[0][2]
        self.assertNotEqual(body, plaintext, "Plaintext must NOT be stored in S3")
        # Should be decryptable
        self.assertEqual(tgt._decrypt(body), plaintext)

    def test_read_chunk_decrypts_on_read(self):
        """read_chunk decrypts S3 bytes before returning them."""
        tgt = self._make_target(enc_key=self._VALID_KEY)
        plaintext = b"backup content for VM 101"
        ciphertext = tgt._encrypt(plaintext)

        mock_body = MagicMock()
        mock_body.read.return_value = ciphertext
        tgt._s3.get_object.return_value = {"Body": mock_body}

        result = tgt.read_chunk("chunk-001")
        self.assertEqual(result, plaintext)

    def test_different_encryptions_produce_different_ciphertext(self):
        """AES-GCM uses random nonce per encryption — two calls produce different ciphertexts."""
        tgt = self._make_target(enc_key=self._VALID_KEY)
        plaintext = b"same data twice"
        ct1 = tgt._encrypt(plaintext)
        ct2 = tgt._encrypt(plaintext)
        self.assertNotEqual(ct1, ct2, "Each encryption must use a fresh random nonce")

    def test_no_encryption_key_stores_plaintext(self):
        """Without encryption_key, data is written as-is (unencrypted)."""
        tgt = self._make_target(enc_key=None)
        plaintext = b"unencrypted backup data"
        stored = tgt._encrypt(plaintext)
        self.assertEqual(stored, plaintext)

    def test_invalid_chunk_id_rejected(self):
        """_safe_id rejects chunk_ids with path traversal or slashes."""
        from core.backup_targets.s3 import _safe_id  # type: ignore[import]
        with self.assertRaises(ValueError):
            _safe_id("../etc/passwd")
        with self.assertRaises(ValueError):
            _safe_id("folder/file")
        with self.assertRaises(ValueError):
            _safe_id(".hidden")

    def test_wrong_length_encryption_key_rejected(self):
        """encryption_key must be exactly 64 hex chars (32 bytes)."""
        from core.backup_targets.s3 import S3BackupTarget  # type: ignore[import]

        with patch("boto3.client", return_value=MagicMock()):
            with self.assertRaises(ValueError):
                S3BackupTarget(bucket="b", encryption_key="a" * 32)  # 16 bytes, not 32


# ---------------------------------------------------------------------------
# Single-file restore (Plan 16 L210)
# ---------------------------------------------------------------------------

class TestSingleFileRestore(unittest.TestCase):
    def setUp(self):
        import subprocess
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self._tmp = Path(self._tmpdir)

        # Build a real tar.gz archive with two test files
        archive_dir = self._tmp / "arc_contents"
        archive_dir.mkdir()
        (archive_dir / "hello.txt").write_text("hello from beagle\n")
        (archive_dir / "data.json").write_text('{"key": "value"}\n')

        self._archive = str(self._tmp / "test-backup.tar.gz")
        subprocess.run(
            ["tar", "-czf", self._archive, "-C", str(archive_dir), "hello.txt", "data.json"],
            check=True,
        )

    def _make_service_with_job(self):
        svc = _make_service(self._tmp, ["2026-05-10T00:00:00Z"])
        svc.update_pool_policy("p1", {"target_type": "local", "target_path": str(self._tmp / "backups")})
        _inject_job(svc, job_id="job-sfr-001", scope_type="pool", scope_id="p1",
                    created_at="2026-05-10T00:00:00Z", archive=self._archive)
        return svc

    def test_list_snapshot_files_returns_files(self):
        """list_snapshot_files returns all files in the archive."""
        svc = self._make_service_with_job()
        result = svc.list_snapshot_files("job-sfr-001")
        self.assertTrue(result["ok"])
        paths = [f["path"] for f in result["files"]]
        self.assertTrue(any("hello.txt" in p for p in paths))
        self.assertTrue(any("data.json" in p for p in paths))

    def test_read_snapshot_file_returns_bytes(self):
        """read_snapshot_file extracts a single file's contents."""
        svc = self._make_service_with_job()
        data = svc.read_snapshot_file("job-sfr-001", "hello.txt")
        self.assertIn(b"hello from beagle", data)

    def test_read_snapshot_file_path_traversal_rejected(self):
        """read_snapshot_file rejects paths with .. or leading /."""
        svc = self._make_service_with_job()
        with self.assertRaises(ValueError):
            svc.read_snapshot_file("job-sfr-001", "../etc/passwd")
        with self.assertRaises(ValueError):
            svc.read_snapshot_file("job-sfr-001", "/etc/passwd")

    def test_list_snapshot_files_missing_job_raises(self):
        """list_snapshot_files raises ValueError for unknown job_id."""
        svc = _make_service(self._tmp / "empty", ["2026-05-10T00:00:00Z"])
        with self.assertRaises(ValueError):
            svc.list_snapshot_files("no-such-job")

    def test_read_nonexistent_file_in_archive_raises(self):
        """read_snapshot_file raises FileNotFoundError for missing file in archive."""
        svc = self._make_service_with_job()
        with self.assertRaises(FileNotFoundError):
            svc.read_snapshot_file("job-sfr-001", "does-not-exist.txt")


if __name__ == "__main__":
    unittest.main()
