# Beagle API Breaking-Change Policy

Stand: 2026-04-21

## Scope

This policy applies to all public control-plane endpoints under `/api/v1/*`.

## What is breaking

- Removing an endpoint.
- Renaming a path or required field.
- Changing field types in request or response payloads.
- Tightening auth/permission requirements for an existing endpoint without migration window.
- Changing semantic meaning of an existing field.

## What is non-breaking

- Adding new optional request fields.
- Adding new response fields.
- Adding new endpoints.
- Adding new enum values when clients are expected to ignore unknown values.

## Deprecation headers

For v1 endpoints planned for removal in v2, responses must include:

- `Deprecation: true`
- `Sunset: <RFC7231-date>`
- `Link: <https://beagle-os.com/api/migrations/v1-to-v2>; rel="deprecation"`

## Support window

- `/api/v1` remains supported for at least 12 months after `/api/v2` GA.
- Security fixes continue within that support window.

## Release discipline

- Any breaking v1 change must be blocked from release unless it is introduced as `/api/v2`.
- OpenAPI artifacts are regenerated before release and checked into repo.
