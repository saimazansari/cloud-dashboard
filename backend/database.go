package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"
)

type User struct {
	ID           int       `json:"id"`
	Username     string    `json:"username"`
	Email        string    `json:"email"`
	PasswordHash string    `json:"-"`
	Token        string    `json:"token,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
}

type Resource struct {
	ID             int               `json:"id"`
	UserID         int               `json:"user_id"`
	Name           string            `json:"name"`
	Type           string            `json:"type"`
	Region         string            `json:"region"`
	CostPerHour    float64           `json:"cost_per_hour"`
	Status         string            `json:"status"`
	Tags           map[string]string `json:"tags"`
	CreatedAt      time.Time         `json:"created_at"`
	UpdatedAt      time.Time         `json:"updated_at"`
	Sku            string            `json:"sku,omitempty"`
	ResourceGroup  string            `json:"resource_group,omitempty"`
	SubscriptionID string            `json:"subscription_id,omitempty"`
	CloudProvider  string            `json:"cloud_provider"`
}

type CostEntry struct {
	Date      string  `json:"date"`
	TotalCost float64 `json:"total_cost"`
}

type CostByProvider struct {
	Provider     string  `json:"provider"`
	Count        int     `json:"count"`
	TotalHourly  float64 `json:"total_hourly"`
	TotalMonthly float64 `json:"total_monthly"`
}

type CostSummary struct {
	TotalMonthly float64            `json:"total_monthly"`
	TotalHourly  float64            `json:"total_hourly"`
	ByType       []CostByType       `json:"by_type"`
	ByProvider   []CostByProvider   `json:"by_provider"`
	Resources    []ResourceWithCost `json:"resources"`
}

type CostByType struct {
	Type         string  `json:"type"`
	Count        int     `json:"count"`
	TotalHourly  float64 `json:"total_hourly"`
	TotalMonthly float64 `json:"total_monthly"`
}

type ResourceWithCost struct {
	Resource
	MonthlyCost float64 `json:"monthly_cost"`
}

func costPerHour(resourceType string) float64 {
	rates := map[string]float64{
		"Virtual Machine":     0.0860,
		"Storage Account":     0.0180,
		"Load Balancer":       0.0250,
		"Database":            0.0150,
		"Kubernetes Cluster":  0.1000,
		"Serverless Function": 0.0000,
		"CDN Profile":         0.0100,
		"Public IP":           0.0040,
		"Container Registry":  0.0050,
		"Managed Disk":        0.0100,
		"Virtual Network":     0.0,
		"Network Security Group": 0.0,
		"Key Vault":           0.0,
		"Network Watcher":     0.0,
		"Network Interface":   0.0,
		"Log Analytics":       0.0,
	}
	if rate, exists := rates[resourceType]; exists {
		return rate
	}
	return 0.0
}

func (s *Server) migrate() error {
	statements := []string{
		`CREATE TABLE IF NOT EXISTS users (
			id SERIAL PRIMARY KEY,
			username VARCHAR(100) UNIQUE NOT NULL,
			email VARCHAR(255) NOT NULL DEFAULT '',
			password_hash TEXT NOT NULL,
			token TEXT DEFAULT '',
			preferences JSONB DEFAULT '{}',
			created_at TIMESTAMP DEFAULT NOW()
		)`,
		`ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) NOT NULL DEFAULT ''`,
		`ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'`,
		`CREATE TABLE IF NOT EXISTS resources (
			id SERIAL PRIMARY KEY,
			user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
			name VARCHAR(255) NOT NULL,
			type VARCHAR(100) NOT NULL,
			region VARCHAR(100) DEFAULT 'us-east-1',
			cost_per_hour NUMERIC(10,4) DEFAULT 0,
			status VARCHAR(50) DEFAULT 'running',
			tags JSONB DEFAULT '{}',
			created_at TIMESTAMP DEFAULT NOW(),
			updated_at TIMESTAMP DEFAULT NOW()
		)`,
		`CREATE TABLE IF NOT EXISTS cost_history (
			id SERIAL PRIMARY KEY,
			user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
			date DATE NOT NULL,
			total_cost NUMERIC(12,4) NOT NULL,
			hourly_cost NUMERIC(10,4) NOT NULL,
			UNIQUE(user_id, date)
		)`,
	}

	for _, stmt := range statements {
		if _, err := s.db.Exec(context.Background(), stmt); err != nil {
			return fmt.Errorf("migration failed: %w", err)
		}
	}

	return nil
}

