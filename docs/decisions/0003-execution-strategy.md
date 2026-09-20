# ADR 0003: Execution strategy for Nextflow/nf-core on the user's Windows machine

Date: 2026-09-20
Status: Accepted

## Context

PROJECT_MASTER_SPEC.md section 29 asks for a reproducible environment
strategy, offering "WSL2 + Docker Desktop" as the primary suggested option
and explicitly says not to make Docker mandatory if it makes development
unnecessarily difficult on the user's machine. This had to be decided
before Milestone 5 (first end-to-end sample) can be attempted.

The user initially asked whether Docker could be used *without* WSL2 at
all, preferring to avoid touching WSL2/virtualization settings mainly for
simplicity (not because of an active conflict, though the user does have
VirtualBox installed for other scientific tools, e.g. CNApy/COPASI-related
work).

## Research findings (2026-09-20)

1. Nextflow's own documentation states it runs "on any POSIX-compatible
   system (Linux, macOS, etc), and on Windows through WSL" — there is no
   supported native-Windows execution path for Nextflow itself.
   https://docs.seqera.io/nextflow/install
2. Docker Desktop *can* run without WSL2 using a Hyper-V backend, but only
   in "Windows containers" mode in that configuration — which cannot run
   the Linux-based bioinformatics containers nf-core publishes (Salmon,
   fastp, STAR, etc. are all Linux images). So "Docker without WSL2" does
   not actually solve our problem on its own.
   https://hitoritech.com/blog/how-to-install-docker-on-windows-without-wsl/
3. Docker Desktop for Windows defaults to the WSL2 backend whenever WSL2 is
   available on the machine, and this is Docker's own recommended
   configuration (better file-sharing performance, faster cold starts,
   dynamic resource allocation). A Hyper-V backend remains available mainly
   for stricter kernel-isolation/security requirements, which do not apply
   here. https://docs.docker.com/desktop/features/wsl/
4. The user confirmed Docker Desktop is **already installed and working**
   on this machine ("usei recentemente umas ferramentas por lá"). Per
   finding 3, it is almost certainly already running on the WSL2 backend,
   meaning the WSL2 subsystem itself is likely already present on this
   machine as a side effect of installing Docker Desktop, even though the
   user has not directly opened a WSL2 shell.
5. The standard community-documented setup for Nextflow on Windows (Seqera
   blog) is: enable WSL2 → install an Ubuntu distro from the Microsoft
   Store → install Docker Desktop with WSL2 integration enabled for that
   distro → install Java/curl/Nextflow inside the Ubuntu distro → run
   `nextflow` from there. https://seqera.io/blog/setup-nextflow-on-windows/

## Decision

Use the existing Docker Desktop installation as the container engine
(`-profile docker` for `nf-core/fetchngs` and `nf-core/rnaseq`), with
Nextflow itself running inside a WSL2 Ubuntu distro that has Docker
Desktop's WSL integration enabled for it. This is recorded in
`config/pipeline.yaml` (`execution.profile: docker`,
`execution.container_engine: docker_desktop_wsl2`,
`execution.runs_inside: wsl2_ubuntu`).

This avoids introducing a *new* virtualization stack: Docker Desktop has
already brought whatever Hyper-V/WSL2 plumbing it needs onto this machine,
and does not need Hyper-V configured separately from that. The only
remaining setup step is adding a general-purpose Ubuntu WSL2 distro (Docker
Desktop's own internal WSL2 distros are not meant to be used as a general
shell) and enabling Docker Desktop's integration toggle for it — normally a
single `wsl --install -d Ubuntu` command plus one checkbox in Docker
Desktop's settings, not a from-scratch WSL2/Hyper-V setup.

### Alternatives considered and rejected

- **Docker Desktop in Windows-containers/Hyper-V mode, no WSL2**: rejected
  — cannot run the Linux containers nf-core publishes (finding 2).
- **Full Ubuntu VM under VirtualBox (which the user already has) + Docker
  Engine inside it, avoiding WSL2 entirely**: technically workable and was
  offered as an option, but the user's stated reason for avoiding WSL2 was
  general simplicity, not an actual VirtualBox/Hyper-V conflict, and would
  have meant setting up and maintaining a second, heavier virtualization
  stack alongside the Docker Desktop install that already works. Rejected
  in favor of reusing what already works.
- **Conda/Mamba instead of containers**: rejected for now because the user
  has a working Docker Desktop install and prefers it (see the "Docker vs
  Conda" decision in this same conversation); Conda remains a documented
  fallback in `pyproject.toml`'s `discovery` extra and in
  PROJECT_MASTER_SPEC.md section 29 if container-specific issues come up
  later.

## Follow-up (tracked in TODO.md)

- Confirm Docker Desktop's Settings > General has "Use the WSL 2 based
  engine" checked.
- Install a general-purpose Ubuntu WSL2 distro if one is not already
  present (`wsl --install -d Ubuntu` in an elevated PowerShell), and enable
  it under Docker Desktop > Settings > Resources > WSL integration.
- Install Java + Nextflow inside that Ubuntu distro.
- Only then attempt Milestone 5 (first end-to-end sample), which is the
  first milestone that actually invokes Nextflow.
