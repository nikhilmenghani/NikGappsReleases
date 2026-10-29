"""Re-sign a development APK with its existing identity and verify its payload."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile


class SigningError(RuntimeError):
    pass


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_tool(arguments, environment):
    try:
        result = subprocess.run(arguments, env=environment, capture_output=True, text=True)
    except OSError:
        raise SigningError("Could not run Android apksigner") from None
    if result.returncode:
        # Signing-tool diagnostics can contain sensitive inputs. Never echo them.
        raise SigningError("Android apksigner failed; no APK was published")
    return result.stdout


def verify(apksigner, apk, environment, expected_certificate, require_v2_only=False):
    result = run_tool([str(apksigner), "verify", "--verbose", "--print-certs", str(apk)], environment)
    certificates = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([a-fA-F0-9]{64})$", result, re.M)
    if [value.lower() for value in certificates] != [expected_certificate]:
        raise SigningError("APK signing certificate does not match the expected release certificate")
    if require_v2_only:
        schemes = dict(re.findall(r"^Verified using (v[\d.]+) scheme[^\n]*: (true|false)$", result, re.M))
        if schemes.get("v2") != "true" or any(value != "false" for key, value in schemes.items() if key != "v2"):
            raise SigningError("APK does not use the required v2-only signing configuration")


def compressed_digest(stream, entry):
    stream.seek(entry.header_offset)
    header = stream.read(30)
    if len(header) != 30 or header[:4] != b"PK\x03\x04":
        raise SigningError("Malformed APK entry header")
    name_length, extra_length = struct.unpack_from("<HH", header, 26)
    stream.seek(name_length + extra_length, os.SEEK_CUR)
    remaining = entry.compress_size
    digest = hashlib.sha256()
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        if not chunk:
            raise SigningError("Truncated APK entry")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.digest()


def verify_payload(original, candidate):
    try:
        with zipfile.ZipFile(original) as before, zipfile.ZipFile(candidate) as after, \
                Path(original).open("rb") as raw_before, Path(candidate).open("rb") as raw_after:
            names = before.namelist()
            if names != after.namelist() or len(names) != len(set(names)):
                raise SigningError("APK entries were added, removed, reordered or duplicated")
            for name in names:
                left, right = before.getinfo(name), after.getinfo(name)
                if left.flag_bits & 1 or right.flag_bits & 1:
                    raise SigningError("Encrypted APK entries are not supported")
                if (left.file_size, left.compress_size, left.compress_type) != \
                        (right.file_size, right.compress_size, right.compress_type):
                    raise SigningError("APK payload or compression changed during signing")
                # Reading every entry verifies ZIP CRCs as well as content identity.
                with before.open(left) as first, after.open(right) as second:
                    if hashlib.file_digest(first, "sha256").digest() != hashlib.file_digest(second, "sha256").digest():
                        raise SigningError("APK contents changed during signing")
                if compressed_digest(raw_before, left) != compressed_digest(raw_after, right):
                    raise SigningError("APK entries were recompressed during signing")
            return len(names)
    except (zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError) as error:
        if isinstance(error, SigningError):
            raise
        raise SigningError("APK payload validation failed") from None


def normalize(apk, output, keystore, alias, apksigner, expected_certificate, environment=None, report=None):
    apk, output, keystore, apksigner = map(Path, (apk, output, keystore, apksigner))
    environment = dict(os.environ if environment is None else environment)
    expected_certificate = expected_certificate.replace(":", "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_certificate):
        raise SigningError("Invalid expected certificate fingerprint")
    if not apk.is_file() or not keystore.is_file() or not apksigner.is_file():
        raise SigningError("APK, keystore or apksigner is missing")
    if not alias or not environment.get("APK_STORE_PASSWORD") or not environment.get("APK_KEY_PASSWORD"):
        raise SigningError("Signing alias and password environment variables are required")
    if output.exists() or output.resolve() in (apk.resolve(), keystore.resolve()):
        raise SigningError("Output must be a new file; existing inputs and outputs are preserved")
    if report is not None and Path(report).resolve() in (apk.resolve(), output.resolve(), keystore.resolve()):
        raise SigningError("Verification report must not overwrite the APK or keystore")
    original_hash = sha256(apk)
    verify(apksigner, apk, environment, expected_certificate)
    with tempfile.TemporaryDirectory(prefix=".apk-signing-", dir=output.parent) as staging:
        candidate = Path(staging) / "candidate.apk"
        run_tool([
            str(apksigner), "sign", "--ks", str(keystore), "--ks-key-alias", alias,
            "--ks-pass", "env:APK_STORE_PASSWORD", "--key-pass", "env:APK_KEY_PASSWORD",
            "--v1-signing-enabled", "false", "--v2-signing-enabled", "true",
            "--v3-signing-enabled", "false", "--v4-signing-enabled", "false",
            "--out", str(candidate), str(apk),
        ], environment)
        verify(apksigner, candidate, environment, expected_certificate, require_v2_only=True)
        count = verify_payload(apk, candidate)
        if sha256(apk) != original_hash:
            raise SigningError("Input APK changed during signing")
        result = {
            "input_sha256": original_hash,
            "output_sha256": sha256(candidate),
            "certificate_sha256": expected_certificate,
            "signature_scheme": "v2",
            "verified_entries": count,
            "payload_unchanged": True,
            "compressed_entry_bytes_unchanged": True,
        }
        if report is not None:
            Path(report).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        # Same-directory hard link publishes the complete verified file atomically
        # and refuses to overwrite an output created by another process.
        os.link(candidate, output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "output", "keystore", "alias", "apksigner", "expected-certificate"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        result = normalize(args.input, args.output, args.keystore, args.alias, args.apksigner,
                           args.expected_certificate, report=args.report)
    except (SigningError, OSError) as error:
        # Never expose raw tool output or password values through exception messages.
        print(str(error) if isinstance(error, SigningError) else "APK signing output could not be written")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
