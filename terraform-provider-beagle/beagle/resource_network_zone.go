package beagle

import (
"context"

"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceNetworkZone() *schema.Resource {
return &schema.Resource{
CreateContext: resourceNetworkZoneCreate,
ReadContext:   resourceNetworkZoneRead,
UpdateContext: resourceNetworkZoneUpdate,
DeleteContext: resourceNetworkZoneDelete,
Schema: map[string]*schema.Schema{
"zone_id":    {Type: schema.TypeString, Required: true, ForceNew: true},
"zone_name":  {Type: schema.TypeString, Required: true},
"vlan_id":    {Type: schema.TypeInt, Required: true},
"subnet":     {Type: schema.TypeString, Required: true},
"gateway":    {Type: schema.TypeString, Required: true},
"dhcp_start": {Type: schema.TypeString, Required: true},
"dhcp_end":   {Type: schema.TypeString, Required: true},
"dns_servers": {
Type:     schema.TypeList,
Optional: true,
Elem:     &schema.Schema{Type: schema.TypeString},
},
},
}
}

func resourceNetworkZoneCreate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
zoneID := d.Get("zone_id").(string)
payload := map[string]any{
"zone_id":     zoneID,
"zone_name":   d.Get("zone_name").(string),
"vlan_id":     d.Get("vlan_id").(int),
"subnet":      d.Get("subnet").(string),
"gateway":     d.Get("gateway").(string),
"dhcp_start":  d.Get("dhcp_start").(string),
"dhcp_end":    d.Get("dhcp_end").(string),
"dns_servers": d.Get("dns_servers").([]any),
}
if _, err := client.request("POST", "/api/v1/network/zones", payload); err != nil {
return diag.FromErr(err)
}
d.SetId(zoneID)
return resourceNetworkZoneRead(ctx, d, m)
}

func resourceNetworkZoneRead(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, err := client.request("GET", "/api/v1/network/zones/"+d.Id(), nil)
if err != nil {
d.SetId("")
return nil
}
return nil
}

func resourceNetworkZoneUpdate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
payload := map[string]any{}
if d.HasChange("zone_name") {
payload["zone_name"] = d.Get("zone_name").(string)
}
if d.HasChange("gateway") {
payload["gateway"] = d.Get("gateway").(string)
}
if d.HasChange("dhcp_start") {
payload["dhcp_start"] = d.Get("dhcp_start").(string)
}
if d.HasChange("dhcp_end") {
payload["dhcp_end"] = d.Get("dhcp_end").(string)
}
if d.HasChange("dns_servers") {
payload["dns_servers"] = d.Get("dns_servers").([]any)
}
if len(payload) > 0 {
if _, err := client.request("PUT", "/api/v1/network/zones/"+d.Id(), payload); err != nil {
return diag.FromErr(err)
}
}
return resourceNetworkZoneRead(ctx, d, m)
}

func resourceNetworkZoneDelete(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, _ = client.request("DELETE", "/api/v1/network/zones/"+d.Id(), nil)
d.SetId("")
return nil
}
