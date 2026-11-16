# Bifrost Docs

Bifrost Docs is an installable Bifrost Solution for organization-scoped operational
documentation. It provides native document authoring, folders, attachments,
configuration records, safe search, audit history, and an optional IT Glue migration
connector.

Native documentation works without IT Glue. Installers configure only the roles and
the Bifrost platform resources needed for their organization. IT Glue is an optional
one-way migration source for teams that have an existing IT Glue account.

## Install

Use Bifrost CLI 1.4.2 or later against the intended Bifrost instance:

```bash
git clone https://github.com/gobifrost/docs.git
cd docs
bifrost solution deploy . --global
```

Use `--org <organization>` when the Solution should be installed for one
organization. The install creates the Solution-owned tables, file locations,
workflows, agent, and app described by the manifests. It does not include table
rows, managed files, integration credentials, or customer data.

Assign the supplied `Bifrost Docs Reader`, `Bifrost Docs Editor`, and `Bifrost Docs
Administrator` roles before opening the app. Verify a non-administrator role after
install: platform administrators bypass normal policy checks and do not prove the
role configuration. Bifrost Docs requires the platform authorization behavior from
[Bifrost #791](https://github.com/gobifrost/bifrost/issues/791), which evaluates
both the existing row and the proposed row for updates, upserts, and batch writes.
Every installation still needs fresh role and file-policy verification; this package
does not claim that its roles have already been tested in your environment.

## Development

Bind the checkout to a non-production install, then use the platform-selected SDK:

```bash
bifrost solution bind --solution <install-id>
bifrost solution sdk update . --app bifrost-docs
bifrost solution start bifrost-docs
```

`bifrost solution start` supplies the selected instance, authentication, and
Solution scope through its local proxy. The app never commits an instance URL or
authentication token. The server-side Solution builder injects the API-matched web
SDK during deployment.

### Running the checks

The tests need the Bifrost SDKs that match the instance you deploy to. A Bifrost
instance serves both without authentication, so a clean machine or CI runner can
fetch them directly. Set `BIFROST_URL` to that instance, for example
`https://bifrost.example.com`, and run from the repository root:

```bash
export BIFROST_URL=https://bifrost.example.com

# Python tests: requirements.txt, test tooling, and the instance's `bifrost` Python SDK.
docker run --rm -e BIFROST_URL -v "$PWD:/workspace" -w /workspace python:3.13-slim \
  sh -lc 'pip install pytest pytest-asyncio pydantic pyyaml packaging -r requirements.txt \
    "$BIFROST_URL/api/cli/download/bifrost-cli.tar.gz" && python -m pytest -q tests'

# App tests and build (Node.js 22.12 or later).
npm --prefix apps/bifrost-docs ci
npm --prefix apps/bifrost-docs install --no-save "bifrost@$BIFROST_URL/api/sdk/download"
npm --prefix apps/bifrost-docs test
npm --prefix apps/bifrost-docs run build
```

The second `npm` command adds the instance's web SDK to `node_modules` only, as
`bifrost solution sdk update` does: `--no-save` keeps it out of `package.json` and
`package-lock.json`, while the lockfile still pins every other package. In a bound
checkout, `bifrost solution sdk update . --app bifrost-docs` installs the SDK for
you. Never commit the SDK dependency; the portability test rejects it.

## Optional IT Glue migration

The `IT Glue` connection in `.bifrost/connections.yaml` is optional. To migrate
existing records, a Docs Administrator configures its API key as an Integration
secret and maps each Bifrost organization to its IT Glue organization ID. The
migration is API-first, resumable, and one-way: it never downloads an account ZIP,
does not create organizations from names, and never migrates password or TOTP values.

Mapped source records preserve local edits until the source changes. Native Bifrost
records are not overwritten by the migration. Review the migration and rollback
checklist in [docs/CUTOVER_RUNBOOK.md](docs/CUTOVER_RUNBOOK.md) before a production
cutover.

## Optional AI profile

The Documentation Agent is included without a model selection. If your platform
requires an AI profile or model assignment, configure it after installation according
to your Bifrost instance policy. The agent searches only documentation data that the
caller is authorized to access and excludes passwords, TOTP secrets, integration
credentials, signed URLs, and protected ciphertext from its context.

## Security and support

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Use the public
project URL `https://github.com/gobifrost/docs` for issue tracking and releases.

This project is licensed under the [MIT License](LICENSE).
