// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package http

import (
	"account_service/app/auth_proxy/request_processor"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestHandleForwardAuth_NoServer verifies that the handler returns 500 when the
// ExtProcServer has not been wired yet.
func TestHandleForwardAuth_NoServer(t *testing.T) {
	prev := extProcServer
	extProcServer = nil
	defer func() { extProcServer = prev }()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth", nil)
	rr := httptest.NewRecorder()

	HandleForwardAuth(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 when server is nil, got %d", rr.Code)
	}
}

// TestHandleForwardAuth_NoCredentials verifies that the handler returns 401 when
// neither an Authorization header nor a geti-cookie is present.
func TestHandleForwardAuth_NoCredentials(t *testing.T) {
	prev := extProcServer
	// Use a zero-value ExtProcServer; the nil-credential branch is reached before
	// any field of the server is accessed.
	extProcServer = &request_processor.ExtProcServer{}
	defer func() { extProcServer = prev }()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth", nil)
	rr := httptest.NewRecorder()

	HandleForwardAuth(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 when no credentials supplied, got %d", rr.Code)
	}
}

// TestHandleForwardAuth_MalformedAuthHeader verifies that a non-Bearer
// Authorization header value returns 401.
func TestHandleForwardAuth_MalformedAuthHeader(t *testing.T) {
	prev := extProcServer
	extProcServer = &request_processor.ExtProcServer{}
	defer func() { extProcServer = prev }()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth", nil)
	req.Header.Set("Authorization", "NotBearer abc123")
	rr := httptest.NewRecorder()

	HandleForwardAuth(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 for malformed auth header, got %d", rr.Code)
	}
}

// TestHandleForwardAuth_CookieFallback verifies that the handler accepts a
// geti-cookie when no Authorization header is present. Full JWT validation is
// expected to fail (invalid token) and return 401 — the important thing is that
// the cookie value is picked up (i.e. we don't get a 500).
func TestHandleForwardAuth_CookieFallback(t *testing.T) {
	prev := extProcServer
	extProcServer = &request_processor.ExtProcServer{}
	defer func() { extProcServer = prev }()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth", nil)
	req.AddCookie(&http.Cookie{Name: "geti-cookie", Value: "notavalidjwt"})
	rr := httptest.NewRecorder()

	HandleForwardAuth(rr, req)

	// JWT parsing will fail → 401; but we must NOT get 500 (which would mean the
	// cookie was never picked up or the server pointer was dereferenced while nil).
	if rr.Code == http.StatusInternalServerError {
		t.Errorf("unexpected 500: cookie value should have been read before server methods are called")
	}
}

func TestResolveForwardAuthPath(t *testing.T) {
	tests := []struct {
		name        string
		requestPath string
		forwarded   string
		want        string
	}{
		{
			name:        "uses forwarded uri path",
			requestPath: "/api/v1/auth",
			forwarded:   "/api/v1/profile?foo=bar",
			want:        "/api/v1/profile",
		},
		{
			name:        "falls back on invalid forwarded uri",
			requestPath: "/api/v1/auth",
			forwarded:   "::not-a-uri::",
			want:        "/api/v1/auth",
		},
		{
			name:        "falls back when header missing",
			requestPath: "/api/v1/auth",
			forwarded:   "",
			want:        "/api/v1/auth",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.requestPath, nil)
			if tt.forwarded != "" {
				req.Header.Set("X-Forwarded-Uri", tt.forwarded)
			}

			got := resolveForwardAuthPath(req)
			if got != tt.want {
				t.Errorf("resolveForwardAuthPath() = %q, want %q", got, tt.want)
			}
		})
	}
}
