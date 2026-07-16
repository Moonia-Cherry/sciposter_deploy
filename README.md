# SciPoster FastClaw Windows deployment

This directory is a self-contained Windows x64 deployment package for the
SciPoster FastClaw backend. It does not install a Windows service and it does
not modify the machine-wide `PATH`.

FastClaw v0.35.1 invokes its host command tool through `sh.exe`. The package
uses `runtime/shell` when bundled; otherwise Git for Windows must be installed.
The deployment scripts discover Git Bash automatically and modify only the
FastClaw child-process `PATH`.

## First deployment

1. Copy `config/deploy.example.json` to `config/deploy.local.json`.
2. Replace every `REPLACE_ME` value in the local file.
3. Open PowerShell in this directory and run `./deploy.ps1`.

The deployment binds FastClaw to `127.0.0.1:18953`, creates four agents,
installs their private skills, writes their role prompts, and creates a scoped
API key for the future middleware. The generated key is written only to
`config/deploy.local.json`.

Run `./deploy.ps1 -Reconcile` after changing `config/agents.json`, prompts, or
skill ZIP files. Daily process control uses `start.ps1`, `stop.ps1`, and
`status.ps1`; those scripts never reconcile configuration.

## Supported input formats

PDF, DOCX, TXT, and Markdown are supported. Legacy `.doc` parsing is available
only when Microsoft Word, LibreOffice, or `antiword` is already installed.

## Security boundary

Skills execute on the host because FastClaw sandboxing is disabled for this
package. Keep the service bound to loopback and expose it to a frontend only
through an authenticated middleware.

## Building releases

The Git repository intentionally excludes `bin/`, `runtime/`, and `build/`.
Deployable ZIP files are assembled in two stages on Windows x64.

First, create a versioned portable base from the locally verified FastClaw,
Python, and Node directories:

```powershell
./scripts/New-PortableBase.ps1 -Version 1.0.0
```

Create a GitHub Release named `base-v1.0.0`, upload the generated portable-base
ZIP and its `.sha256` file, then copy `dist/portable-base.lock.json` to
`release/portable-base.lock.json` and commit it.

To test final assembly locally before publishing:

```powershell
./scripts/Build-Release.ps1 `
  -Version 1.0.0 `
  -BaseLockFile dist/portable-base.lock.json `
  -BaseArchive dist/sciposter-portable-base-windows-amd64-1.0.0.zip
```

Commit tracked changes before running the final assembly script. It packages
deployment files from Git `HEAD` and rejects a dirty tracked working tree.

After the base lock is committed, push an application tag such as `v1.0.0`.
The GitHub Actions release workflow downloads the locked base, verifies its
SHA-256, builds the final package, runs the local E2E test, and publishes the
final ZIP and checksum. Tags beginning with `base-v` do not trigger this
workflow.

The final deployment package does not bundle `sh.exe`; Git for Windows remains
a deployment prerequisite.
