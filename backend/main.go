package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/security/keyvault/azsecrets"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
)

type Server struct {
	db                *pgxpool.Pool
	az                *AzureManager
	googleClientID    string
	githubClientID    string
	githubClientSecret string
	pendingStatuses   map[string]string
	pendingMu         sync.RWMutex
	mockResources     []Resource
	mockMu            sync.RWMutex
}

func (s *Server) setPendingStatus(azID, status string) {
	s.pendingMu.Lock()
	defer s.pendingMu.Unlock()
	if s.pendingStatuses == nil {
		s.pendingStatuses = make(map[string]string)
	}
	s.pendingStatuses[azID] = status
}

func (s *Server) clearPendingStatus(azID string) {
	s.pendingMu.Lock()
	defer s.pendingMu.Unlock()
	delete(s.pendingStatuses, azID)
}

func (s *Server) getPendingStatus(azID string) (string, bool) {
	s.pendingMu.RLock()
	defer s.pendingMu.RUnlock()
	st, ok := s.pendingStatuses[azID]
	return st, ok
}

type rateLimiter struct {
	mu   sync.Mutex
	data map[string]int
}

func newRateLimiter() *rateLimiter {
	rl := &rateLimiter{
		data: make(map[string]int),
	}
	go func() {
		for {
			time.Sleep(1 * time.Minute)
			rl.mu.Lock()
			rl.data = make(map[string]int)
			rl.mu.Unlock()
		}
	}()
	return rl
}

func (rl *rateLimiter) allow(key string, limit int) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.data[key]++
	return rl.data[key] <= limit
}

var (
	rlOnce sync.Once
	rlInst *rateLimiter
)

func main() {
	port := env("PORT", "8080")
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		log.Fatal("DATABASE_URL environment variable is required")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if kvURL := os.Getenv("AZURE_KEY_VAULT_URL"); kvURL != "" {
		pw, err := fetchSecret(ctx, kvURL, "db-password")
		if err != nil {
			log.Fatalf("key vault: %v", err)
		}
		databaseURL = injectDBPassword(databaseURL, pw)
		log.Println("database password sourced from Azure Key Vault")
	}

	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		log.Fatalf("cannot connect to database: %v", err)
	}
	defer pool.Close()

	server := &Server{
		db:                pool,
		googleClientID:    os.Getenv("GOOGLE_CLIENT_ID"),
		githubClientID:    os.Getenv("GITHUB_CLIENT_ID"),
		githubClientSecret: os.Getenv("GITHUB_CLIENT_SECRET"),
	}

	if server.googleClientID != "" {
		log.Println("Google OAuth enabled")
	} else {
		log.Println("GOOGLE_CLIENT_ID not set — Google sign-in disabled")
	}

	if subID := os.Getenv("AZURE_SUBSCRIPTION_ID"); subID != "" {
		az, err := NewAzureManager(subID)
		if err != nil {
			log.Printf("warning: Azure integration not available: %v", err)
		} else {
			server.az = az
			log.Println("Azure integration enabled")
		}
	}

	if err := server.migrate(); err != nil {
		log.Fatalf("database migration failed: %v", err)
	}

	server.initMockResources()

	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/register", server.Register)
	mux.HandleFunc("POST /api/login", server.Login)
	mux.HandleFunc("POST /api/auth/google", server.GoogleAuth)
	mux.HandleFunc("POST /api/auth/github", server.GitHubAuth)
	mux.HandleFunc("GET /api/resources", server.requireAuth(server.ListResources))
	mux.HandleFunc("GET /api/resources/{id}", server.requireAuth(server.GetResource))
	mux.HandleFunc("POST /api/resources/batch", server.requireAuth(server.BatchAction))
	mux.HandleFunc("POST /api/resources/{id}/stop", server.requireAuth(server.StopResource))
	mux.HandleFunc("POST /api/resources/{id}/start", server.requireAuth(server.StartResource))
	mux.HandleFunc("POST /api/resources/seed", server.requireAuth(server.SeedResources))
	mux.HandleFunc("GET /api/cost-summary", server.requireAuth(server.CostSummary))
	mux.HandleFunc("GET /api/cost-history", server.requireAuth(server.CostHistory))
	mux.HandleFunc("GET /api/subscriptions", server.requireAuth(server.ListSubscriptions))
	mux.HandleFunc("PUT /api/user/password", server.requireAuth(server.UpdatePassword))
	mux.HandleFunc("GET /api/user/preferences", server.requireAuth(server.GetPreferences))
	mux.HandleFunc("PUT /api/user/preferences", server.requireAuth(server.UpdatePreferences))
	mux.HandleFunc("GET /api/budget/status", server.requireAuth(server.BudgetStatus))

	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	handler := logging(recovery(rateLimit(cors(mux))))

	srv := &http.Server{
		Addr:           ":" + port,
		Handler:        handler,
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   20 * time.Second,
		IdleTimeout:    60 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}

	log.Printf("server listening on :%s", port)
	log.Fatal(srv.ListenAndServe())
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "http://"+r.Host || origin == "https://"+r.Host {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-User-ID, X-Auth-Token, X-Subscription-ID")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

type responseWriter struct {
	http.ResponseWriter
	status int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

func recovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				slog.Error("panic recovered", "error", fmt.Sprintf("%v", rec))
				http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func logging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &responseWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(wrapped, r)
		slog.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", wrapped.status,
			"duration", time.Since(start).String(),
		)
	})
}

