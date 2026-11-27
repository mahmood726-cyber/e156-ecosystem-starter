"""Verify native import files and compile checked source instead of cached pyc.

This is consistency under a trusted local interpreter, not hostile-host
attestation. OS libraries outside purelib are outside this import boundary.
No package installation, cache deletion, .pth processing or network occurs.
"""
from __future__ import annotations

import base64
import copy
import csv
from email import message_from_bytes
import hashlib
import hmac
import importlib.abc
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from types import MappingProxyType

if __package__:
    from scripts import harness_context as context
else:
    import harness_context as context

require, Refused = context.require, context.Refused
HASH = re.compile(r"[0-9a-f]{64}")


def purelib_path(purelib=None):
    """Resolve independently of sys.prefix, which differs under Python 3.13 -S."""
    if purelib is None:
        executable = context.guard(sys.executable).resolve()
        prefix = executable.parent.parent
        require(sys.platform == "win32" and executable.parent.name == "Scripts"
                and context.guard(prefix / "pyvenv.cfg").is_file(), "supported Windows virtualenv required")
        purelib = prefix / "Lib" / "site-packages"
    root = context.guard(purelib).resolve()
    require(root.is_dir(), "native purelib directory missing")
    return root


def _dependencies():
    # Reuse the existing complete version/RECORD check without modifying it.
    if __package__:
        from scripts.harness_execution_benchmark import dependency_manifest
    else:
        from harness_execution_benchmark import dependency_manifest
    return dependency_manifest()


def _code(name):
    lower = name.lower()
    return lower.endswith((".py", ".pyd", ".dll", ".so")) or ".so." in lower


def _relative(root, path):
    path = context.guard(path).resolve()
    require(path != root and root in path.parents, "native import origin outside verified purelib")
    return path.relative_to(root).as_posix()


def _file(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "native execution path must be relative POSIX")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts
            and relative.as_posix() == name, "native execution path escape")
    return context.guard(root.joinpath(*relative.parts))


def _bytes(root, name, expected):
    require(isinstance(expected, str) and HASH.fullmatch(expected), "invalid native executable digest")
    raw = _read_bounded(_file(root, name))
    require(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected), "native executable bytes changed")
    return raw


def _read_bounded(path):
    # The complete tree is link-checked before these bulk verification reads.
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        require(size <= context.MAX_FILE, "native executable exceeds bounded read size")
        raw = handle.read(size + 1)
    require(len(raw) == size, "native executable changed during bounded read")
    return raw


def _files(root):
    result = []
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                status = entry.stat(follow_symlinks=False)
                require(not stat.S_ISLNK(status.st_mode)
                        and not (getattr(status, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)),
                        "linked native paths refused")
                if stat.S_ISDIR(status.st_mode):
                    pending.append(Path(entry.path))
                else:
                    require(stat.S_ISREG(status.st_mode), "unsupported native filesystem entry")
                    result.append(Path(entry.path))
    return result


def _cache_source(root, path, inventory):
    try:
        source = Path(importlib.util.source_from_cache(str(path))) if path.parent.name == "__pycache__" else path.with_suffix(".py")
    except ValueError as exc:
        raise Refused("unrecognized native bytecode cache") from exc
    # Both paths came from the already guarded tree walk; avoid re-walking every
    # filesystem ancestor for thousands of generated caches.
    try:
        name = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise Refused("native bytecode source outside purelib") from exc
    require(name in inventory, "sourceless native bytecode refused")


def _footprint(root, inventory, files=None):
    observed = set()
    caches = []
    for path in _files(root) if files is None else files:
        relative = path.relative_to(root).as_posix()
        if _code(relative):
            require(relative in inventory, "unlisted native executable file")
            require(hmac.compare_digest(hashlib.sha256(_read_bounded(path)).hexdigest(), inventory[relative]),
                    "native executable bytes changed")
            observed.add(relative)
        elif path.suffix.lower() in {".pyc", ".pyo"}:
            caches.append(path)
    require(observed == set(inventory), "native executable inventory incomplete")
    for path in caches:
        _cache_source(root, path, inventory)


def verify(purelib=None):
    """Return path-free distribution evidence plus every purelib executable hash."""
    root = purelib_path(purelib)
    dependencies = _dependencies()
    inventory = {}
    files = _files(root)
    present = {path.relative_to(root).as_posix(): path for path in files}
    records = sorted(path for path in files if path.name == "RECORD" and path.parent.parent == root
                     and path.parent.name.endswith(".dist-info"))
    require(records, "native installed RECORD inventory missing")
    for record in records:
        raw = _read_bounded(record)
        # importlib.metadata.read_text() uses universal newlines. Match that
        # existing manifest field; executable identities below use raw bytes.
        record_text = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8").read()
        name = message_from_bytes(_read_bounded(record.parent / "METADATA")).get("Name")
        require(isinstance(name, str), "native distribution identity missing")
        distribution = dependencies.get(name.lower().replace("_", "-"))
        require(isinstance(distribution, dict)
                and hmac.compare_digest(hashlib.sha256(record_text.encode("utf-8")).hexdigest(), distribution.get("record_sha256", "")),
                "native RECORD changed after dependency verification")
        for row in csv.reader(io.StringIO(record_text)):
            require(len(row) == 3, "malformed native RECORD row")
            name, encoded, size = row
            relative = PurePosixPath(name)
            require(name and not relative.is_absolute() and ":" not in name and "\\" not in name,
                    "unsupported native RECORD path")
            if ".." in relative.parts:
                continue  # Wheel-owned scripts outside purelib remain covered by the reused checker.
            require(relative.as_posix() == name, "noncanonical native RECORD path")
            if not _code(name):
                continue
            require(encoded.startswith("sha256="), "native executable lacks RECORD SHA-256")
            require(name in present, "recorded native executable missing")
            data = _read_bounded(present[name])
            actual = hashlib.sha256(data).digest()
            wanted = base64.urlsafe_b64encode(actual).decode("ascii").rstrip("=")
            require(hmac.compare_digest(wanted, encoded[7:]) and (not size or str(len(data)) == size),
                    "native executable differs from RECORD")
            value = actual.hex()
            require(name not in inventory or hmac.compare_digest(inventory[name], value), "conflicting native executable owners")
            inventory[name] = value
    _footprint(root, inventory, files)
    return {"dependencies": dependencies, "execution_files": dict(sorted(inventory.items()))}


