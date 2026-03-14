// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package http

import (
	"errors"
	"net/http"
	"strings"
)

func BuildGetiCookie(r *http.Request) (http.Cookie, error) {
	value, err := getCookieValue(r)
	if err != nil {
		return http.Cookie{}, err
	}

	maxAge := getMaxAge(r)

	return http.Cookie{
		Name:     "geti-cookie",
		Value:    value,
		HttpOnly: true,
		Path:     "/",
		SameSite: http.SameSiteStrictMode,
		Secure:   isSecureRequest(r),
		MaxAge:   maxAge,
	}, nil
}

func isSecureRequest(r *http.Request) bool {
	if r.TLS != nil {
		return true
	}
	return strings.EqualFold(r.Header.Get("X-Forwarded-Proto"), "https")
}

func getCookieValue(r *http.Request) (string, error) {
	if r.Method == http.MethodDelete {
		return "", nil
	}

	authHeader := r.Header.Get("Authorization")
	if authHeader == "" {
		return "", errors.New("authorization header missing")
	}

	parts := strings.Split(authHeader, " ")
	if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
		return "", errors.New("invalid Authorization header format")
	}

	return parts[1], nil
}

func getMaxAge(r *http.Request) int {
	if r.Method == http.MethodDelete {
		return -1
	}

	return 0
}
