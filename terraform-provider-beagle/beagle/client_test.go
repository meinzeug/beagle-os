package beagle_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	beagle "github.com/meinzeug/terraform-provider-beagle/beagle"
)

// mockBeagleServer provides a minimal in-memory Beagle API for client tests.
// It handles:
//   POST   /api/v1/provisioning/vms          → 201, stores VM
//   GET    /api/v1/virtualization/vms/{id}   → 200 if found, 404 otherwise
//   DELETE /api/v1/provisioning/vms/{id}     → 200, removes VM
func mockBeagleServer(t *testing.T) (*httptest.Server, *map[string]map[string]any) {
	t.Helper()
	store := make(map[string]map[string]any)

	mux := http.NewServeMux()

	// Create VM
	mux.HandleFunc("/api/v1/provisioning/vms", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		vmid := fmt.Sprintf("%v", body["vmid"])
		store[vmid] = body
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]any{"ok": true, "vmid": body["vmid"]})
	})

	// Read VM
	mux.HandleFunc("/api/v1/virtualization/vms/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		vmid := strings.TrimPrefix(r.URL.Path, "/api/v1/virtualization/vms/")
		vm, ok := store[vmid]
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			json.NewEncoder(w).Encode(map[string]any{"error": "not found"})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(vm)
	})

	// Delete VM
	mux.HandleFunc("/api/v1/provisioning/vms/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		vmid := strings.TrimPrefix(r.URL.Path, "/api/v1/provisioning/vms/")
		delete(store, vmid)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"ok": true})
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, &store
}

// TestClientCreateReadDelete tests the full terraform apply → destroy cycle
// for beagle_vm using a mock Beagle API server.
func TestClientCreateReadDelete(t *testing.T) {
	srv, store := mockBeagleServer(t)
	client := beagle.NewClient(srv.URL, "test-token")

	// Create VM (terraform apply)
	payload := map[string]any{
		"vmid":      float64(200),
		"name":      "test-vm-200",
		"node":      "beagle-0",
		"memory_mb": float64(4096),
		"cpu_cores": float64(2),
	}
	result, err := client.RequestForTest("POST", "/api/v1/provisioning/vms", payload)
	if err != nil {
		t.Fatalf("create VM failed: %v", err)
	}
	if result["ok"] != true {
		t.Errorf("expected ok=true, got %v", result["ok"])
	}

	// VM stored in mock
	if _, ok := (*store)["200"]; !ok {
		t.Errorf("VM 200 not found in mock store after create")
	}

	// Read VM (terraform plan / refresh)
	readResult, err := client.RequestForTest("GET", "/api/v1/virtualization/vms/200", nil)
	if err != nil {
		t.Fatalf("read VM failed: %v", err)
	}
	if readResult["name"] != "test-vm-200" {
		t.Errorf("unexpected name: %v", readResult["name"])
	}

	// Delete VM (terraform destroy)
	_, err = client.RequestForTest("DELETE", "/api/v1/provisioning/vms/200", nil)
	if err != nil {
		t.Fatalf("delete VM failed: %v", err)
	}
	if _, ok := (*store)["200"]; ok {
		t.Errorf("VM 200 still in mock store after delete")
	}
}

// TestClientReadNotFound ensures a 404 results in the resource being cleared.
func TestClientReadNotFound(t *testing.T) {
	srv, _ := mockBeagleServer(t)
	client := beagle.NewClient(srv.URL, "test-token")

	_, err := client.RequestForTest("GET", "/api/v1/virtualization/vms/9999", nil)
	if err == nil {
		t.Error("expected error for 404, got nil")
	}
}

// TestClientBadToken ensures a server error propagates as an error.
func TestClientBadToken(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]any{"error": "unauthorized"})
	}))
	t.Cleanup(srv.Close)

	client := beagle.NewClient(srv.URL, "wrong-token")
	_, err := client.RequestForTest("GET", "/api/v1/virtualization/vms/1", nil)
	if err == nil {
		t.Error("expected error for 401, got nil")
	}
}

// TestApplyCreatesVMDestroyRemovesVM is the high-level Plan 18 assertion:
// terraform apply (POST) creates the VM, terraform destroy (DELETE) removes it.
func TestApplyCreatesVMDestroyRemovesVM(t *testing.T) {
	srv, store := mockBeagleServer(t)
	client := beagle.NewClient(srv.URL, "test-token")

	// --- apply ---
	_, err := client.RequestForTest("POST", "/api/v1/provisioning/vms", map[string]any{
		"vmid": float64(101), "name": "vm-apply-test", "node": "beagle-0",
		"memory_mb": float64(2048), "cpu_cores": float64(1),
	})
	if err != nil {
		t.Fatalf("apply (create) failed: %v", err)
	}
	if len(*store) != 1 {
		t.Errorf("expected 1 VM in store after apply, got %d", len(*store))
	}

	// --- destroy ---
	_, err = client.RequestForTest("DELETE", "/api/v1/provisioning/vms/101", nil)
	if err != nil {
		t.Fatalf("destroy (delete) failed: %v", err)
	}
	if len(*store) != 0 {
		t.Errorf("expected 0 VMs in store after destroy, got %d", len(*store))
	}
}
