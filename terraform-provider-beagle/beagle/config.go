package beagle

import (
	"context"

	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func providerConfigure(_ context.Context, d *schema.ResourceData) (any, diag.Diagnostics) {
	server := d.Get("server").(string)
	token := d.Get("token").(string)
	return NewClient(server, token), nil
}
