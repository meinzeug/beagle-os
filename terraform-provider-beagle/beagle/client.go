package beagle

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Client struct {
	baseURL string
	token   string
	http    *http.Client
}

func NewClient(baseURL, token string) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		token:   token,
		http: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *Client) request(method, path string, payload any) (map[string]any, error) {
	var body io.Reader
	if payload != nil {
		buf := &bytes.Buffer{}
		if err := json.NewEncoder(buf).Encode(payload); err != nil {
			return nil, err
		}
		body = buf
	}

	req, err := http.NewRequest(method, c.baseURL+path, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.token)
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("beagle API %s %s failed: %d %s", method, path, resp.StatusCode, string(respBody))
	}
	if len(respBody) == 0 {
		return map[string]any{"ok": true}, nil
	}

	decoded := map[string]any{}
	if err := json.Unmarshal(respBody, &decoded); err != nil {
		return nil, fmt.Errorf("invalid json response: %w", err)
	}
	return decoded, nil
}

// RequestForTest exposes the internal request method for unit tests.
func (c *Client) RequestForTest(method, path string, payload any) (map[string]any, error) {
	return c.request(method, path, payload)
}

// requestWithStatus makes a request and returns (httpStatusCode, body, err).
// Unlike request(), a 404 response does NOT return an error — the caller checks
// the status code. Other 4xx/5xx responses still return an error.
func (c *Client) requestWithStatus(method, path string, payload any) (int, map[string]any, error) {
	var body io.Reader
	if payload != nil {
		buf := &bytes.Buffer{}
		if err := json.NewEncoder(buf).Encode(payload); err != nil {
			return 0, nil, err
		}
		body = buf
	}

	req, err := http.NewRequest(method, c.baseURL+path, body)
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.token)
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, nil, err
	}

	if resp.StatusCode == http.StatusNotFound {
		return resp.StatusCode, nil, nil
	}
	if resp.StatusCode >= 400 {
		return resp.StatusCode, nil, fmt.Errorf("beagle API %s %s failed: %d %s", method, path, resp.StatusCode, string(respBody))
	}
	if len(respBody) == 0 {
		return resp.StatusCode, map[string]any{"ok": true}, nil
	}

	decoded := map[string]any{}
	if err := json.Unmarshal(respBody, &decoded); err != nil {
		return resp.StatusCode, nil, fmt.Errorf("invalid json response: %w", err)
	}
	return resp.StatusCode, decoded, nil
}
