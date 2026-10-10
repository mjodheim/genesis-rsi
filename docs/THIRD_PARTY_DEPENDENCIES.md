# Third-party dependency and tooling audit

**Snapshot date: 12 August 2026.** Amended 19 August 2026 for `pytest-xdist`; amended 23 August
2026 for M102's planned use of the SQLite library exposed by Python's optional standard-library
`sqlite3` module. No declared Python package dependency changed.

This is the project's initial human-readable due-diligence inventory. It distinguishes software that
Mira Genesis directly declares as a Python dependency from tools, container images and operating
system packages used only to reproduce experiments or CI.

It is **not yet a complete legal SBOM** and it does not assert that every transitive component or
container package has been individually cleared for redistribution. A release-specific SPDX or
CycloneDX inventory should be generated before distributing a proprietary/commercial product that
bundles third-party software.

## 1. Declared Python package surface

`pyproject.toml` is the source of truth for the installable Python project at this snapshot.

| Component | Project use | Declaration | Licence observed at audit | Distribution note |
|---|---|---|---|---|
| Python | Runtime | `>=3.11` | PSF terms vary by release/component | Runtime prerequisite; determine bundling obligations if a commercial distribution embeds Python |
| setuptools | Build backend | `setuptools>=68` | MIT | Build-time dependency; not evidence that setuptools is redistributed with a Mira artefact |
| NumPy | Runtime dependency | `numpy` | Modified BSD / BSD-style | Direct runtime dependency and therefore part of any product-specific dependency review |
| pytest | Development/test | optional extra `dev` | MIT | Test dependency; ordinarily not a runtime component |
| pytest-xdist | Development/test — parallel execution of the existing suite | optional extra `dev` | MIT (`License-Expression: MIT`) | Test-runner plugin added 19 August 2026. Never imported by the project; invoked as `pytest -n <N> --dist loadscope`. Pulls `execnet` (MIT) transitively. Not a runtime component and not redistributed with any Mira artefact |

Primary upstream references checked for this audit:

- NumPy project/licensing statement: <https://numpy.org/about/>
- setuptools official repository: <https://github.com/pypa/setuptools>
- pytest official repository: <https://github.com/pytest-dev/pytest>
- pytest-xdist official repository: <https://github.com/pytest-dev/pytest-xdist>

The project CI already contains an integrity check intended to keep declared Python dependencies in
sync with imports. That is useful engineering evidence, but it is not a licence scanner.

## 2. CI-only infrastructure

The current GitHub Actions workflow uses:

- `actions/checkout@v6`;
- `actions/setup-python@v6`;
- `actions/setup-node@v6`;
- Python 3.11 and 3.13 test jobs;
- Node.js 20 for the Node/WebAssembly portion of repository integrity tests.

These actions/runtimes are used in GitHub-hosted CI. Their presence in a workflow does not by itself
mean that they are shipped in a Mira Genesis distribution. If the project later vendors an action,
runtime or binary, that new distribution relationship must be reviewed separately.

## 3. Real-environment experimental infrastructure

### M074 / Docker isolation

M074 invokes the Docker CLI/daemon to create disposable, network-disabled containers. Docker is an
external execution prerequisite for that experiment; it is not declared as a Python package and is
not copied into the Mira Python package by the repository.

### Defects4J validator image

`deploy/defects4j/Dockerfile` builds a local image from `ubuntu:22.04`, OpenJDK 11 and Defects4J
pinned at revision `8c16da8230843cdc918eaf4ddb449637f02b83c6`. Defects4J, its project repositories
and the tools its `init.sh` downloads are fetched at image build time and stay in the local image;
none of them is copied into this repository or redistributed by it. `genesis/defects4j_sandbox.py`
invokes the Docker CLI to run that image in disposable, network-disabled containers.

**Audit note:** the `ubuntu:22.04` base is named by tag, not by digest.

### External localization catalogue

`scripts/run_external_localization.py` reads a local checkout of GrowingBugRepository (MIT licence)
pinned at revision `f198b74b03c1a12b4acd842a7d6568fe5efdbf9a` and clones the public repositories of
the projects it lists. Patches, failure reports and sources stay in the local workspace; this
repository records case names, revisions and digests only.

### M081 / shell and HTTP service

M081 uses two pinned container bases:

- Alpine image: `alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc`;
- Python image: `python@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6`.

The shell arm uses a POSIX shell/filesystem in the Alpine container. The service arm runs a Python
HTTP server from experiment-authored source inside the Python container. The image digests are part
of experiment reproducibility, but the images contain many upstream packages whose notices and
licences must be obtained from the image itself if the image is ever redistributed rather than
pulled as an external prerequisite.

### M082 / browser environment

M082 builds `mira-m082-browser:1` from the pinned Microsoft Playwright image:

`mcr.microsoft.com/playwright@sha256:98b1ad488de36b22d41fdd1b0c5b9cceaa78a8d2661c6ab02d2108a07c182338`

