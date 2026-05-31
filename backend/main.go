package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
)

type Server struct {
	db *pgxpool.Pool
}

func main() {
	port := env("PORT", "8080")
	databaseURL := env("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/clouddashboard?sslmode=disable")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		log.Fatalf("cannot connect to database: %v", err)
	}
	defer pool.Close()

	server := &Server{db: pool}

	if err := server.migrate(); err != nil {
		log.Fatalf("database migration failed: %v", err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/register", server.Register)
	mux.HandleFunc("POST /api/login", server.Login)
	mux.HandleFunc("GET /api/resources", server.requireAuth(server.ListResources))
	mux.HandleFunc("GET /api/resources/{id}", server.requireAuth(server.GetResource))
	mux.HandleFunc("POST /api/resources", server.requireAuth(server.CreateResource))
	mux.HandleFunc("PUT /api/resources/{id}", server.requireAuth(server.UpdateResource))
	mux.HandleFunc("DELETE /api/resources/{id}", server.requireAuth(server.DeleteResource))
	mux.HandleFunc("POST /api/resources/batch", server.requireAuth(server.BatchAction))
	mux.HandleFunc("GET /api/cost-summary", server.requireAuth(server.CostSummary))
	mux.HandleFunc("POST /api/deployments", server.requireAuth(server.TriggerDeployment))
	mux.HandleFunc("GET /api/deployments", server.requireAuth(server.ListDeployments))
	mux.HandleFunc("GET /api/cost-history", server.requireAuth(server.CostHistory))

	log.Printf("server listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, cors(mux)))
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-User-ID, X-Auth-Token")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
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
