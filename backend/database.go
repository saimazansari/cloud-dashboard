package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

type User struct {
	ID           int       `json:"id"`
	Username     string    `json:"username"`
	PasswordHash string    `json:"-"`
	Token        string    `json:"token,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
}

type Resource struct {
	ID          int               `json:"id"`
	UserID      int               `json:"user_id"`
	Name        string            `json:"name"`
	Type        string            `json:"type"`
	Region      string            `json:"region"`
	CostPerHour float64           `json:"cost_per_hour"`
	Status      string            `json:"status"`
	Tags        map[string]string `json:"tags"`
	CreatedAt   time.Time         `json:"created_at"`
	UpdatedAt   time.Time         `json:"updated_at"`
}

type Deployment struct {
	ID          int        `json:"id"`
	UserID      int        `json:"user_id"`
	ResourceIDs []int      `json:"resource_ids"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
}

type CostSummary struct {
	TotalMonthly float64            `json:"total_monthly"`
	TotalHourly  float64            `json:"total_hourly"`
	ByType       []CostByType       `json:"by_type"`
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

func defaultCostPerHour(resourceType string) float64 {
	costs := map[string]float64{
		"Virtual Machine":    0.0860,
		"Storage Account":    0.0180,
		"Load Balancer":      0.0250,
		"Database":           0.0150,
		"Kubernetes Cluster": 0.1000,
		"Serverless Function": 0.0000,
		"CDN Profile":        0.0100,
	}
	if c, ok := costs[resourceType]; ok {
		return c
	}
	return 0.01
}

func (s *Server) migrate() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS users (
			id SERIAL PRIMARY KEY,
			username VARCHAR(100) UNIQUE NOT NULL,
			password_hash TEXT NOT NULL,
			token TEXT DEFAULT '',
			created_at TIMESTAMP DEFAULT NOW()
		)`,
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
		`CREATE TABLE IF NOT EXISTS deployments (
			id SERIAL PRIMARY KEY,
			user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
			resource_ids JSON DEFAULT '[]',
			status VARCHAR(50) DEFAULT 'pending',
			created_at TIMESTAMP DEFAULT NOW(),
			completed_at TIMESTAMP
		)`,
	}
	for _, q := range queries {
		if _, err := s.db.Exec(context.Background(), q); err != nil {
			return err
		}
	}
	_, err := s.db.Exec(context.Background(),
		`ALTER TABLE resources ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '{}'`)
	return err
}

func (s *Server) createUser(ctx context.Context, username, passwordHash string) (User, error) {
	var u User
	err := s.db.QueryRow(ctx,
		`INSERT INTO users (username, password_hash) VALUES ($1, $2)
		 RETURNING id, username, password_hash, token, created_at`,
		username, passwordHash,
	).Scan(&u.ID, &u.Username, &u.PasswordHash, &u.Token, &u.CreatedAt)
	return u, err
}

func (s *Server) getUserByUsername(ctx context.Context, username string) (User, error) {
	var u User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, password_hash, token, created_at FROM users WHERE username = $1`,
		username,
	).Scan(&u.ID, &u.Username, &u.PasswordHash, &u.Token, &u.CreatedAt)
	return u, err
}

func (s *Server) getUserByID(ctx context.Context, id int) (User, error) {
	var u User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, password_hash, token, created_at FROM users WHERE id = $1`,
		id,
	).Scan(&u.ID, &u.Username, &u.PasswordHash, &u.Token, &u.CreatedAt)
	return u, err
}

func (s *Server) setToken(ctx context.Context, userID int, token string) error {
	_, err := s.db.Exec(ctx,
		`UPDATE users SET token = $1 WHERE id = $2`, token, userID)
	return err
}

func (s *Server) validateToken(ctx context.Context, userID int, token string) (bool, error) {
	var dbToken string
	err := s.db.QueryRow(ctx,
		`SELECT token FROM users WHERE id = $1`, userID,
	).Scan(&dbToken)
	if err != nil {
		return false, err
	}
	return dbToken == token, nil
}

func (s *Server) listResources(ctx context.Context, userID int) ([]Resource, error) {
	rows, err := s.db.Query(ctx,
		`SELECT id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at
		 FROM resources WHERE user_id = $1 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var resources []Resource
	for rows.Next() {
		var r Resource
		var tagsJSON []byte
		if err := rows.Scan(&r.ID, &r.UserID, &r.Name, &r.Type, &r.Region, &r.CostPerHour, &r.Status, &tagsJSON, &r.CreatedAt, &r.UpdatedAt); err != nil {
			return nil, err
		}
		json.Unmarshal(tagsJSON, &r.Tags)
		if r.Tags == nil {
			r.Tags = map[string]string{}
		}
		resources = append(resources, r)
	}
	return resources, nil
}

