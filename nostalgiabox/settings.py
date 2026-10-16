"""Validated configuration drafts. UI and CLI share the existing Config schema."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import yaml
from .config import ConfigError, config_from_dict, library_problem
from .storage import atomic_write

SCHEMA_VERSION = 1


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def read_document(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f'Cannot read settings: {exc}') from exc
    if not isinstance(raw, dict):
        raise ConfigError('Settings must be a YAML mapping')
    version = raw.get('schema_version', 0)
    if type(version) is not int or version not in (0, SCHEMA_VERSION):
        raise ConfigError(f'Unsupported settings schema version: {version}')
    return raw


def merge_document(original, updates):
    result = copy.deepcopy(original)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_document(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_document(raw, path: Path, *, require_media=True):
    if not isinstance(raw, dict):
        raise ConfigError('Settings must be a mapping')
    try:
        cfg = config_from_dict(raw, base_dir=path.parent)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ConfigError(str(exc)) from exc
    if require_media:
        roots = [c.path for c in cfg.channels] if raw.get('channels') else [cfg.active_media_root]
        for root in roots:
            if root is None:
                raise ConfigError('Choose a library folder')
            error = library_problem(root)
            if error:
                raise ConfigError(error)
        if not cfg.channels:
            raise ConfigError('No show folders found. Put videos inside one subfolder per show.')
    return cfg


class SettingsDraft:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.original = read_document(self.path)
        self.expected = fingerprint(self.path)
        self.data = copy.deepcopy(self.original)

    def update(self, values):
        self.data = merge_document(self.data, values)

    def validate(self):
        return validate_document(self.data, self.path)

    def save(self):
        cfg = self.validate()
        if fingerprint(self.path) != self.expected:
            raise ConfigError('Settings changed in another window. Close and reopen settings before saving.')
        if self.path.exists() and self.original.get('schema_version', 0) == 0:
            backup = self.path.with_suffix(self.path.suffix + '.v0.bak')
            if not backup.exists():
                atomic_write(backup, self.path.read_text(encoding='utf-8'))
        self.data['schema_version'] = SCHEMA_VERSION
        atomic_write(self.path, yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True))
        self.original = copy.deepcopy(self.data)
        self.expected = fingerprint(self.path)
        return cfg
