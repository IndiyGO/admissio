# admissio

*admissio* — Latin for "admission": the moment someone joins the company, and the moment their account should exist.

**Turn new-hire records from any HR system into ready-to-use Active Directory / LDAP accounts.**

Every company that grows has the same ticket on repeat: *"new employee starts Monday, please create their login."*
Someone copies a name from the HR tool, guesses a username, checks whether it's taken, picks the right OU,
adds groups, invents a password and emails it around. admissio does that whole loop from one command —
consistently, idempotently, and with a report you can audit.

```
HR export / API  ──►  normalize  ──►  pick login  ──►  place (OU, domain, groups)  ──►  AD / OpenLDAP
   (CSV, REST)        field map       free-slot        rules by branch/department        create + report
```

> 🇧🇷 **Em português:** o admissio lê as admissões do seu sistema de RH (planilha ou API), gera o login
> seguindo a regra da empresa (`primeiro.ultimo`, com alternativas quando já existe), escolhe a OU, o domínio
> de e-mail e os grupos por filial/departamento e cria a conta no Active Directory ou OpenLDAP. Pode rodar
> quantas vezes quiser: quem já tem conta é ignorado.

## Features

- **Any HR source** — CSV exports or any JSON REST API; map your column names in YAML, no code.
- **Packed exports** — BPM/workflow tools often cram everything into one column
  (`Person: Ana | Badge: 42 | Office: SP`); admissio unpacks it and filters by task type.
- **Login policy as config** — ordered patterns like `{first}.{last}` → `{second}.{last}` → `{first}.{last}{n}`,
  accent folding (`José D'Ávila` → `jose.davila`), name particles ignored (`da`, `dos`…), length limits that
  keep the numeric suffix.
- **Collision-safe** — checks the directory *and* the current batch; retries the next candidate if the
  directory rejects a duplicate.
- **Idempotent** — people are matched by employee ID (`employeeID` / `employeeNumber`), so re-runs never
  create duplicates. Schedule it with cron/Task Scheduler and forget it.
- **Placement rules** — OU, e-mail domain and groups chosen per branch/department (accent- and case-insensitive).
- **AD done right** — passwords only sent over verified LDAPS/StartTLS, *must change at next logon*, account
  stays disabled (and the report says so) if a password can't be set; handles two people with the same
  display name; ignores AD referrals.
- **No clear-text passwords in OpenLDAP** — `userPassword` is stored as a salted SHA hash.
- **Safe by default** — `--dry-run` shows exactly what would happen; strong random initial passwords; secrets
  come from environment variables; CSV report for auditing.

## Quick start (2 minutes, with a demo LDAP server)

```bash
git clone https://github.com/IndiyGO/admissio && cd admissio
docker compose up -d                 # OpenLDAP + web UI, pre-seeded with OUs, groups and one existing user
pip install -e .

admissio sync -c config.example.yaml --dry-run   # see the plan
admissio sync -c config.example.yaml             # create the accounts
```

Browse the result at http://localhost:8080 (`cn=admin,dc=example,dc=org` / `admin`).

The demo data deliberately includes the messy cases: an employee whose login is already taken, two
"João Oliveira"s, a name with accents and an apostrophe, a branch typed in caps, a duplicated row and a row
with no name.

| Input | Result |
|---|---|
| Ana Paula Souza (`ana.souza` already exists) | `paula.souza` |
| João Pedro de Oliveira / João Oliveira | `joao.oliveira` / `joao.oliveira2` |
| Maria José dos Santos D'Ávila | `maria.davila` |
| Lucas Ferreira, branch `SAO PAULO` | placed in the São Paulo OU and group |
| Duplicated row / empty name | reported as `duplicate` / `invalid`, nothing created |

No Docker? Set `directory.type: memory` to run everything offline.

## Commands

| Command | What it does |
|---|---|
| `admissio sync -c config.yaml [--dry-run]` | Read hires, create missing accounts, write a report |
| `admissio check -c config.yaml` | Validate config, read the source, test the directory bind |
| `admissio logins "João Pedro de Oliveira"` | Show the login candidates for a name, in order |

## Configuration

Everything lives in one YAML file — see [`config.example.yaml`](config.example.yaml) (CSV + OpenLDAP, with
commented AD and REST examples) and [`examples/bpm_export.yaml`](examples/bpm_export.yaml) (packed workflow
export). Values can reference environment variables: `${AD_PASSWORD}` or `${LDAP_URL:-ldap://localhost}`.

Active Directory in short:

```yaml
directory:
  type: ldap
  flavor: ad
  url: ldaps://dc01.corp.example.com
  auth: ntlm
  bind_dn: CORP\svc-provisioning
  bind_password: ${AD_PASSWORD}
  base_dn: DC=corp,DC=example,DC=com
  ca_file: corp-root-ca.pem   # optional: internal CA; certificates are always verified
```

Give the service account only *Create user objects* on the target OUs and *Write member* on the groups it manages.

## Architecture

```
src/admissio/
  sources/        CSV and REST readers → NewHire (field mapping, unpacking, filters)
  logins.py       pattern-based login candidates
  rules.py        branch/department → OU, e-mail domain, groups
  engine.py       the sync loop (idempotency, collisions, dry-run)
  directories/    Directory protocol + LDAP (AD/OpenLDAP) and in-memory implementations
  report.py       CSV audit report
  cli.py          Typer CLI
```

Adding a target (Google Workspace, Entra ID, Keycloak…) means implementing three methods:
`login_exists`, `find_by_employee_id`, `create_user`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests cover login generation, collision handling, idempotency, rules, CSV/REST sources, both example configs,
and OpenLDAP and Active Directory round-trips against ldap3's mock servers — no real directory needed.

## Roadmap

- Deliver initial passwords by e-mail/Teams/Slack to the manager instead of a report file
- Offboarding: disable accounts from HR termination records
- Microsoft Entra ID and Google Workspace targets
- Paginated REST sources

## License

MIT