The image build installs:

- `playwright@1.49.0` through npm;
- the browser binaries and operating-system dependencies supplied by the upstream Playwright image;
- Node.js as supplied by that environment.

The Playwright source repository is licensed under Apache-2.0. Browser binaries and packages inside
the container can have their own terms; the Playwright licence must therefore not be treated as a
single blanket licence for the entire image.

Upstream reference checked at audit:
<https://github.com/microsoft/playwright/blob/main/LICENSE>

M082 is an experimental container environment. If a future product ships this image or any of its
contents, generate a container-level SBOM and notice bundle for the **exact pinned image** before
release.

### M083 / X11 desktop environment

M083 builds `mira-m083-desktop:1` from `python:3.13-slim` and installs these Debian packages:

- `xvfb`;
- `x11-utils`;
- `xdotool`;
- `openbox`;
- `python3-tk`;
- `imagemagick`.

The experiment uses Xvfb, Openbox, Tk, xdotool, xwininfo and ImageMagick commands to create, control
and pixel-score a real X11 desktop session inside a container.

**Audit note:** unlike the pinned M081 and M082 bases, the M083 Dockerfile currently names
`python:3.13-slim` without a content digest. That historical experimental source should not be
silently rewritten merely to improve today's diligence record. For future private/commercial
images, pin the exact base digest before qualification and produce the package/notice inventory from
that realised image.

The Debian packages above have independent copyright/licence records. Do not infer their licences
from the base image name. If the M083-derived image is ever distributed, extract the applicable
`/usr/share/doc/*/copyright` records (and any upstream notices) from the exact built image and attach
them to the release compliance record.

### M102 / SQLite-backed interference environment

M102 plans to use Python's optional standard-library `sqlite3` module against disposable local
database files. Python's documentation states that the module requires the third-party SQLite
library; the exact SQLite version is supplied by the Python distribution and must be recorded in
the final M102 protocol and result. SQLite's official copyright record states that its deliverable
code and documentation are dedicated to the public domain.

Upstream references checked for this amendment:

- <https://docs.python.org/3/library/sqlite3.html>
- <https://www.sqlite.org/copyright.html>

M102 does not vendor SQLite source or binaries. SQLite remains an external component of the local
Python runtime. A product that embeds or redistributes Python/SQLite still requires an exact
release-specific runtime and notice review; the upstream public-domain statement is not rewritten
as a Mira Genesis licence.

## 4. Node.js and WebAssembly research

The repository contains Node ESM and WebAssembly experiments, and CI provisions Node.js 20 to
exercise them. Treat Node.js and any future Wasm engine/toolchain as external runtime/tooling unless
a product artefact actually embeds or redistributes them. A future commercial packaging decision
must state explicitly whether Node, a browser engine, a Wasm runtime, or generated Wasm modules are
bundled.

## 5. AI services are development tools, not package dependencies

OpenAI Codex, Anthropic Claude and OpenAI ChatGPT are recorded in
[`AI_ASSISTED_DEVELOPMENT_PROVENANCE.md`](AI_ASSISTED_DEVELOPMENT_PROVENANCE.md). They are not
currently declared runtime dependencies of the `mira-genesis` Python package merely because they
were used during development.

If a future product invokes a model/API at runtime, that service becomes part of the product's
contractual and operational dependency inventory and its then-current API/product terms must be
reviewed separately.

## 6. What this audit does not yet certify

This document does **not** yet certify:

- a complete transitive dependency graph;
- the package-level contents of every Docker base image;
- the licence of every Debian/Alpine package in the experimental images;
- browser-engine third-party notices inside the Playwright image;
- every benchmark, task bank or externally supplied future M085 asset;
- every historical external executable potentially present on a researcher's workstation;
- freedom to operate under patents or trademarks;
- that an AI-generated code fragment cannot resemble or derive from third-party code.

Those are separate questions from the small direct Python dependency surface.

## 7. Release/acquisition compliance procedure

Before any proprietary/commercial distribution or acquisition data-room snapshot:

1. choose the exact commit and product packaging boundary being diligenced;
2. lock/pin all direct runtime versions used by that artefact;
3. generate a machine-readable SPDX or CycloneDX SBOM for the Python/package layer;
4. if containers are distributed, scan the exact image digests and export package copyright/notices;
5. if Node/browser/Wasm runtimes are bundled, include their full notice trees and transitive packages;
6. review generated-code provenance for material, unusually distinctive or citation-signalled fragments;
7. classify each dependency as build-only, test-only, external prerequisite, dynamically obtained, or distributed;
8. preserve required notices/licence texts with the distributed artefact;
9. record unresolved copyleft, source-offer, attribution, patent or trademark questions before release;
10. archive the resulting SBOM, licence report, notices and source commit hash in the IP data room.

A future release-specific SBOM supersedes this document for the artefact it actually scans; this file
remains the repository-level starting inventory and records why experimental infrastructure must not
be conflated with the dependency surface of a commercial product.
