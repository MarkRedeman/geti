// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package request_processor

import (
	"auth_proxy/app/cache"
	"context"
	"fmt"
	"strings"
	"time"
)

// AuthenticateBearerToken validates a raw Bearer token string (without "Bearer " prefix)
// and returns the signed Geti internal JWT string.  It reuses the same logic as the
// gRPC ext-proc path so there is no duplication of JWT / cache handling.
//
// path is used only for organisation-extraction from the URL; pass "" if not applicable.
func AuthenticateBearerToken(ctx context.Context, server *ExtProcServer, bearerToken string, path string) (string, error) {
	h := &RequestHandler{}
	h.Server = server
	h.Logger = &RequestProcessingLogger{
		basicLogger: logger,
	}
	h.Logger.Handler = h
	h.StreamContext = ctx
	h.JwtExternalString = ""
	h.GetiJwtSignedString = ""
	h.RequestID = GenerateRandomString(10)
	h.RequestPath = path

	jwtExternal, claimsExternal, err := ParseJwtString(bearerToken)
	if err != nil {
		return "", fmt.Errorf("failed to parse token: %v", err)
	}

	h.JwtExternalString = bearerToken

	// Check unauthorised URL list (anon JWT)
	for _, u := range server.UnauthorizedURLs {
		if u == path {
			getiJwt, err := h.CreateGetiAnonymJWT()
			if err != nil {
				return "", fmt.Errorf("failed to create anonymous Geti JWT: %v", err)
			}
			return getiJwt, nil
		}
	}

	// No auth-proxy config means on-prem: handle as external user request
	if server.AuthProxyConfig == nil {
		if err := h.handleExternalRequest(claimsExternal, bearerToken); err != nil {
			return "", err
		}
		return h.GetiJwtSignedString, nil
	}

	issuer, ok := claimsExternal["iss"].(string)
	if !ok {
		return "", fmt.Errorf("missing iss claim in token")
	}
	audience, ok := claimsExternal["aud"].(string)
	if !ok {
		// audience may also be a []interface{} slice; try that
		audList, ok2 := claimsExternal["aud"].([]interface{})
		if !ok2 || len(audList) == 0 {
			return "", fmt.Errorf("missing aud claim in token")
		}
		audience, ok = audList[0].(string)
		if !ok {
			return "", fmt.Errorf("aud claim is not a string")
		}
	}

	if issuer == server.AuthProxyConfig.IssInternal && audience == server.AuthProxyConfig.AudInternal {
		getiJwt, err := h.CreateIntelAdminJWT(jwtExternal, claimsExternal)
		if err != nil {
			return "", fmt.Errorf("intel admin JWT creation failed: %v", err)
		}
		return getiJwt, nil
	} else if issuer == server.AuthProxyConfig.IssExternal && audience == server.AuthProxyConfig.AudExternal {
		if err := h.handleExternalRequest(claimsExternal, bearerToken); err != nil {
			return "", err
		}
		return h.GetiJwtSignedString, nil
	}

	return "", fmt.Errorf("token issuer/audience does not match any known configuration")
}

// AuthenticateAPIKey validates an API key and returns the signed Geti internal JWT.
func AuthenticateAPIKey(ctx context.Context, server *ExtProcServer, apiKeyValue string, path string) (string, error) {
	h := &RequestHandler{}
	h.Server = server
	h.Logger = &RequestProcessingLogger{
		basicLogger: logger,
	}
	h.Logger.Handler = h
	h.StreamContext = ctx
	h.JwtExternalString = ""
	h.GetiJwtSignedString = ""
	h.RequestID = GenerateRandomString(10)
	h.RequestPath = path

	accessToken := AccessTokenHeader{}
	if err := accessToken.ParseHeaderValue(apiKeyValue); err != nil {
		return "", fmt.Errorf("unable to parse API key header value: %v", err)
	}
	if !accessToken.IsFormatValid() || !accessToken.IsChecksumValid() {
		return "", fmt.Errorf("invalid API key format or checksum")
	}

	patHash, err := accessToken.CalculateHash()
	if err != nil {
		return "", fmt.Errorf("unable to calculate hash of API key: %v", err)
	}

	// check cache first
	accessTokenCache, err := server.Cache.GetAccessTokenCache(patHash)
	if err == nil {
		if accessTokenCache.ErrorMsg != "" {
			return "", fmt.Errorf("cached error for access token: %s", accessTokenCache.ErrorMsg)
		}
		if accessTokenCache.ExpiresAt.Before(time.Now().UTC()) {
			return "", fmt.Errorf("access token is expired")
		}
		return accessTokenCache.GetiJWT, nil
	}

	token, err := h.dispatchGetPATRequest(patHash)
	if err != nil {
		newAccessTokenCache := cache.AccessTokenCache{
			GetiJWT:  "",
			ErrorMsg: err.Error(),
		}
		_ = server.Cache.SetAccessTokenCache(patHash, newAccessTokenCache)
		return "", fmt.Errorf("PAT lookup failed: %v", err)
	}

	getiJwt, err := h.CreateGetiJWTforPAT(token)
	if err != nil {
		return "", fmt.Errorf("failed to create Geti JWT for API key: %v", err)
	}

	newAccessTokenCache := cache.AccessTokenCache{
		AccessTokenData: token,
		GetiJWT:         getiJwt,
		ErrorMsg:        "",
	}
	_ = server.Cache.SetAccessTokenCache(patHash, newAccessTokenCache)

	return getiJwt, nil
}

// ExtractBearerToken strips the "Bearer " prefix from an Authorization header value.
// Returns the raw token and true on success.
func ExtractBearerToken(authHeader string) (string, bool) {
	parts := strings.SplitN(authHeader, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "bearer") {
		return "", false
	}
	return strings.TrimSpace(parts[1]), true
}
