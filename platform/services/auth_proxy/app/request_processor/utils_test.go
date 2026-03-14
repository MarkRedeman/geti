// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package request_processor

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/assert"
)

func TestGenerateRandomString(t *testing.T) {
	str := GenerateRandomString(10)
	assert.Equal(t, 10, len(str))

	str = GenerateRandomString(0)
	assert.Equal(t, 0, len(str))
}

func TestGetAuthenticationTime(t *testing.T) {
	claims := jwt.MapClaims{
		"auth_time": float64(1633072800),
	}

	authTime, err := GetAuthenticationTime(claims)
	assert.NoError(t, err)
	assert.Equal(t, time.Unix(1633072800, 0), authTime)

	claims["auth_time"] = json.Number("1633072800")
	authTime, err = GetAuthenticationTime(claims)
	assert.NoError(t, err)
	assert.Equal(t, time.Unix(1633072800, 0), authTime)

	claims["auth_time"] = "invalid"
	_, err = GetAuthenticationTime(claims)
	assert.Error(t, err)
}

func TestExtractBearerToken(t *testing.T) {
	tests := []struct {
		name      string
		header    string
		wantToken string
		wantOk    bool
	}{
		{
			name:      "valid Bearer token",
			header:    "Bearer mytoken123",
			wantToken: "mytoken123",
			wantOk:    true,
		},
		{
			name:      "Bearer with extra whitespace",
			header:    "Bearer   spaced_token",
			wantToken: "spaced_token",
			wantOk:    true,
		},
		{
			name:      "case-insensitive bearer prefix",
			header:    "bearer mytoken",
			wantToken: "mytoken",
			wantOk:    true,
		},
		{
			name:      "missing bearer prefix",
			header:    "Basic somebase64==",
			wantToken: "",
			wantOk:    false,
		},
		{
			name:      "empty header",
			header:    "",
			wantToken: "",
			wantOk:    false,
		},
		{
			name:      "bearer only, no token",
			header:    "Bearer",
			wantToken: "",
			wantOk:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotToken, gotOk := ExtractBearerToken(tt.header)
			assert.Equal(t, tt.wantOk, gotOk)
			assert.Equal(t, tt.wantToken, gotToken)
		})
	}
}

