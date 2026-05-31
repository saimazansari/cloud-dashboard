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
	port := getEnv("PORT", "8080")
	dbURL := getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/clouddashboard?sslmode=disable")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	pool, err := pgxpool.New(ctx, dbURL)
	if err != nil {
		log.Fatal("unable to connect to database:", err)
	}
	defer pool.Close()

	s := &Server{db: pool}

	if err := s.migrate(); err != nil {
		log.Fatal("migration failed:", err)
	}

	mux := http.NewServeMux()

	mux.HandleFunc("POST /api/register", s.Register)
	mux.HandleFunc("POST /api/login", s.Login)
	mux.HandleFunc("GET /api/resources", s.authMiddleware(s.ListResources))
	mux.HandleFunc("POST /api/resources", s.authMiddleware(s.CreateResource))
	mux.HandleFunc("PUT /api/resources/{id}", s.authMiddleware(s.UpdateResource))
	mux.HandleFunc("DELETE /api/resources/{id}", s.authMiddleware(s.DeleteResource))
	mux.HandleFunc("GET /api/cost-summary", s.authMiddleware(s.CostSummary))
	mux.HandleFunc("POST /api/deployments", s.authMiddleware(s.TriggerDeployment))
	mux.HandleFunc("GET /api/deployments", s.authMiddleware(s.ListDeployments))

	log.Printf("backend listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, corsMiddleware(mux)))
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func corsMiddleware(next http.Handler) http.Handler {
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

func (s *Server) authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userIDStr := r.Header.Get("X-User-ID")
		token := r.Header.Get("X-Auth-Token")
		if userIDStr == "" || token == "" {
			respondError(w, http.StatusUnauthorized, "missing auth headers")
			return
		}
		userID, err := strconv.Atoi(userIDStr)
		if err != nil {
			respondError(w, http.StatusUnauthorized, "invalid user id")
			return
		}
		valid, err := s.validateToken(r.Context(), userID, token)
		if err != nil || !valid {
			respondError(w, http.StatusUnauthorized, "invalid or expired token")
			return
		}
		next(w, r)
	}
}

func generateToken() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, msg string) {
	respondJSON(w, status, map[string]string{"error": msg})
}

func hashPassword(password string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	return string(b), err
}

func checkPassword(hash, password string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) == nil
}