func rateLimit(next http.Handler) http.Handler {
	rlOnce.Do(func() {
		rlInst = newRateLimiter()
	})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/login" || r.URL.Path == "/api/register" {
			ip := r.RemoteAddr
			if !rlInst.allow(ip, 10) {
				http.Error(w, "Too Many Requests", http.StatusTooManyRequests)
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Server) requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := r.Header.Get("X-User-ID")
		token := r.Header.Get("X-Auth-Token")

		if userID == "" || token == "" {
			writeError(w, http.StatusUnauthorized, "missing authentication headers")
			return
		}

		id, err := strconv.Atoi(userID)
		if err != nil {
			writeError(w, http.StatusUnauthorized, "invalid user id")
			return
		}

		valid, err := s.validateToken(r.Context(), id, token)
		if err != nil || !valid {
			writeError(w, http.StatusUnauthorized, "invalid or expired session token")
			return
		}

		next(w, r)
	}
}

func newSessionToken() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func hashPassword(plaintext string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(plaintext), bcrypt.DefaultCost)
	return string(hash), err
}

func checkPassword(hash, plaintext string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(plaintext)) == nil
}

type googleTokenPayload struct {
	Subject  string `json:"sub"`
	Email    string `json:"email"`
	Name     string `json:"name"`
	Picture  string `json:"picture"`
	Audience string `json:"aud"`
	Issuer   string `json:"iss"`
}

func verifyGoogleToken(ctx context.Context, idToken, clientID string) (*googleTokenPayload, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", "https://oauth2.googleapis.com/tokeninfo?id_token="+idToken, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("tokeninfo request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("tokeninfo returned status %d", resp.StatusCode)
	}

	var payload googleTokenPayload
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, fmt.Errorf("decode tokeninfo: %w", err)
	}

	if payload.Audience != clientID {
		return nil, fmt.Errorf("audience mismatch")
	}
	if payload.Issuer != "https://accounts.google.com" && payload.Issuer != "accounts.google.com" {
		return nil, fmt.Errorf("invalid issuer: %s", payload.Issuer)
	}

	return &payload, nil
}

type githubAccessToken struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
	Scope       string `json:"scope"`
}

type githubUser struct {
	ID    int    `json:"id"`
	Login string `json:"login"`
	Email string `json:"email"`
	Name  string `json:"name"`
}

func exchangeGitHubCode(ctx context.Context, code, clientID, clientSecret string) (ghID, username, email string, err error) {
	tokenURL := "https://github.com/login/oauth/access_token"
	payload := map[string]string{
		"client_id":     clientID,
		"client_secret": clientSecret,
		"code":          code,
	}
	body, _ := json.Marshal(payload)
	req, _ := http.NewRequestWithContext(ctx, "POST", tokenURL, bytes.NewReader(body))
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", "", "", fmt.Errorf("token exchange: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp githubAccessToken
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return "", "", "", fmt.Errorf("decode token response: %w", err)
	}
	if tokenResp.AccessToken == "" {
		return "", "", "", fmt.Errorf("empty access token")
	}

	userReq, _ := http.NewRequestWithContext(ctx, "GET", "https://api.github.com/user", nil)
	userReq.Header.Set("Authorization", "Bearer "+tokenResp.AccessToken)
	userReq.Header.Set("Accept", "application/json")

	userResp, err := http.DefaultClient.Do(userReq)
	if err != nil {
		return "", "", "", fmt.Errorf("user info: %w", err)
	}
	defer userResp.Body.Close()

	var ghUser githubUser
	if err := json.NewDecoder(userResp.Body).Decode(&ghUser); err != nil {
		return "", "", "", fmt.Errorf("decode user: %w", err)
	}

	ghID = strconv.Itoa(ghUser.ID)
	username = ghUser.Login
	email = ghUser.Email

	if ghUser.Name != "" {
		username = ghUser.Name
	}

	return ghID, username, email, nil
}

func fetchSecret(ctx context.Context, vaultURL, name string) (string, error) {
	cred, err := azidentity.NewDefaultAzureCredential(nil)
	if err != nil {
		return "", fmt.Errorf("credential: %w", err)
	}
	client, err := azsecrets.NewClient(vaultURL, cred, nil)
	if err != nil {
		return "", fmt.Errorf("client: %w", err)
	}
	resp, err := client.GetSecret(ctx, name, "", nil)
	if err != nil {
		return "", fmt.Errorf("get secret %q: %w", name, err)
	}
	if resp.Value == nil {
		return "", fmt.Errorf("secret %q is nil", name)
	}
	return *resp.Value, nil
}

func injectDBPassword(rawURL, password string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	user := u.User.Username()
	u.User = url.UserPassword(user, password)
	return u.String()
}
