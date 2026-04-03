# Remaining `_resources` Audit

Date: 2026-04-03

## Scope

This audit covers the remaining untracked folders in the local
`_resources/` tree that were intentionally excluded from the clean
`codex/external-asset-migration-foundation` publication branch.

## Findings

### `._resources/.github`

- Contains one file: `profile/README.md`
- Status: already published in `zarishsphere/.github`
- Remote: `https://github.com/zarishsphere/.github`
- Decision: no further action required

### `_resources/zs-core-fhir-engine`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-core-fhir-r4-bridge`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-core-fhir-subscriptions`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-core-fhir-validator`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-core-fhirpath`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-pkg-go-fhir`

- Contains one file: `go.sum`
- File contents are only placeholder comments
- Decision: do not publish separately

### `_resources/zs-data-fhir-profiles`

- No publishable files found in the current local tree
- Decision: no action

### `_resources/zs-pkg-go-auth`

- No publishable files found in the current local tree
- Decision: no action

### `_resources/zs-pkg-go-db`

- No publishable files found in the current local tree
- Decision: no action

## Conclusion

No additional repository publication is required from the remaining local
`_resources/` folders.

The only meaningful asset in this remainder set was the organization profile
README, and it is already present in `zarishsphere/.github`.

The other remnants are placeholder or empty scaffold leftovers and should be
treated as local residue rather than source-of-truth assets.