func (s *Server) createUser(ctx context.Context, username, email, passwordHash string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`INSERT INTO users (username, email, password_hash)
		 VALUES ($1, $2, $3)
		 RETURNING id, username, email, password_hash, token, created_at`,
		username, email, passwordHash,
	).Scan(&user.ID, &user.Username, &user.Email, &user.PasswordHash, &user.Token, &user.CreatedAt)
	return user, err
}

func (s *Server) getUserByUsername(ctx context.Context, username string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, email, password_hash, token, created_at
		 FROM users WHERE username = $1`,
		username,
	).Scan(&user.ID, &user.Username, &user.Email, &user.PasswordHash, &user.Token, &user.CreatedAt)
	return user, err
}

func (s *Server) findUserByEmail(ctx context.Context, email string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, email, password_hash, token, created_at
		 FROM users WHERE email = $1`,
		email,
	).Scan(&user.ID, &user.Username, &user.Email, &user.PasswordHash, &user.Token, &user.CreatedAt)
	return user, err
}

func (s *Server) findUserByGitHubID(ctx context.Context, githubID string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, email, password_hash, token, created_at
		 FROM users WHERE email = $1`,
		"github:"+githubID,
	).Scan(&user.ID, &user.Username, &user.Email, &user.PasswordHash, &user.Token, &user.CreatedAt)
	return user, err
}

func (s *Server) validateToken(ctx context.Context, userID int, token string) (bool, error) {
	var storedToken string
	err := s.db.QueryRow(ctx,
		`SELECT token FROM users WHERE id = $1`, userID,
	).Scan(&storedToken)
	if err != nil {
		return false, err
	}
	return storedToken == token, nil
}

func (s *Server) setToken(ctx context.Context, userID int, token string) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET token = $1 WHERE id = $2`, token, userID)
	return err
}

