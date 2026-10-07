"""YAML configuration with ${ENV_VAR} / ${ENV_VAR:-default} interpolation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from .logins import DEFAULT_PARTICLES

_ENV = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


class FieldMap(BaseModel):
    """Maps canonical fields to the column / key names your HR system uses."""

    employee_id: str = "employee_id"
    full_name: str = "full_name"
    branch: str | None = None
    department: str | None = None
    title: str | None = None
    manager: str | None = None
    start_date: str | None = None


class Unpack(BaseModel):
    """Expand a packed column like 'Name: Ana | ID: 42' into separate fields."""

    column: str
    separator: str = "|"
    kv_separator: str = ":"


class SourceConfig(BaseModel):
    type: Literal["csv", "rest"] = "csv"
    fields: FieldMap = Field(default_factory=FieldMap)
    unpack: Unpack | None = None
    where: dict[str, str] = Field(default_factory=dict)
    # csv
    path: str | None = None
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    # rest
    url: str | None = None
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    body: dict | None = None
    records_path: str = ""
    timeout: float = 30.0

    @model_validator(mode="after")
    def _check(self) -> SourceConfig:
        if self.type == "csv" and not self.path:
            raise ValueError("source.path is required for csv sources")
        if self.type == "rest" and not self.url:
            raise ValueError("source.url is required for rest sources")
        return self


class LoginConfig(BaseModel):
    patterns: list[str] = Field(default_factory=lambda: ["{first}.{last}", "{second}.{last}", "{first}.{last}{n}"])
    max_suffix: int = 9
    max_length: int = 20
    ignore_particles: list[str] = Field(default_factory=lambda: list(DEFAULT_PARTICLES))


class PasswordConfig(BaseModel):
    length: int = 14


class DirectoryConfig(BaseModel):
    type: Literal["ldap", "memory"] = "ldap"
    flavor: Literal["ad", "openldap"] = "openldap"
    url: str = "ldap://localhost:389"
    auth: Literal["simple", "ntlm"] = "simple"
    bind_dn: str = ""
    bind_password: str = ""
    base_dn: str = ""
    start_tls: bool = False
    tls_verify: bool = True
    ca_file: str = ""


class Placement(BaseModel):
    email_domain: str
    ou: str
    groups: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    by_field: str = "branch"
    default: Placement
    match: dict[str, Placement] = Field(default_factory=dict)


class ReportConfig(BaseModel):
    path: str = "reports/run-{timestamp}.csv"
    include_passwords: bool = True


class Config(BaseModel):
    source: SourceConfig
    login: LoginConfig = Field(default_factory=LoginConfig)
    password: PasswordConfig = Field(default_factory=PasswordConfig)
    directory: DirectoryConfig = Field(default_factory=DirectoryConfig)
    rules: RulesConfig
    report: ReportConfig = Field(default_factory=ReportConfig)


def interpolate(text: str, env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    missing: list[str] = []

    def sub(m: re.Match[str]) -> str:
        name, default = m.group(1), m.group(2)
        if name in env:
            return env[name]
        if default is not None:
            return default
        missing.append(name)
        return ""

    out = _ENV.sub(sub, text)
    if missing:
        raise ValueError(f"missing environment variable(s): {', '.join(sorted(set(missing)))}")
    return out


def _interpolate_tree(node):
    if isinstance(node, str):
        return interpolate(node)
    if isinstance(node, dict):
        return {k: _interpolate_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_interpolate_tree(v) for v in node]
    return node


def load_config(path: str | Path) -> Config:
    path = Path(path)
    data = _interpolate_tree(yaml.safe_load(path.read_text(encoding="utf-8")))
    cfg = Config.model_validate(data)
    # Relative file paths are resolved against the config file's folder.
    if cfg.source.path and not Path(cfg.source.path).is_absolute():
        cfg.source.path = str((path.parent / cfg.source.path).resolve())
    return cfg
