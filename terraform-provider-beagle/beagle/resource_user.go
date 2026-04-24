package beagle

import (
"context"

"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceUser() *schema.Resource {
return &schema.Resource{
CreateContext: resourceUserCreate,
ReadContext:   resourceUserRead,
UpdateContext: resourceUserUpdate,
DeleteContext: resourceUserDelete,
Schema: map[string]*schema.Schema{
"username":     {Type: schema.TypeString, Required: true, ForceNew: true},
"display_name": {Type: schema.TypeString, Required: true},
"role":         {Type: schema.TypeString, Optional: true, Default: "viewer"},
"password":     {Type: schema.TypeString, Required: true, Sensitive: true},
},
}
}

func resourceUserCreate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
username := d.Get("username").(string)
payload := map[string]any{
"username":     username,
"display_name": d.Get("display_name").(string),
"role":         d.Get("role").(string),
"password":     d.Get("password").(string),
}
if _, err := client.request("POST", "/api/v1/auth/users", payload); err != nil {
return diag.FromErr(err)
}
d.SetId(username)
return resourceUserRead(ctx, d, m)
}

func resourceUserRead(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
resp, err := client.request("GET", "/api/v1/auth/users/"+d.Id(), nil)
if err != nil {
d.SetId("")
return nil
}
if v, ok := resp["display_name"].(string); ok {
_ = d.Set("display_name", v)
}
if v, ok := resp["role"].(string); ok {
_ = d.Set("role", v)
}
return nil
}

func resourceUserUpdate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
payload := map[string]any{}
if d.HasChange("display_name") {
payload["display_name"] = d.Get("display_name").(string)
}
if d.HasChange("role") {
payload["role"] = d.Get("role").(string)
}
if d.HasChange("password") {
payload["password"] = d.Get("password").(string)
}
if len(payload) > 0 {
if _, err := client.request("PUT", "/api/v1/auth/users/"+d.Id(), payload); err != nil {
return diag.FromErr(err)
}
}
return resourceUserRead(ctx, d, m)
}

func resourceUserDelete(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, _ = client.request("DELETE", "/api/v1/auth/users/"+d.Id(), nil)
d.SetId("")
return nil
}
