"""Stdlib-only synthetic import-boundary probes; never alter an installed venv."""
import base64
import csv
import hashlib
import importlib
from importlib._bootstrap_external import _code_to_timestamp_pyc
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import harness_native_environment as environment


class EnvironmentChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-environment-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "purelib"
        self.root.mkdir()
        self.package = "synthetic_native_checked"
        self.metadata = self.root / "synthetic_native_contract-1.dist-info"
        self.metadata.mkdir()
        (self.metadata / "METADATA").write_bytes(b"Name: synthetic-native-contract\nVersion: 1\n")
        self.files = {}
        self.put(self.package + "/__init__.py", b"VALUE = 'CHECKED_SOURCE'\n")
        self.seal()
        self.original_path = list(sys.path)
        self.original_meta = list(sys.meta_path)
        self.original_modules = set(sys.modules)
        self.addCleanup(self.restore)

    def restore(self):
        sys.path[:] = self.original_path
        sys.meta_path[:] = self.original_meta
        for name in set(sys.modules) - self.original_modules:
            module = sys.modules.get(name)
            source = getattr(module, "__file__", None)
            spec = getattr(module, "__spec__", None)
            paths = list(getattr(spec, "submodule_search_locations", None) or [])
            if source: paths.append(source)
            if name.startswith(self.package) or any(str(self.root) in str(path) for path in paths):
                sys.modules.pop(name, None)
        importlib.invalidate_caches()

    def put(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.files[name] = raw
        return path

    def seal(self):
        buffer = io.StringIO(newline="")
        rows = csv.writer(buffer)
        for name, raw in sorted(self.files.items()):
            encoded = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
            rows.writerow([name, "sha256=" + encoded, len(raw)])
        rows.writerow([self.metadata.name + "/RECORD", "", ""])
        raw = buffer.getvalue().encode()
        (self.metadata / "RECORD").write_bytes(raw)
        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        self.dependencies = {"synthetic-native-contract": {"version": "1", "record_sha256": hashlib.sha256(normalized).hexdigest(),
                              "verified_files": len(self.files), "role": "runtime"}}

    def verify(self):
        with patch.object(environment, "_dependencies", return_value=self.dependencies) as reused:
            result = environment.verify(self.root)
        reused.assert_called_once_with()
        return result

    def install(self):
        verification = self.verify()
        sys.path.insert(0, str(self.root))
        finder = environment.install_source_only(verification, self.root)
        return verification, finder

    def test_verification_contains_relative_executable_inventory_and_existing_dependency_evidence(self):
        self.put(self.package + "/data.json", b'{"SYNTHETIC":true}')
        self.put(self.package + "/native.pyd", b"SYNTHETIC extension fixture, never executed")
        self.put(self.package + "/support.dll", b"SYNTHETIC library fixture, never executed")
        self.put(self.package + "/support.so.1", b"SYNTHETIC library fixture, never executed")
        self.seal()
        verification = self.verify()
        self.assertEqual(verification["dependencies"], self.dependencies)
        self.assertEqual(set(verification["execution_files"]), set(self.files) - {self.package + "/data.json"})
        self.assertNotIn(str(self.root), json.dumps(verification))

    def test_timestamp_valid_but_changed_pyc_is_ignored_without_cache_mutation(self):
        source = self.root / self.package / "__init__.py"
        pyc = Path(importlib.util.cache_from_source(str(source)))
        pyc.parent.mkdir()
        raw = _code_to_timestamp_pyc(compile("VALUE = 'UNBOUND_BYTECODE'\n", str(source), "exec"),
                                     int(source.stat().st_mtime), source.stat().st_size)
        pyc.write_bytes(raw)
        verification, _ = self.install()
        module = importlib.import_module(self.package)
        self.assertEqual(module.VALUE, "CHECKED_SOURCE")
        self.assertEqual(pyc.read_bytes(), raw)
        self.assertEqual(self.verify(), verification)

    def test_source_change_after_install_refused_before_execution(self):
        self.install()
        (self.root / self.package / "__init__.py").write_bytes(b"VALUE = 'CHANGED'\n")
        with self.assertRaisesRegex(environment.Refused, "bytes changed"):
            importlib.import_module(self.package)
        self.assertNotIn(self.package, sys.modules)

    def test_source_loader_compiles_verified_buffer_even_if_file_changes_after_read(self):
        self.install()
        original = environment._bytes
        def read_then_change(root, name, expected):
            raw = original(root, name, expected)
            (root / name).write_bytes(b"VALUE = 'LATE_REPLACEMENT'\n")
            return raw
        with patch.object(environment, "_bytes", side_effect=read_then_change):
            module = importlib.import_module(self.package)
        self.assertEqual(module.VALUE, "CHECKED_SOURCE")

    def test_unlisted_source_or_native_library_is_refused(self):
        for suffix in (".py", ".pyd", ".dll", ".so"):
            with self.subTest(suffix=suffix):
                path = self.root / ("unlisted" + suffix)
                path.write_bytes(b"SYNTHETIC unlisted executable")
                with self.assertRaisesRegex(environment.Refused, "unlisted"):
                    self.verify()
                path.unlink()  # Fixture-owned single file, never an installed environment.

    def test_sourceless_bytecode_is_refused_even_when_recorded(self):
        self.put("orphan.pyc", b"SYNTHETIC sourceless cache")
        self.seal()
        with self.assertRaisesRegex(environment.Refused, "sourceless"):
            self.verify()

    def test_added_unlisted_module_after_install_is_refused(self):
        self.install()
        (self.root / "late_unlisted.py").write_text("VALUE='SYNTHETIC'\n", encoding="utf-8")
        importlib.invalidate_caches()
        with self.assertRaisesRegex(environment.Refused, "unlisted native import"):
            importlib.import_module("late_unlisted")

    def test_already_imported_module_cannot_be_retroactively_trusted(self):
        sys.path.insert(0, str(self.root))
        importlib.import_module(self.package)
        with self.assertRaisesRegex(environment.Refused, "already loaded"):
            environment.install_source_only(self.verify(), self.root)

    def test_unverified_bootstrap_module_is_not_exempt(self):
        self.put("_distutils_hack/__init__.py", b"SYNTHETIC=True\n")
        self.seal()
        module = types.ModuleType("_distutils_hack")
        origin = self.root / "_distutils_hack" / "__init__.py"
        module.__file__ = str(origin)
        module.__spec__ = importlib.util.spec_from_file_location("_distutils_hack", origin)
        with patch.dict(sys.modules, {"_distutils_hack": module}):
            with self.assertRaisesRegex(environment.Refused, "already loaded"):
                environment.install_source_only(self.verify(), self.root)

    def test_reinstall_accepts_only_same_verified_loader_and_inventory(self):
        verification, finder = self.install()
        importlib.import_module(self.package)
        self.assertIs(environment.install_source_only(verification, self.root), finder)
        changed = {**verification, "execution_files": dict(verification["execution_files"])}
        changed["execution_files"][self.package + "/__init__.py"] = "f" * 64
        with self.assertRaises(environment.Refused):
            environment.install_source_only(changed, self.root)

    def test_owned_package_cannot_be_shadowed_from_another_directory(self):
        self.install()
        outside = self.root.parent / "shadow"
        (outside / self.package).mkdir(parents=True)
        (outside / self.package / "__init__.py").write_text("VALUE='SHADOW'\n", encoding="utf-8")
        sys.path.insert(0, str(outside))
        with self.assertRaisesRegex(environment.Refused, "shadowed"):
            importlib.import_module(self.package)

    def test_namespace_package_and_checked_submodule_are_supported(self):
        self.put("synthetic_namespace/module.py", b"VALUE='NAMESPACE_SOURCE'\n")
        self.seal()
        verification, finder = self.install()
        module = importlib.import_module("synthetic_namespace.module")
        self.assertEqual(module.VALUE, "NAMESPACE_SOURCE")
        self.assertIs(environment.install_source_only(verification, self.root), finder)

    def test_pth_is_not_processed_and_startup_customization_is_refused(self):
        self.put("synthetic-startup.pth", b"import SYNTHETIC_THIS_MUST_NEVER_EXECUTE\n")
        self.put("sitecustomize.py", b"raise AssertionError('SYNTHETIC startup must not execute')\n")
        self.seal()
        self.install()
        self.assertEqual(importlib.import_module(self.package).VALUE, "CHECKED_SOURCE")
        with self.assertRaisesRegex(environment.Refused, "startup customization"):
            importlib.import_module("sitecustomize")

    def test_extension_is_rechecked_before_native_loader_execution(self):
        filename = "synthetic_extension" + importlib.machinery.EXTENSION_SUFFIXES[0]
        self.put(filename, b"SYNTHETIC extension fixture, never executed")
        self.seal()
        _, finder = self.install()
        spec = finder.find_spec("synthetic_extension")
        (self.root / filename).write_bytes(b"CHANGED SYNTHETIC extension")
        with patch.object(importlib.machinery.ExtensionFileLoader, "create_module", side_effect=AssertionError("unverified native bytes executed")):
            with self.assertRaisesRegex(environment.Refused, "bytes changed"):
                spec.loader.create_module(spec)

    def test_record_change_after_existing_checker_is_refused(self):
        (self.metadata / "RECORD").write_bytes(b"SYNTHETIC changed record")
        with self.assertRaisesRegex(environment.Refused, "RECORD changed"):
            self.verify()

    def test_recorded_source_without_hash_is_refused(self):
        raw = (self.package + "/__init__.py,,\n").encode()
        (self.metadata / "RECORD").write_bytes(raw)
        self.dependencies["synthetic-native-contract"]["record_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(environment.Refused, "lacks RECORD"):
            self.verify()

    def test_linked_paths_are_refused(self):
        if sys.platform == "win32":
            outside = self.root.parent / "outside-directory"
            outside.mkdir()
            junction = self.root / "unlisted-junction"
            created = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue(junction.is_junction())
            self.addCleanup(os.rmdir, junction)  # Remove this fixture junction, never its target tree.
            with self.assertRaisesRegex(environment.Refused, "linked"):
                self.verify()
            self.assertTrue(outside.is_dir())
            return
        source = self.root / self.package / "__init__.py"
        other = self.root.parent / "outside.py"
        other.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(other)
        except OSError as exc:
            self.skipTest("OS does not permit fixture symlinks: " + type(exc).__name__)
        with self.assertRaisesRegex(environment.Refused, "linked"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