class _Source(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, path, root, inventory):
        super().__init__(fullname, str(path))
        self.root, self.inventory = root, inventory
        self.relative = _relative(root, path)

    def get_code(self, fullname):
        require(fullname == self.name, "native source loader name changed")
        raw = _bytes(self.root, self.relative, self.inventory[self.relative])
        return self.source_to_code(raw, self.path)


class _Extension(importlib.machinery.ExtensionFileLoader):
    def __init__(self, fullname, path, root, inventory):
        super().__init__(fullname, str(path))
        self.root, self.inventory = root, inventory
        self.relative = _relative(root, path)

    def _check(self):
        _bytes(self.root, self.relative, self.inventory[self.relative])
        # Adjacent native libraries are also bound; system DLL resolution is not attested.
        for name, expected in self.inventory.items():
            if name.lower().endswith(".dll"):
                _bytes(self.root, name, expected)

    def create_module(self, spec):
        self._check()
        return super().create_module(spec)

    def exec_module(self, module):
        self._check()
        return super().exec_module(module)


class _Namespace(importlib.abc.Loader):
    def __init__(self, root, inventory):
        self.root, self.inventory = root, inventory

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        return None


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self, root, inventory):
        self.root = root
        self.inventory = MappingProxyType(dict(inventory))
        self.owned = {name.split("/", 1)[0].split(".", 1)[0] for name in inventory}

    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"sitecustomize", "usercustomize"}:
            raise Refused("native startup customization is disabled")
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        owned = fullname.split(".", 1)[0] in self.owned
        if spec is None:
            require(not owned, "native module missing from verified footprint")
            return None
        if spec.origin is None:
            locations = list(spec.submodule_search_locations or [])
            inside = [self.root in Path(value).resolve().parents for value in locations]
            if not owned and not any(inside):
                return None
            require(locations and all(inside), "native namespace crosses verified purelib")
            for location in locations:
                context.guard(location)
            spec.loader = _Namespace(self.root, self.inventory)
            return spec
        origin = context.guard(spec.origin).resolve()
        inside = self.root in origin.parents
        if not owned and not inside:
            return None
        require(inside, "native module shadowed outside verified purelib")
        relative = _relative(self.root, origin)
        require(relative in self.inventory, "unlisted native import origin")
        if isinstance(spec.loader, importlib.machinery.SourceFileLoader) and origin.suffix.lower() == ".py":
            spec.loader = _Source(fullname, origin, self.root, self.inventory)
        elif isinstance(spec.loader, importlib.machinery.ExtensionFileLoader):
            spec.loader = _Extension(fullname, origin, self.root, self.inventory)
        else:
            raise Refused("unsupported native import loader")
        return spec


def _loaded(root, inventory, owned):
    for name, module in list(sys.modules.items()):
        if module is None:
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
        locations = list(getattr(spec, "submodule_search_locations", None) or [])
        paths = ([origin] if origin and origin not in {"built-in", "frozen"} else []) + locations
        inside = any(root in Path(path).resolve().parents for path in paths)
        if not inside and name.split(".", 1)[0] not in owned:
            continue
        loader = getattr(spec, "loader", None)
        require(isinstance(loader, (_Source, _Extension, _Namespace)) and loader.root == root
                and dict(loader.inventory) == inventory,
                "native module already loaded by an unverified loader; use a clean isolated process")


def install_source_only(verification, purelib=None):
    """Install before native imports; refuse retroactive trust in loaded packages.

Returns the installed finder so fixture tests can remove their own hook. This
function never adds sys.path entries or executes site/.pth startup processing.
"""
    root = purelib_path(purelib)
    require(isinstance(verification, dict) and set(verification) == {"dependencies", "execution_files"}
            and isinstance(verification["dependencies"], dict) and isinstance(verification["execution_files"], dict),
            "native verification schema mismatch")
    inventory = copy.deepcopy(verification["execution_files"])
    require(inventory, "native executable inventory missing")
    for name, expected in inventory.items():
        require(isinstance(name, str) and _code(name) and isinstance(expected, str) and HASH.fullmatch(expected),
                "unsupported native inventory entry")
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and ":" not in name
                and relative.as_posix() == name, "native execution path escape")
    _footprint(root, inventory)
    finder = _Finder(root, inventory)
    _loaded(root, inventory, finder.owned)
    for installed in sys.meta_path:
        if isinstance(installed, _Finder) and installed.root == root:
            require(dict(installed.inventory) == inventory, "native loader inventory changed")
            return installed
    sys.meta_path.insert(0, finder)
    return finder