func (s *Server) createResource(ctx context.Context, userID int, r Resource) (Resource, error) {
	if r.CostPerHour == 0 {
		r.CostPerHour = defaultCostPerHour(r.Type)
	}
	if r.Region == "" {
		r.Region = "us-east-1"
	}
	if r.Status == "" {
		r.Status = "running"
	}
	if r.Tags == nil {
		r.Tags = map[string]string{}
	}
	tagsJSON, _ := json.Marshal(r.Tags)
	var created Resource
	var createdTags []byte
	err := s.db.QueryRow(ctx,
		`INSERT INTO resources (user_id, name, type, region, cost_per_hour, status, tags)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)
		 RETURNING id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at`,
		userID, r.Name, r.Type, r.Region, r.CostPerHour, r.Status, string(tagsJSON),
	).Scan(&created.ID, &created.UserID, &created.Name, &created.Type, &created.Region,
		&created.CostPerHour, &created.Status, &createdTags, &created.CreatedAt, &created.UpdatedAt)
	json.Unmarshal(createdTags, &created.Tags)
	return created, err
}

func (s *Server) updateResource(ctx context.Context, userID, resourceID int, r Resource) (Resource, error) {
	if r.Tags == nil {
		r.Tags = map[string]string{}
	}
	tagsJSON, _ := json.Marshal(r.Tags)
	var updated Resource
	var updatedTags []byte
	err := s.db.QueryRow(ctx,
		`UPDATE resources SET name=$1, type=$2, region=$3, cost_per_hour=$4, status=$5, tags=$6, updated_at=NOW()
		 WHERE id=$7 AND user_id=$8
		 RETURNING id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at`,
		r.Name, r.Type, r.Region, r.CostPerHour, r.Status, string(tagsJSON), resourceID, userID,
	).Scan(&updated.ID, &updated.UserID, &updated.Name, &updated.Type, &updated.Region,
		&updated.CostPerHour, &updated.Status, &updatedTags, &updated.CreatedAt, &updated.UpdatedAt)
	if err != nil {
		return Resource{}, err
	}
	json.Unmarshal(updatedTags, &updated.Tags)
	return updated, nil
}

func (s *Server) deleteResource(ctx context.Context, userID, resourceID int) error {
	tag, err := s.db.Exec(ctx,
		`DELETE FROM resources WHERE id = $1 AND user_id = $2`, resourceID, userID)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return fmt.Errorf("resource not found")
	}
	return nil
}

func (s *Server) getCostSummary(ctx context.Context, userID int) (CostSummary, error) {
	resources, err := s.listResources(ctx, userID)
	if err != nil {
		return CostSummary{}, err
	}

	var summary CostSummary
	byType := make(map[string]*CostByType)

	for _, r := range resources {
		monthly := r.CostPerHour * 730
		summary.TotalHourly += r.CostPerHour
		summary.TotalMonthly += monthly

		resourceWithCost := ResourceWithCost{Resource: r, MonthlyCost: monthly}
		summary.Resources = append(summary.Resources, resourceWithCost)

		if _, ok := byType[r.Type]; !ok {
			byType[r.Type] = &CostByType{Type: r.Type}
		}
		byType[r.Type].Count++
		byType[r.Type].TotalHourly += r.CostPerHour
		byType[r.Type].TotalMonthly += monthly
	}

	for _, ct := range byType {
		summary.ByType = append(summary.ByType, *ct)
	}

	return summary, nil
}

func (s *Server) createDeployment(ctx context.Context, userID int, resourceIDs []int) (Deployment, error) {
	idsJSON, err := json.Marshal(resourceIDs)
	if err != nil {
		return Deployment{}, err
	}
	var d Deployment
	err = s.db.QueryRow(ctx,
		`INSERT INTO deployments (user_id, resource_ids, status)
		 VALUES ($1, $2, 'in_progress')
		 RETURNING id, user_id, resource_ids, status, created_at, completed_at`,
		userID, string(idsJSON),
	).Scan(&d.ID, &d.UserID, &idsJSON, &d.Status, &d.CreatedAt, &d.CompletedAt)
	if err != nil {
		return Deployment{}, err
	}
	json.Unmarshal(idsJSON, &d.ResourceIDs)

	go s.simulateDeployment(d.ID)

	return d, nil
}

func (s *Server) simulateDeployment(deploymentID int) {
	time.Sleep(5 * time.Second)
	s.db.Exec(context.Background(),
		`UPDATE deployments SET status = 'completed', completed_at = NOW() WHERE id = $1`,
		deploymentID,
	)
}

func (s *Server) listDeployments(ctx context.Context, userID int) ([]Deployment, error) {
	rows, err := s.db.Query(ctx,
		`SELECT id, user_id, resource_ids, status, created_at, completed_at
		 FROM deployments WHERE user_id = $1 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var deployments []Deployment
	for rows.Next() {
		var d Deployment
		var idsJSON []byte
		if err := rows.Scan(&d.ID, &d.UserID, &idsJSON, &d.Status, &d.CreatedAt, &d.CompletedAt); err != nil {
			return nil, err
		}
		json.Unmarshal(idsJSON, &d.ResourceIDs)
		deployments = append(deployments, d)
	}
	return deployments, nil
}
