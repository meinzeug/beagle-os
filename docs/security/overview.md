# Security Assumptions

## Scope

This repository does not provide a complete identity, secret-rotation or fleet-enrollment layer.
It assumes infrastructure-provider access, Beagle Stream Server access and endpoint hardening are managed by the surrounding environment. At the moment, the main provider is Beagle host.

## Beagle host operator surface

- The browser extension only talks to the Beagle host origin the user is already authenticated against.
- The browser extension now centralizes Beagle API token lookup and optional session-scoped token storage in shared extension helpers instead of duplicating that logic inside `content.js`.
- The host-installed UI integration resolves Beagle profile data from Beagle host API state and VM metadata.
- VM description metadata is treated as administrator-controlled configuration.
- Beagle profile exports can contain Beagle Stream Server credentials when the operator stores them in VM metadata.

Operational implications:

- treat VM description metadata as sensitive administrative input
- limit who may edit or inspect Beagle-enabled VM descriptions
- prefer dedicated Beagle host roles for operators who manage Beagle endpoints
- when adding future providers, apply equivalent least-privilege controls instead of copying Beagle host assumptions into business logic

## Thin-client endpoint assumptions

- The endpoint is a controlled device with dedicated operational purpose.
- Local autologin is acceptable only on physically controlled hardware.
- Beagle stores runtime configuration locally on disk.
- Beagle Stream Server credentials and pairing data may be present on the endpoint if the deployment model requires unattended startup.

Recommended hardening:

- use a dedicated runtime user for the Beagle session
- restrict shell access for the endpoint account
- place endpoints in a network segment that can reach the active management provider and Beagle Stream Server, but not unnecessary destinations
- manage OS and package updates through standard patching workflows
- protect exported `endpoint.env` files and support bundles as operational secrets

## Control plane assumptions

- The Beagle control plane is intended to run behind the current infrastructure-provider boundary.
- Public health data may be exposed through the bundled HTTPS endpoint.
- Inventory endpoints should be treated as management APIs, not end-user APIs.

## Known non-goals in this baseline

- secure boot provisioning
- full disk encryption automation
- central secret rotation
- tenant-isolated multitenancy
- zero-touch hardware enrollment
