package beagle

import (
"context"

"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourcePool() *schema.Resource {
return &schema.Resource{
CreateContext: resourcePoolCreate,
ReadContext:   resourcePoolRead,
UpdateContext: resourcePoolUpdate,
DeleteContext: resourcePoolDelete,
Schema: map[string]*schema.Schema{
"pool_id":  {Type: schema.TypeString, Required: true, ForceNew: true},
"name":     {Type: schema.TypeString, Required: true},
"template": {Type: schema.TypeString, Required: true},
"size":     {Type: schema.TypeInt, Optional: true, Default: 1},
},
}
}

func resourcePoolCreate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
poolID := d.Get("pool_id").(string)
payload := map[string]any{
"pool_id":  poolID,
"name":     d.Get("name").(string),
"template": d.Get("template").(string),
"size":     d.Get("size").(int),
}
if _, err := client.request("POST", "/api/v1/pools", payload); err != nil {
return diag.FromErr(err)
}
d.SetId(poolID)
return resourcePoolRead(ctx, d, m)
}

func resourcePoolRead(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, err := client.request("GET", "/api/v1/pools/"+d.Id(), nil)
if err != nil {
d.SetId("")
return nil
}
return nil
}

func resourcePoolUpdate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
payload := map[string]any{}
if d.HasChange("name") {
payload["name"] = d.Get("name").(string)
}
if d.HasChange("template") {
payload["template"] = d.Get("template").(string)
}
if d.HasChange("size") {
payload["size"] = d.Get("size").(int)
}
if len(payload) > 0 {
if _, err := client.request("PUT", "/api/v1/pools/"+d.Id(), payload); err != nil {
return diag.FromErr(err)
}
}
return resourcePoolRead(ctx, d, m)
}

func resourcePoolDelete(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, _ = client.request("DELETE", "/api/v1/pools/"+d.Id(), nil)
d.SetId("")
return nil
}
