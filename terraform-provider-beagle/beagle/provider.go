package beagle

import "github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"

func Provider() *schema.Provider {
	return &schema.Provider{
		Schema: map[string]*schema.Schema{
			"server": {
				Type:        schema.TypeString,
				Required:    true,
				Description: "Beagle API base URL, e.g. http://127.0.0.1:9088",
			},
			"token": {
				Type:        schema.TypeString,
				Required:    true,
				Sensitive:   true,
				Description: "Beagle API bearer token",
			},
		},
		ResourcesMap: map[string]*schema.Resource{
			"beagle_vm":           resourceVM(),
			"beagle_pool":         resourcePool(),
			"beagle_user":         resourceUser(),
			"beagle_network_zone": resourceNetworkZone(),
		},
		ConfigureContextFunc: providerConfigure,
	}
}
