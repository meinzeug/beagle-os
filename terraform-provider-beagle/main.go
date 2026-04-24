package main

import (
	"github.com/hashicorp/terraform-plugin-sdk/v2/plugin"
	"github.com/meinzeug/terraform-provider-beagle/beagle"
)

func main() {
	plugin.Serve(&plugin.ServeOpts{
		ProviderFunc: beagle.Provider,
	})
}
