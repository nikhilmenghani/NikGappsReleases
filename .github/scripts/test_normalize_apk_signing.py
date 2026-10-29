"""Failure-path tests with a fake signer; real-signature integration is separate."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from normalize_apk_signing import SigningError, normalize, sha256, verify_payload


CERTIFICATE = "a" * 64


class NormalizeSigningTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / "input.apk"
        self.output = self.root / "normalized.apk"
        self.keystore = self.root / "test.keystore"
        self.tool = self.root / "apksigner"
        self.report = self.root / "report.json"
        self.keystore.write_bytes(b"fake key for unit tests")
        self.tool.touch()
        self.entries = [("AndroidManifest.xml", b"manifest with install permission"),
                        ("classes.dex", b"executable payload" * 1024),
                        ("assets/debloater.sh", b"installer script" * 1024)]
        self.write_apk(self.apk, self.entries)
        self.original_hash = sha256(self.apk)
        self.environment = {"APK_STORE_PASSWORD": "private store password",
                            "APK_KEY_PASSWORD": "private key password"}
        self.mode = "success"
        self.calls = []

    def write_apk(self, path, entries, level=9):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as archive:
            for name, contents in entries:
                archive.writestr(name, contents)

    def fake_signer(self, arguments, **kwargs):
        self.calls.append(arguments)
        self.assertTrue(kwargs["capture_output"])
        self.assertNotIn(self.environment["APK_STORE_PASSWORD"], arguments)
        self.assertNotIn(self.environment["APK_KEY_PASSWORD"], arguments)
        if arguments[1] == "verify":
            is_output = Path(arguments[-1]).name == "candidate.apk"
            if self.mode == "invalid_signature" and is_output:
                return subprocess.CompletedProcess(arguments, 1, "", "signature invalid")
            fingerprint = "b" * 64 if (self.mode == "wrong_input_key" and not is_output) or \
                (self.mode == "wrong_output_key" and is_output) else CERTIFICATE
            v3 = "true" if self.mode == "wrong_scheme" and is_output else "false"
            text = (f"Signer #1 certificate SHA-256 digest: {fingerprint}\n"
                    "Verified using v1 scheme (JAR signing): false\n"
                    "Verified using v2 scheme (APK Signature Scheme v2): true\n"
                    f"Verified using v3 scheme (APK Signature Scheme v3): {v3}\n"
                    "Verified using v4 scheme (APK Signature Scheme v4): false\n")
            return subprocess.CompletedProcess(arguments, 0, text, "")
        self.assertEqual(arguments[1], "sign")
        if self.mode == "sign_failure":
            return subprocess.CompletedProcess(arguments, 1, "", self.environment["APK_STORE_PASSWORD"])
        candidate = Path(arguments[arguments.index("--out") + 1])
        shutil.copyfile(arguments[-1], candidate)
        if self.mode == "changed_manifest":
            self.write_apk(candidate, [(name, b"changed manifest" if name == "AndroidManifest.xml" else data)
                                       for name, data in self.entries])
        elif self.mode == "changed_code":
            self.write_apk(candidate, [(name, b"changed executable" if name == "classes.dex" else data)
                                       for name, data in self.entries])
        elif self.mode == "added_entry":
            self.write_apk(candidate, self.entries + [("extra.dex", b"new executable")])
        elif self.mode == "recompressed":
            self.write_apk(candidate, self.entries, level=1)
        elif self.mode == "truncated":
            candidate.write_bytes(b"PK\x03\x04")
        elif self.mode == "input_changed":
            self.apk.write_bytes(self.apk.read_bytes() + b"concurrent input change")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    def run_normalization(self):
        with patch("normalize_apk_signing.subprocess.run", side_effect=self.fake_signer):
            return normalize(self.apk, self.output, self.keystore, "test alias", self.tool,
                             CERTIFICATE, environment=self.environment, report=self.report)

    def test_success_retains_input_and_reports_public_verification_metadata(self):
        result = self.run_normalization()
        self.assertEqual(sha256(self.apk), self.original_hash)
        self.assertEqual(verify_payload(self.apk, self.output), 3)
        self.assertEqual(result["certificate_sha256"], CERTIFICATE)
        self.assertEqual(result["output_sha256"], sha256(self.output))
        self.assertTrue(result["compressed_entry_bytes_unchanged"])
        self.assertEqual(json.loads(self.report.read_text()), result)
        for password in self.environment.values():
            self.assertNotIn(password, self.report.read_text())
        sign_call = next(call for call in self.calls if call[1] == "sign")
        self.assertIn("env:APK_STORE_PASSWORD", sign_call)
        self.assertIn("env:APK_KEY_PASSWORD", sign_call)
        self.assertEqual(sign_call[sign_call.index("--v3-signing-enabled") + 1], "false")
        self.assertFalse(list(self.root.glob(".apk-signing-*")))

    def test_failed_signing_or_validation_never_publishes_candidate(self):
        for mode in ("sign_failure", "invalid_signature", "wrong_input_key", "wrong_output_key", "wrong_scheme",
                     "changed_manifest", "changed_code", "added_entry", "recompressed", "truncated"):
            with self.subTest(mode=mode):
                self.mode = mode
                with self.assertRaises(SigningError) as raised:
                    self.run_normalization()
                self.assertFalse(self.output.exists())
                self.assertEqual(sha256(self.apk), self.original_hash)
                self.assertFalse(list(self.root.glob(".apk-signing-*")))
                self.assertNotIn(self.environment["APK_STORE_PASSWORD"], str(raised.exception))

    def test_existing_output_is_not_overwritten(self):
        self.output.write_bytes(b"previous valid output")
        with self.assertRaises(SigningError):
            self.run_normalization()
        self.assertEqual(self.output.read_bytes(), b"previous valid output")
        self.assertEqual(self.calls, [])

    def test_same_input_and_output_is_rejected(self):
        self.output = self.apk
        with self.assertRaises(SigningError):
            self.run_normalization()
        self.assertEqual(sha256(self.apk), self.original_hash)

    def test_input_change_during_signing_is_rejected(self):
        self.mode = "input_changed"
        with self.assertRaisesRegex(SigningError, "Input APK changed"):
            self.run_normalization()
        self.assertFalse(self.output.exists())

    def test_missing_password_stops_before_any_tool_execution(self):
        del self.environment["APK_KEY_PASSWORD"]
        with self.assertRaises(SigningError):
            self.run_normalization()
        self.assertEqual(self.calls, [])

    def test_report_cannot_overwrite_apk_or_keystore(self):
        for target in (self.apk, self.keystore, self.output):
            with self.subTest(target=target.name):
                self.report = target
                with self.assertRaises(SigningError):
                    self.run_normalization()
        self.assertEqual(sha256(self.apk), self.original_hash)
        self.assertEqual(self.keystore.read_bytes(), b"fake key for unit tests")

    def test_concurrent_output_is_preserved(self):
        original_link = os.link

        def create_conflict(source, destination):
            self.output.write_bytes(b"another operation's output")
            original_link(source, destination)

        with patch("normalize_apk_signing.os.link", side_effect=create_conflict):
            with self.assertRaises(FileExistsError):
                self.run_normalization()
        self.assertEqual(self.output.read_bytes(), b"another operation's output")
        self.assertFalse(list(self.root.glob(".apk-signing-*")))

    def test_storage_failure_cleans_staging_and_preserves_input(self):
        with patch("normalize_apk_signing.os.link", side_effect=OSError("No space left on device")):
            with self.assertRaises(OSError):
                self.run_normalization()
        self.assertFalse(self.output.exists())
        self.assertEqual(sha256(self.apk), self.original_hash)
        self.assertFalse(list(self.root.glob(".apk-signing-*")))


if __name__ == "__main__":
    unittest.main()