func (s *Server) listResources(ctx context.Context, userID int) ([]Resource, error) {
	rows, err := s.db.Query(ctx,
		`SELECT id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at
		 FROM resources WHERE user_id = $1
		 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var resources []Resource
	for rows.Next() {
		var resource Resource
		var tagsJSON []byte

		err := rows.Scan(
			&resource.ID, &resource.UserID, &resource.Name, &resource.Type,
			&resource.Region, &resource.CostPerHour, &resource.Status,
			&tagsJSON, &resource.CreatedAt, &resource.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}

		if err := json.Unmarshal(tagsJSON, &resource.Tags); err != nil {
			log.Printf("error unmarshalling tags: %v", err)
			resource.Tags = map[string]string{}
		} else if resource.Tags == nil {
			resource.Tags = map[string]string{}
		}

		resources = append(resources, resource)
	}
	return resources, nil
}

func (s *Server) updateResourceStatus(ctx context.Context, userID, resourceID int, status string) error {
	_, err := s.db.Exec(ctx,
		`UPDATE resources SET status=$1, updated_at=NOW() WHERE id=$2 AND user_id=$3`,
		status, resourceID, userID)
	return err
}

func (s *Server) batchAction(ctx context.Context, userID int, action string, ids []int) error {
	if len(ids) == 0 {
		return nil
	}

	var status string
	switch action {
	case "start":
		status = "running"
	case "stop":
		status = "stopped"
	case "terminate":
		status = "terminated"
	default:
		return fmt.Errorf("unknown action: %s", action)
	}

	_, err := s.db.Exec(ctx,
		`UPDATE resources SET status=$1, updated_at=NOW() WHERE id = ANY($2) AND user_id=$3`,
		status, ids, userID)
	return err
}

func (s *Server) getCostSummary(ctx context.Context, userID int) (CostSummary, error) {
	resources, err := s.listResources(ctx, userID)
	if err != nil {
		return CostSummary{}, err
	}

	var summary CostSummary
	grouped := make(map[string]*CostByType)
	providerGrouped := make(map[string]*CostByProvider)

	for _, resource := range resources {
		monthly := resource.CostPerHour * 730
		summary.TotalHourly += resource.CostPerHour
		summary.TotalMonthly += monthly

		entry := ResourceWithCost{Resource: resource, MonthlyCost: monthly}
		summary.Resources = append(summary.Resources, entry)

		if _, exists := grouped[resource.Type]; !exists {
			grouped[resource.Type] = &CostByType{Type: resource.Type}
		}
		grouped[resource.Type].Count++
		grouped[resource.Type].TotalHourly += resource.CostPerHour
		grouped[resource.Type].TotalMonthly += monthly

		provider := resource.CloudProvider
		if provider == "" {
			provider = "azure"
		}
		if _, exists := providerGrouped[provider]; !exists {
			providerGrouped[provider] = &CostByProvider{Provider: provider}
		}
		providerGrouped[provider].Count++
		providerGrouped[provider].TotalHourly += resource.CostPerHour
		providerGrouped[provider].TotalMonthly += monthly
	}

	for _, group := range grouped {
		summary.ByType = append(summary.ByType, *group)
	}

	for _, group := range providerGrouped {
		summary.ByProvider = append(summary.ByProvider, *group)
	}

	return summary, nil
}

func (s *Server) getCostHistory(ctx context.Context, userID int) ([]CostEntry, error) {
	s.seedCostHistory(ctx, userID)

	rows, err := s.db.Query(ctx,
		`SELECT date, total_cost FROM cost_history
		 WHERE user_id = $1
		 ORDER BY date ASC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []CostEntry
	for rows.Next() {
		var date time.Time
		var total float64
		if err := rows.Scan(&date, &total); err != nil {
			return nil, err
		}
		entries = append(entries, CostEntry{
			Date:      date.Format("2006-01-02"),
			TotalCost: total,
		})
	}
	if entries == nil {
		entries = []CostEntry{}
	}
	return entries, nil
}

func (s *Server) seedCostHistory(ctx context.Context, userID int) {
	var count int
	err := s.db.QueryRow(ctx,
		`SELECT COUNT(*) FROM cost_history WHERE user_id = $1`, userID).Scan(&count)
	if err != nil || count > 0 {
		return
	}

	resources, err := s.listResources(ctx, userID)
	if err != nil || len(resources) == 0 {
		return
	}

	var baseHourly float64
	for _, r := range resources {
		baseHourly += r.CostPerHour
	}

	now := time.Now()
	for i := 29; i >= 0; i-- {
		date := now.AddDate(0, 0, -i)
		hourly := baseHourly * (0.8 + float64(i%5)*0.05)
		daily := hourly * 24
		s.db.Exec(ctx,
			`INSERT INTO cost_history (user_id, date, total_cost, hourly_cost)
			 VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING`,
			userID, date.Format("2006-01-02"), daily, hourly)
	}
}

func (s *Server) updatePassword(ctx context.Context, userID int, newHash string) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET password_hash = $1 WHERE id = $2`, newHash, userID)
	return err
}

func (s *Server) getPreferences(ctx context.Context, userID int) (map[string]interface{}, error) {
	var prefsJSON []byte
	err := s.db.QueryRow(ctx,
		`SELECT preferences FROM users WHERE id = $1`, userID,
	).Scan(&prefsJSON)
	if err != nil {
		return nil, err
	}
	var prefs map[string]interface{}
	if len(prefsJSON) > 0 {
		if err := json.Unmarshal(prefsJSON, &prefs); err != nil {
			log.Printf("error unmarshalling preferences: %v", err)
		}
	}
	if prefs == nil {
		prefs = map[string]interface{}{}
	}
	return prefs, nil
}

func (s *Server) updatePreferences(ctx context.Context, userID int, prefs map[string]interface{}) error {
	data, err := json.Marshal(prefs)
	if err != nil {
		return fmt.Errorf("marshal preferences: %w", err)
	}
	_, err = s.db.Exec(ctx,
		`UPDATE users SET preferences = $1 WHERE id = $2`, string(data), userID)
	return err
}

func (s *Server) getResourceByID(ctx context.Context, userID, resourceID int) (Resource, error) {
	var resource Resource
	var tagsJSON []byte
	err := s.db.QueryRow(ctx,
		`SELECT id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at
		 FROM resources WHERE id = $1 AND user_id = $2`,
		resourceID, userID,
	).Scan(
		&resource.ID, &resource.UserID, &resource.Name, &resource.Type,
		&resource.Region, &resource.CostPerHour, &resource.Status,
		&tagsJSON, &resource.CreatedAt, &resource.UpdatedAt,
	)
	if err != nil {
		return Resource{}, err
	}
	if err := json.Unmarshal(tagsJSON, &resource.Tags); err != nil {
		log.Printf("error unmarshalling tags: %v", err)
		resource.Tags = map[string]string{}
	} else if resource.Tags == nil {
		resource.Tags = map[string]string{}
	}
	return resource, nil
}
