package beagle

import (
	"context"
	"net/http"
	"strconv"

	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceVM() *schema.Resource {
	return &schema.Resource{
		CreateContext: resourceVMCreate,
		ReadContext:   resourceVMRead,
		UpdateContext: resourceVMUpdate,
		DeleteContext: resourceVMDelete,
		Schema: map[string]*schema.Schema{
			"vmid": {Type: schema.TypeInt, Required: true, ForceNew: true},
			"name": {Type: schema.TypeString, Required: true},
			"node": {Type: schema.TypeString, Required: true},
			"template": {Type: schema.TypeString, Optional: true},
			"memory_mb": {Type: schema.TypeInt, Optional: true, Default: 4096},
			"cpu_cores": {Type: schema.TypeInt, Optional: true, Default: 2},
		},
	}
}

func resourceVMCreate(ctx context.Context, d *schema.ResourceData, m any) error {
	client := m.(*Client)
	vmid := d.Get("vmid").(int)
	payload := map[string]any{
		"vmid": vmid,
		"name": d.Get("name").(string),
		"node": d.Get("node").(string),
		"template": d.Get("template").(string),
		"memory_mb": d.Get("memory_mb").(int),
		"cpu_cores": d.Get("cpu_cores").(int),
	}
	if _, err := client.request("POST", "/api/v1/provisioning/vms", payload); err != nil {
		return err
	}
	d.SetId(strconv.Itoa(vmid))
	return resourceVMRead(ctx, d, m)
}

func resourceVMRead(_ context.Context, d *schema.ResourceData, m any) error {
	client := m.(*Client)
	status, data, err := client.requestWithStatus("GET", "/api/v1/virtualization/vms/"+d.Id(), nil)
	if err != nil {
		return err
	}
	if status == http.StatusNotFound {
		d.SetId("")
		return nil
	}
	if data != nil {
		if v, ok := data["name"].(string); ok {
			_ = d.Set("name", v)
		}
		if v, ok := data["node"].(string); ok {
			_ = d.Set("node", v)
		}
		if v, ok := data["memory_mb"].(float64); ok {
			_ = d.Set("memory_mb", int(v))
		}
		if v, ok := data["cpu_cores"].(float64); ok {
			_ = d.Set("cpu_cores", int(v))
		}
		if v, ok := data["template"].(string); ok {
			_ = d.Set("template", v)
		}
	}
	return nil
}

func resourceVMUpdate(ctx context.Context, d *schema.ResourceData, m any) error {
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
			return err
		}
	}
	return resourceVMRead(ctx, d, m)
}

func resourceVMDelete(_ context.Context, d *schema.ResourceData, m any) error {
	client := m.(*Client)
	_, _ = client.request("DELETE", "/api/v1/provisioning/vms/"+d.Id(), nil)
	d.SetId("")
	return nil
}
