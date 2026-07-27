# Internal Artifact Visibility Design

Date: 2026-07-27
Status: approved by continuation of the release-blocker handoff
Implementation branch: `feat/agent-runtime-backends-verify`

## Problem

`continuous-episode.json` is a private diagnostic artifact containing the
research contract, model/tool events, provider traces, evidence hashes and
locators. It is currently registered like a public artifact and the direct
`/api/runs/{run_id}/artifacts/{name}` endpoint serves any file below the run
directory. Frontend flags such as `previewable` and `downloadable` are not an
authorization boundary.

## Selected design

The persisted Run artifact record gains one visibility value:

```text
public   — may appear in public Run/Artifact projections and may be downloaded
internal — retained for local audit but absent from public projections and denied by public content endpoints
```

The write default is `public` for backward compatibility. On read, explicit
visibility wins; an unknown/corrupt value fails closed to `internal`, and the
legacy exact path `continuous-episode.json` is classified as internal even when
old Run metadata has no visibility field. Other historical artifacts remain
public. `RunStore.add_artifact()` validates the value and records it atomically
with the artifact metadata.
`continuous-episode.json` is written as `internal`; `answer.md` and the already
redacted `report.json` remain public.

The public Run projection filters internal entries. `RunArtifactProvider`
does not discover them. The direct Run artifact endpoint serves only a
registered artifact whose visibility is public and whose `downloadable` flag
is true; arbitrary sibling files such as `run.json` are therefore also denied.
The generic Artifact registry inherits the same rule because internal Run
artifacts never enter it.

## Alternatives rejected

1. Set only `previewable=false` / `downloadable=false`: rejected because a
   caller can still request the path directly unless the server enforces the
   policy.
2. Move diagnostics to a second private server: stronger isolation, but adds a
   deployment and authentication surface that the current localhost product
   does not need.
3. Delete the diagnostic artifact: rejected because independent review,
   replay, provider accounting and evidence audits require it.

## Interface and ownership

- `RunStore` owns persisted visibility and validation.
- The Workbench public projection owns omission from Run responses.
- The Run artifact download endpoint owns access enforcement.
- `RunArtifactProvider` owns registry discovery and must ignore internal
  records.
- Callers choose visibility only when registering an artifact; they do not
  reimplement access checks.

This is a deep-module seam: one small visibility interface hides enforcement
across persistence, listing and content delivery.

## Error handling and compatibility

- Unknown visibility values fail at write time with `ValueError`.
- Missing visibility in historical Run JSON is interpreted as `public` except
  for the exact legacy private diagnostic path `continuous-episode.json`.
- Unknown persisted visibility fails closed to `internal`.
- Requests for internal, unregistered, non-downloadable or path-traversal
  artifacts return the same 404 surface so callers cannot enumerate private
  filenames.
- Private files remain readable by trusted local diagnostics through the
  filesystem/RunStore, not through public HTTP.

## Acceptance

1. An internal artifact persists in the private Run record.
2. Public Run/list/bootstrap responses omit it.
3. `/api/artifacts` does not discover it.
4. Both direct Run artifact download and registry content download reject it.
5. Public answer/report artifacts remain downloadable.
6. Existing historical Run fixtures remain readable.
