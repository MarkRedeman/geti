// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package grpc_gateway

import (
	"testing"
)

func TestHTTPRequestHeadersMatcher(t *testing.T) {
	tests := []struct {
		name       string
		input      string
		wantKey    string
		wantMatch  bool
	}{
		{
			name:      "canonical title-case header",
			input:     "X-Auth-Request-Access-Token",
			wantKey:   "x-auth-request-access-token",
			wantMatch: true,
		},
		{
			name:      "lowercase header (Traefik forwardAuth form)",
			input:     "x-auth-request-access-token",
			wantKey:   "x-auth-request-access-token",
			wantMatch: true,
		},
		{
			name:      "unrelated header is not matched",
			input:     "Content-Type",
			wantKey:   "Content-Type",
			wantMatch: false,
		},
		{
			name:      "authorization header is not matched",
			input:     "Authorization",
			wantKey:   "Authorization",
			wantMatch: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotKey, gotMatch := HTTPRequestHeadersMatcher(tt.input)
			if gotMatch != tt.wantMatch {
				t.Errorf("HTTPRequestHeadersMatcher(%q) match = %v, want %v", tt.input, gotMatch, tt.wantMatch)
			}
			if gotKey != tt.wantKey {
				t.Errorf("HTTPRequestHeadersMatcher(%q) key = %q, want %q", tt.input, gotKey, tt.wantKey)
			}
		})
	}
}
