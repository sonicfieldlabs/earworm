"""Object reads/writes/forgetting stay inside an audit-owned temporary store."""
import hashlib
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

import akousma

from akousma import AkousmataStore, new_akousma


class ObjectBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = AkousmataStore(self.base / "store")
        self.addCleanup(self.store.close)
        self.data = b"temporary object-boundary fixture"
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.uri = f"akousmata://objects/{self.digest}.wav"

    def record(self, uri=None, digest=None):
        record = new_akousma(audio={"asset_id": "fixture", "uri": uri or self.uri,
                             "content_hash": "sha256:" + (digest or self.digest)},
                             originating_app="object-boundary-test")
        self.store.put(record)
        return record

    def test_canonical_missing_and_roundtrip(self):
        expected = self.store.objects_dir / self.digest[:2] / f"{self.digest}.wav"
        self.assertEqual(self.store.resolve_uri(self.uri), expected)
        self.assertFalse(expected.exists())
        self.assertEqual(self.store.put_audio(self.data), self.uri)
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)
        self.assertEqual(self.store.put_audio(self.data), self.uri)
        self.assertEqual(self.store.resolve_uri(self.uri, content_hash="sha256:" + self.digest), expected)
        self.assertEqual(self.store.resolve_uri(self.uri, content_hash=self.digest), expected)

    def test_interrupted_staging_leaves_no_final_object_and_can_retry(self):
        factory = akousma.tempfile.NamedTemporaryFile

        def interrupted_file(*args, **kwargs):
            output = factory(*args, **kwargs)
            write = output.write

            def interrupted_write(data):
                write(data[:3])
                raise OSError("injected interrupted write")

            output.write = interrupted_write
            return output

        with patch.object(akousma.tempfile, "NamedTemporaryFile", interrupted_file):
            with self.assertRaises(OSError):
                self.store.put_audio(self.data)
        self.assertFalse(self.store.resolve_uri(self.uri).exists())
        self.assertEqual(list(self.store.objects_dir.rglob(".audio-*")), [])
        self.assertEqual(self.store.put_audio(self.data), self.uri)

    def test_prepublication_failures_keep_unrelated_files_and_allow_retry(self):
        unrelated = self.store.objects_dir / "keep"
        unrelated.write_bytes(b"unrelated")
        for operation in ("fsync", "link"):
            with self.subTest(operation=operation):
                with patch.object(akousma.os, operation, side_effect=OSError("injected failure")):
                    with self.assertRaises(OSError):
                        self.store.put_audio(self.data)
                self.assertFalse(self.store.resolve_uri(self.uri).exists())
                self.assertEqual(list(self.store.objects_dir.rglob(".audio-*")), [])
                self.assertEqual(unrelated.read_bytes(), b"unrelated")
        self.assertEqual(self.store.put_audio(self.data), self.uri)

    def test_process_exit_during_staging_never_publishes_partial_audio(self):
        script = """
import os, sys, akousma
from pathlib import Path
factory = akousma.tempfile.NamedTemporaryFile
def interrupted(*args, **kwargs):
    output = factory(*args, **kwargs)
    write = output.write
    def partial(data):
        write(data[:3])
        output.flush()
        os._exit(17)
    output.write = partial
    return output
akousma.tempfile.NamedTemporaryFile = interrupted
with akousma.AkousmataStore(Path(sys.argv[1])) as store:
    store.put_audio(bytes.fromhex(sys.argv[2]))
"""
        result = subprocess.run([sys.executable, "-I", "-c", script,
                                 str(self.base / "store"), self.data.hex()], check=False)
        self.assertEqual(result.returncode, 17)
        self.assertFalse(self.store.resolve_uri(self.uri).exists())
        # Abrupt death can leave private staging debris, never a usable final locator.
        self.assertEqual(self.store.put_audio(self.data), self.uri)
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)

    def test_postpublication_sync_failure_keeps_complete_object_and_retry_reuses_it(self):
        fsync = akousma.os.fsync
        calls = 0

        def fail_directory_sync(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected directory sync failure")
            return fsync(fd)

        with patch.object(akousma.os, "fsync", fail_directory_sync):
            with self.assertRaises(OSError):
                self.store.put_audio(self.data)
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)
        self.assertEqual(list(self.store.objects_dir.rglob(".audio-*")), [])
        with patch.object(akousma.os, "link", side_effect=AssertionError("retry must reuse")):
            self.assertEqual(self.store.put_audio(self.data), self.uri)

    def test_concurrent_readers_see_only_complete_published_bytes(self):
        staged = threading.Event()
        release = threading.Event()
        link = akousma.os.link

        def paused_link(*args, **kwargs):
            staged.set()
            if not release.wait(5):
                raise TimeoutError("test writer was not released")
            return link(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            with patch.object(akousma.os, "link", paused_link):
                writer = pool.submit(self.store.put_audio, self.data)
                try:
                    self.assertTrue(staged.wait(5))
                    self.assertFalse(self.store.resolve_uri(self.uri).exists())
                finally:
                    release.set()
                self.assertEqual(writer.result(timeout=5), self.uri)
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)

    def test_concurrent_identical_writers_deduplicate_without_overwriting(self):
        barrier = threading.Barrier(4)
        link = akousma.os.link

        def simultaneous_link(*args, **kwargs):
            barrier.wait(timeout=5)
            return link(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=4) as pool:
            with patch.object(akousma.os, "link", simultaneous_link):
                writers = [pool.submit(self.store.put_audio, self.data) for _ in range(4)]
                self.assertEqual([writer.result(timeout=10) for writer in writers], [self.uri] * 4)
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)
        self.assertEqual(list(self.store.objects_dir.rglob(".audio-*")), [])

    def test_malformed_locators_do_not_resolve(self):
        for name in ("../outside.wav", "/tmp/outside.wav", "aa/../../outside.wav",
                     "a" * 63 + ".wav", self.digest.upper() + ".wav",
                     self.digest + ".wav/extra", self.digest + ".wav?query",
                     self.digest + ".wav#fragment", self.digest + ".wav%2fextra",
                     self.digest + ".wav\\extra", self.digest + ".", self.digest + ".wav\n"):
            with self.subTest(name=name):
                self.assertIsNone(self.store.resolve_uri("akousmata://objects/" + name))
        for uri in (None, 1, "file:///unavailable.wav", "https://example.invalid/audio.wav"):
            with self.subTest(uri=uri):
                self.assertIsNone(self.store.resolve_uri(uri))

    def test_bad_extension_is_refused_before_any_write(self):
        for ext in ("../outside", "wav/extra", "WAV", ".wav", "", "x" * 17, None):
            with self.subTest(ext=ext), self.assertRaises(ValueError):
                self.store.put_audio(self.data, ext=ext)
        self.assertEqual(list(self.store.objects_dir.iterdir()), [])

    def test_content_hash_and_corrupt_bytes_are_refused(self):
        self.store.put_audio(self.data)
        path = self.store.resolve_uri(self.uri)
        for digest in ("sha256:" + "0" * 64, "0" * 64, "sha256:" + self.digest.upper(), "", 1, []):
            with self.subTest(digest=digest):
                self.assertIsNone(self.store.resolve_uri(self.uri, content_hash=digest))
        path.write_bytes(b"different bytes")
        self.assertIsNone(self.store.resolve_uri(self.uri))
        with self.assertRaises(ValueError):
            self.store.put_audio(self.data)
        self.assertEqual(path.read_bytes(), b"different bytes")
        record = self.record()
        receipt = self.store.forget_with_receipt(record["akousma_id"], delete_audio=True)
        self.assertFalse(receipt["audio_deleted"])
        self.assertTrue(path.exists())

    def test_file_and_shard_symlinks_are_refused_without_touching_target(self):
        outside = self.base / "outside.wav"
        outside.write_bytes(self.data)
        shard = self.store.objects_dir / self.digest[:2]
        shard.mkdir()
        path = shard / f"{self.digest}.wav"
        path.symlink_to(outside)
        self.assertIsNone(self.store.resolve_uri(self.uri))
        with self.assertRaises(ValueError):
            self.store.put_audio(self.data)
        receipt = self.store.forget_with_receipt(self.record()["akousma_id"], delete_audio=True)
        self.assertFalse(receipt["audio_deleted"])
        self.assertEqual(outside.read_bytes(), self.data)
        self.assertTrue(path.is_symlink())
        path.unlink()
        shard.rmdir()
        shard.symlink_to(self.base, target_is_directory=True)
        self.assertIsNone(self.store.resolve_uri(self.uri))
        with self.assertRaises(ValueError):
            self.store.put_audio(self.data)
        self.assertEqual(outside.read_bytes(), self.data)

    def test_in_store_symlink_alias_is_also_refused(self):
        self.store.put_audio(self.data)
        original = self.store.resolve_uri(self.uri)
        alias = original.with_suffix('.flac')
        alias.symlink_to(original)
        self.assertIsNone(self.store.resolve_uri(self.uri.replace('.wav', '.flac')))
        self.assertEqual(original.read_bytes(), self.data)

    def test_object_directory_symlink_is_refused_at_open_and_after_open(self):
        other = self.base / "redirect"
        other.mkdir()
        self.store.objects_dir.rmdir()
        self.store.objects_dir.symlink_to(other, target_is_directory=True)
        self.assertIsNone(self.store.resolve_uri(self.uri))
        with self.assertRaises(ValueError):
            self.store.put_audio(self.data)
        with self.assertRaises(ValueError):
            AkousmataStore(self.store.root)
        self.assertEqual(list(other.iterdir()), [])

    def test_invalid_locator_forgetting_keeps_external_file_and_receipt(self):
        outside = self.base / "outside.wav"
        outside.write_bytes(self.data)
        record = self.record(uri="akousmata://objects/../../outside.wav")
        receipt = self.store.forget_with_receipt(record["akousma_id"], delete_audio=True)
        self.assertFalse(receipt["audio_deleted"])
        self.assertTrue(receipt["record_deleted"])
        self.assertEqual(outside.read_bytes(), self.data)
        self.assertIsNotNone(self.store.forgotten(record["akousma_id"]))
        with self.assertRaises(ValueError):
            self.store.put(record)

    def test_mismatched_identity_cannot_delete_a_valid_object(self):
        self.store.put_audio(self.data)
        record = self.record(digest="0" * 64)
        receipt = self.store.forget_with_receipt(record["akousma_id"], delete_audio=True)
        self.assertFalse(receipt["audio_deleted"])
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)

    def test_shared_locator_preserved_even_with_different_declared_hash(self):
        self.store.put_audio(self.data)
        first = self.record()
        self.record(digest="0" * 64)
        receipt = self.store.forget_with_receipt(first["akousma_id"], delete_audio=True)
        self.assertTrue(receipt["shared_audio_preserved"])
        self.assertFalse(receipt["audio_deleted"])
        self.assertEqual(self.store.resolve_uri(self.uri).read_bytes(), self.data)

    def test_valid_unshared_forgetting_deletes_only_the_object(self):
        self.store.put_audio(self.data)
        path = self.store.resolve_uri(self.uri)
        outside = self.base / "keep"
        outside.write_bytes(b"unrelated")
        receipt = self.store.forget_with_receipt(self.record()["akousma_id"], delete_audio=True)
        self.assertTrue(receipt["audio_deleted"])
        self.assertFalse(path.exists())
        self.assertEqual(outside.read_bytes(), b"unrelated")
