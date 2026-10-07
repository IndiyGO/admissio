"""Active Directory and OpenLDAP provisioning over LDAP (ldap3)."""

from __future__ import annotations

import ssl
from collections.abc import Callable

from ldap3 import HASHED_SALTED_SHA, MODIFY_ADD, MODIFY_REPLACE, NTLM, SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn
from ldap3.utils.hashed import hashed

from ..config import DirectoryConfig
from ..models import AccountSpec
from . import DirectoryError, LoginTaken

ENTRY_ALREADY_EXISTS = 68

# userAccountControl flags
NORMAL_ACCOUNT = 0x0200
ACCOUNT_DISABLED = 0x0002

FLAVORS = {
    "ad": {
        "login": "sAMAccountName",
        "employee_id": "employeeID",
        "object_class": ["top", "person", "organizationalPerson", "user"],
    },
    "openldap": {
        "login": "uid",
        "employee_id": "employeeNumber",
        "object_class": ["top", "person", "organizationalPerson", "inetOrgPerson"],
    },
}


def connect(cfg: DirectoryConfig) -> Connection:
    use_ssl = cfg.url.lower().startswith("ldaps://")
    tls = None
    if use_ssl or cfg.start_tls:
        tls = Tls(
            validate=ssl.CERT_REQUIRED if cfg.tls_verify else ssl.CERT_NONE,
            ca_certs_file=cfg.ca_file or None,
        )
    server = Server(cfg.url, use_ssl=use_ssl, tls=tls, connect_timeout=10)
    conn = Connection(
        server,
        user=cfg.bind_dn,
        password=cfg.bind_password,
        authentication=NTLM if cfg.auth == "ntlm" else SIMPLE,
        auto_referrals=False,  # AD returns referrals for DNS zones/config; never chase them
        raise_exceptions=False,
    )
    if cfg.start_tls and not use_ssl:
        conn.open()
        conn.start_tls()
    if not conn.bind():
        raise DirectoryError(f"bind failed: {conn.result.get('description')} {conn.result.get('message', '')}")
    return conn


class LdapDirectory:
    def __init__(
        self,
        cfg: DirectoryConfig,
        connection: Connection | None = None,
        connector: Callable[[DirectoryConfig], Connection] = connect,
        encrypted: bool | None = None,
    ) -> None:
        self.cfg = cfg
        self.attrs = FLAVORS[cfg.flavor]
        self.conn = connection or connector(cfg)
        if encrypted is None:
            encrypted = cfg.url.lower().startswith("ldaps://") or cfg.start_tls
        self.encrypted = encrypted

    # -- lookups ---------------------------------------------------------

    def _first(self, attribute: str, value: str) -> dict | None:
        flt = f"({attribute}={escape_filter_chars(value)})"
        self.conn.search(self.cfg.base_dn, flt, SUBTREE, attributes=[self.attrs["login"]], size_limit=1)
        # Skip search references (AD sends them alongside real entries).
        return next((r for r in self.conn.response or [] if r.get("type") == "searchResEntry"), None)

    def login_exists(self, login: str) -> bool:
        return self._first(self.attrs["login"], login) is not None

    def find_by_employee_id(self, employee_id: str) -> str | None:
        hit = self._first(self.attrs["employee_id"], employee_id)
        if not hit:
            return None
        value = hit["attributes"].get(self.attrs["login"])
        return (value[0] if isinstance(value, list) else value) or hit["dn"]

    # -- creation --------------------------------------------------------

    def create_user(self, spec: AccountSpec) -> list[str]:
        if self.cfg.flavor == "ad":
            return self._create_ad(spec)
        return self._create_openldap(spec)

    def _add(self, dn: str, attributes: dict) -> None:
        if self.conn.add(dn, self.attrs["object_class"], attributes):
            return
        if self.conn.result.get("result") == ENTRY_ALREADY_EXISTS:
            raise LoginTaken(dn)
        raise DirectoryError(f"{self.conn.result.get('description')}: {self.conn.result.get('message', '')}")

    def _common(self, spec: AccountSpec) -> dict:
        attrs = {
            "cn": spec.display_name,
            "sn": spec.surname or spec.display_name,
            "givenName": spec.given_name,
            "displayName": spec.display_name,
            "mail": spec.email,
            self.attrs["login"]: spec.login,
            self.attrs["employee_id"]: spec.employee_id,
        }
        if spec.title:
            attrs["title"] = spec.title
        if spec.department:
            attrs["departmentNumber" if self.cfg.flavor == "openldap" else "department"] = spec.department
        return attrs

    def _create_openldap(self, spec: AccountSpec) -> list[str]:
        dn = f"uid={escape_rdn(spec.login)},{spec.ou}"
        attrs = self._common(spec)
        if spec.password:
            # OpenLDAP stores userPassword as given; hash it so it never sits in clear text.
            attrs["userPassword"] = hashed(HASHED_SALTED_SHA, spec.password)
        self._add(dn, attrs)
        return self._add_groups(dn, spec.groups)

    def _create_ad(self, spec: AccountSpec) -> list[str]:
        warnings: list[str] = []
        attrs = self._common(spec)
        attrs["userPrincipalName"] = spec.email
        attrs["userAccountControl"] = NORMAL_ACCOUNT | ACCOUNT_DISABLED

        # Two people can share a display name; AD keys entries by cn, so fall back to "Name (login)".
        dn = f"cn={escape_rdn(spec.display_name)},{spec.ou}"
        try:
            self._add(dn, attrs)
        except LoginTaken:
            if self.login_exists(spec.login):
                raise
            dn = f"cn={escape_rdn(f'{spec.display_name} ({spec.login})')},{spec.ou}"
            attrs["cn"] = f"{spec.display_name} ({spec.login})"
            self._add(dn, attrs)

        # AD only accepts passwords over an encrypted channel; enable the account once one is set.
        if spec.password and self.encrypted:
            pwd = f'"{spec.password}"'.encode("utf-16-le")
            ok = self.conn.modify(
                dn,
                {
                    "unicodePwd": [(MODIFY_REPLACE, [pwd])],
                    "pwdLastSet": [(MODIFY_REPLACE, [0])],  # must change at next logon
                    "userAccountControl": [(MODIFY_REPLACE, [NORMAL_ACCOUNT])],
                },
            )
            if not ok:
                spec.password = None
                warnings.append(f"account created disabled, password not set: {self.conn.result.get('message', '')}")
        elif spec.password:
            spec.password = None
            warnings.append("account created disabled: AD needs ldaps:// or start_tls to set passwords")

        return warnings + self._add_groups(dn, spec.groups)

    def _add_groups(self, dn: str, groups: list[str]) -> list[str]:
        warnings = []
        for group in groups:
            if not self.conn.modify(group, {"member": [(MODIFY_ADD, [dn])]}):
                warnings.append(f"could not add to {group}: {self.conn.result.get('description')}")
        return warnings
