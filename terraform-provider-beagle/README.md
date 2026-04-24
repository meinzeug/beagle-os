# terraform-provider-beagle

Terraform provider skeleton for Beagle OS control-plane resources.

Implemented resources:
- `beagle_vm`
- `beagle_pool`
- `beagle_user`
- `beagle_network_zone`

Provider configuration:

```hcl
provider "beagle" {
  server = "http://127.0.0.1:9088"
  token  = var.beagle_token
}
```

This initial version uses direct REST calls against the Beagle control plane.
Registry publishing is intentionally tracked separately in GoFuture plan step 2.
