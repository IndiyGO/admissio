from ldap3 import MOCK_SYNC, OFFLINE_AD_2012_R2, OFFLINE_SLAPD_2_4, Connection, Server

from admissio.config import DirectoryConfig, Placement, RulesConfig
from admissio.directories.ldap import LdapDirectory
from admissio.engine import sync
from admissio.logins import LoginGenerator
from admissio.models import AccountSpec, NewHire, Status
from admissio.rules import Rules

BASE = "dc=example,dc=org"
ADMIN = f"cn=admin,{BASE}"


def mock_connection() -> Connection:
    server = Server("mock", get_info=OFFLINE_SLAPD_2_4)
    conn = Connection(server, user=ADMIN, password="admin", client_strategy=MOCK_SYNC)
    conn.strategy.add_entry(ADMIN, {"userPassword": "admin", "sn": "admin"})
    conn.strategy.add_entry(f"ou=people,{BASE}", {"objectClass": ["organizationalUnit"], "ou": "people"})
    conn.strategy.add_entry(
        f"uid=ana.souza,ou=people,{BASE}",
        {
            "objectClass": ["inetOrgPerson"],
            "uid": "ana.souza",
            "cn": "Ana Souza",
            "sn": "Souza",
            "employeeNumber": "E0042",
        },
    )
    conn.strategy.add_entry(f"cn=staff,{BASE}", {"objectClass": ["groupOfNames"], "cn": "staff", "member": [ADMIN]})
    conn.bind()
    return conn


def test_openldap_create_and_lookup():
    conn = mock_connection()
    directory = LdapDirectory(DirectoryConfig(flavor="openldap", base_dn=BASE), connection=conn)

    assert directory.login_exists("ana.souza")
    assert directory.find_by_employee_id("E0042") == "ana.souza"

    rules = Rules(
        RulesConfig(default=Placement(email_domain="example.org", ou=f"ou=people,{BASE}", groups=[f"cn=staff,{BASE}"]))
    )
    gen = LoginGenerator(["{first}.{last}", "{second}.{last}", "{first}.{last}{n}"])
    results = sync([NewHire("E1", "Ana Souza", title="Analyst")], directory, rules, gen, lambda: "Pw-1")

    assert results[0].status is Status.CREATED, results[0].message
    assert results[0].login == "ana.souza2"
    assert directory.find_by_employee_id("E1") == "ana.souza2"

    conn.search(f"cn=staff,{BASE}", "(objectClass=*)", attributes=["member"])
    assert f"uid=ana.souza2,ou=people,{BASE}" in conn.entries[0].member.values


def test_openldap_password_is_hashed():
    conn = mock_connection()
    directory = LdapDirectory(DirectoryConfig(flavor="openldap", base_dn=BASE), connection=conn)
    spec = AccountSpec(
        login="lucas.ferreira",
        display_name="Lucas Ferreira",
        given_name="Lucas",
        surname="Ferreira",
        email="lucas.ferreira@example.org",
        ou=f"ou=people,{BASE}",
        employee_id="E9",
        password="Secret-123",
    )
    directory.create_user(spec)
    conn.search(f"uid=lucas.ferreira,ou=people,{BASE}", "(objectClass=*)", attributes=["userPassword"])
    stored = conn.entries[0].userPassword.value
    stored = stored.decode() if isinstance(stored, bytes) else stored
    assert stored.lower().startswith("{ssha}")
    assert "Secret-123" not in stored


def ad_directory(encrypted: bool) -> tuple[LdapDirectory, Connection]:
    root = "DC=corp,DC=example,DC=com"
    server = Server("mock-ad", get_info=OFFLINE_AD_2012_R2)
    conn = Connection(server, user="CN=svc,DC=corp,DC=example,DC=com", password="x", client_strategy=MOCK_SYNC)
    conn.strategy.add_entry("CN=svc,DC=corp,DC=example,DC=com", {"userPassword": "x", "sn": "svc"})
    conn.strategy.add_entry(f"OU=Staff,{root}", {"objectClass": ["organizationalUnit"], "ou": "Staff"})
    conn.strategy.add_entry(
        f"CN=Ana Souza,OU=Staff,{root}",
        {"objectClass": ["user"], "cn": "Ana Souza", "sAMAccountName": "ana.souza", "employeeID": "E0042"},
    )
    conn.bind()
    cfg = DirectoryConfig(flavor="ad", base_dn=root)
    return LdapDirectory(cfg, connection=conn, encrypted=encrypted), conn


def ad_spec(**kw) -> AccountSpec:
    base = dict(
        login="ana.souza2",
        display_name="Ana Souza",
        given_name="Ana",
        surname="Souza",
        email="ana.souza2@example.com",
        ou="OU=Staff,DC=corp,DC=example,DC=com",
        employee_id="E1",
        password="Secret-123",
    )
    return AccountSpec(**(base | kw))


def test_ad_same_display_name_gets_disambiguated_cn():
    directory, conn = ad_directory(encrypted=True)
    directory.create_user(ad_spec())
    assert directory.find_by_employee_id("E1") == "ana.souza2"
    conn.search("OU=Staff,DC=corp,DC=example,DC=com", "(employeeID=E1)", attributes=["cn"])
    assert conn.entries[0].cn.value == "Ana Souza (ana.souza2)"


def test_ad_without_tls_creates_disabled_account_and_drops_password():
    directory, conn = ad_directory(encrypted=False)
    spec = ad_spec(display_name="Bruno Lima", login="bruno.lima", employee_id="E2")
    warnings = directory.create_user(spec)
    assert spec.password is None
    assert any("disabled" in w for w in warnings)
    conn.search("OU=Staff,DC=corp,DC=example,DC=com", "(employeeID=E2)", attributes=["userAccountControl"])
    assert int(conn.entries[0].userAccountControl.value) & 0x2  # ACCOUNT_DISABLED
