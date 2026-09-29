"""Object reads/writes/forgetting stay inside an audit-owned temporary store."""
import hashlib
from pathlib import Path
import tempfile
import unittest

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
