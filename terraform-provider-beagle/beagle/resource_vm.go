package beagle

import (
"context"
"strconv"

"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceVM() *schema.Resource {
return &schema.Resource{
CreateContext: resourceVMCreate,
ReadContext:   resourceVMRead,
UpdateContext: resourceVMUpdate,
DeleteContext: resourceVMDelete,
Schema: map[string]*schema.Schema{
"vmid":      {Type: schema.TypeInt, Required: true, ForceNew: true},
"name":      {Type: schema.TypeString, Required: true},
"node":      {Type: schema.TypeString, Required: true},
"template":  {Type: schema.TypeString, Optional: true},
"memory_mb": {Type: schema.TypeInt, Optional: true, Default: 4096},
"cpu_cores": {Type: schema.TypeInt, Optional: true, Default: 2},
},
}
}

func resourceVMCreate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
vmid := d.Get("vmid").(int)
payload := map[string]any{
"vmid":      vmid,
"name":      d.Get("name").(string),
"node":      d.Get("node").(string),
"template":  d.Get("template").(string),
"memory_mb": d.Get("memory_mb").(int),
"cpu_cores": d.Get("cpu_cores").(int),
}
if _, err := client.request("POST", "/api/v1/provisioning/vms", payload); err != nil {
return diag.FromErr(err)
}
d.SetId(strconv.Itoa(vmid))
return resourceVMRead(ctx, d, m)
}

func resourceVMRead(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, err := client.request("GET", "/api/v1/virtualization/vms/"+d.Id(), nil)
if err != nil {
d.SetId("")
return nil
}
return nil
}

func resourceVMUpdate(ctx context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
payload := map[string]any{}
if d.HasChange("name") {
payload["name"] = d.Get("name").(string)
}
if d.HasChange("memory_mb") {
payload["memory_mb"] = d.Get("memory_mb").(int)
}
if d.HasChange("cpu_cores") {
payload["cpu_cores"] = d.Get("cpu_cores").(int)
}
if len(payload) > 0 {
if _, err := client.request("PUT", "/api/v1/provisioning/vms/"+d.Id(), payload); err != nil {
return diag.FromErr(err)
}
}
return resourceVMRead(ctx, d, m)
}

func resourceVMDelete(_ context.Context, d *schema.ResourceData, m any) diag.Diagnostics {
client := m.(*Client)
_, _ = client.request("DELETE", "/api/v1/provisioning/vms/"+d.Id(), nil)
d.SetId("")
return nil
}
