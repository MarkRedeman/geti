// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package http

import (
	"auth_proxy/app/jwk"
	"auth_proxy/app/request_processor"
	"auth_proxy/app/utils"
	"io"
	"net/http"
	"net/url"
)

var logger = utils.InitializeBasicLogger()

// extProcServer is the shared ExtProcServer instance initialised at startup.
// It holds the JWT TTL, cache, and optional AuthProxy configuration.
var extProcServer *request_processor.ExtProcServer

// SetExtProcServer wires the shared server instance for use by the forwardAuth handler.
func SetExtProcServer(s *request_processor.ExtProcServer) {
	extProcServer = s
}

type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func newLoggingResponseWriter(w http.ResponseWriter) *loggingResponseWriter {
	return &loggingResponseWriter{w, http.StatusOK}
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	lrw.statusCode = code
	lrw.ResponseWriter.WriteHeader(code)
}

func logRequestMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lrw := newLoggingResponseWriter(w)
		next.ServeHTTP(lrw, r)
		logger.Infof("Accessed route: %s %s, Response status: %d", r.Method, r.URL.Path, lrw.statusCode)
	})
}

func handleKeys(w http.ResponseWriter, r *http.Request) {
	response := jwk.GetJWKs()
	logger.Debugf("Sending JWKs response: %s", response)
	if _, err := io.WriteString(w, response); err != nil {
		logger.Errorf("Failed to write JWKs response: %v", err)
	}
}

func handleCookies(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost && r.Method != http.MethodDelete {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	cookie, err := BuildGetiCookie(r)
	if err != nil {
		logger.Error(err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	http.SetCookie(w, &cookie)
}

// handleForwardAuth implements a Traefik forwardAuth endpoint.
// It extracts a Bearer token from the Authorization header (falling back to the
// geti-cookie cookie), mints an internal Geti JWT and returns it in the
// x-auth-request-access-token response header so that Traefik can forward it to
// the upstream service (platform_account).
//
// Supported methods: GET, POST, HEAD (anything Traefik may use for forwardAuth).
func handleForwardAuth(w http.ResponseWriter, r *http.Request) {
	if extProcServer == nil {
		logger.Error("forwardAuth handler: ExtProcServer not initialised")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// 1. Resolve the raw bearer token: Authorization header takes priority,
	//    then fall back to the geti-cookie cookie value.
	var rawToken string

	authHeader := r.Header.Get("Authorization")
	if authHeader != "" {
		t, ok := request_processor.ExtractBearerToken(authHeader)
		if !ok {
			logger.Infof("forwardAuth: malformed Authorization header")
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		rawToken = t
	} else {
		cookie, err := r.Cookie("geti-cookie")
		if err != nil || cookie.Value == "" {
			logger.Infof("forwardAuth: neither Authorization header nor geti-cookie found")
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		rawToken = cookie.Value
	}

	// 2. Determine the original request path that Traefik is authorizing.
	// Traefik forwards it via X-Forwarded-Uri. Fall back to the current handler
	// path if the header is unavailable.
	requestPath := resolveForwardAuthPath(r)

	// 3. Mint the internal Geti JWT.
	getiJwt, err := request_processor.AuthenticateBearerToken(r.Context(), extProcServer, rawToken, requestPath)
	if err != nil {
		logger.Infof("forwardAuth: authentication failed: %v", err)
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	// 4. Return 200 with the internal token so Traefik forwards it upstream.
	w.Header().Set("x-auth-request-access-token", getiJwt)
	w.WriteHeader(http.StatusOK)
}

func resolveForwardAuthPath(r *http.Request) string {
	requestPath := r.URL.Path
	if forwardedURI := r.Header.Get("X-Forwarded-Uri"); forwardedURI != "" {
		if parsed, err := url.ParseRequestURI(forwardedURI); err == nil && parsed.Path != "" {
			requestPath = parsed.Path
		} else {
			logger.Warnf("forwardAuth: invalid X-Forwarded-Uri %q, using %q", forwardedURI, requestPath)
		}
	}

	return requestPath
}

func registerRoutes() {
	http.HandleFunc("/api/v1/keys/", handleKeys)
	http.HandleFunc("/api/v1/set_cookie", handleCookies)
	http.HandleFunc("/api/v1/auth", handleForwardAuth)
}

func StartServer(port string) {
	registerRoutes()

	address := ":" + port
	logger.Infof("Starting HTTP server on address %s", address)
	err := http.ListenAndServe(address, logRequestMiddleware(http.DefaultServeMux))
	if err != nil {
		logger.Fatalf("failed to listen: %v", err)
	}
}
