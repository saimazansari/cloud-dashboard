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

type CostEntry struct {
	Date      string  `json:"date"`
	TotalCost float64 `json:"total_cost"`
}

type Deployment struct {
	ID          int        `json:"id"`
	UserID      int        `json:"user_id"`
	ResourceIDs []int      `json:"resource_ids"`
	Status      string     `json:"status"`
	CreatedAt   time.Time  `json:"created_at"`
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

func costPerHour(resourceType string) float64 {
	rates := map[string]float64{
		"Virtual Machine":    0.0860,
		"Storage Account":    0.0180,
		"Load Balancer":      0.0250,
		"Database":           0.0150,
		"Kubernetes Cluster": 0.1000,
		"Serverless Function": 0.0000,
		"CDN Profile":        0.0100,
	}
	if rate, exists := rates[resourceType]; exists {
		return rate
	}
	return 0.01
}

func (s *Server) migrate() error {
	statements := []string{
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

	_, err := s.db.Exec(context.Background(),
		`ALTER TABLE resources ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '{}'`)
	return err
}

func (s *Server) createUser(ctx context.Context, username, passwordHash string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`INSERT INTO users (username, password_hash)
		 VALUES ($1, $2)
		 RETURNING id, username, password_hash, token, created_at`,
		username, passwordHash,
	).Scan(&user.ID, &user.Username, &user.PasswordHash, &user.Token, &user.CreatedAt)
	return user, err
}

func (s *Server) getUserByUsername(ctx context.Context, username string) (User, error) {
	var user User
	err := s.db.QueryRow(ctx,
		`SELECT id, username, password_hash, token, created_at
		 FROM users WHERE username = $1`,
		username,
	).Scan(&user.ID, &user.Username, &user.PasswordHash, &user.Token, &user.CreatedAt)
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

		json.Unmarshal(tagsJSON, &resource.Tags)
		if resource.Tags == nil {
			resource.Tags = map[string]string{}
		}

		resources = append(resources, resource)
	}
	return resources, nil
}

func (s *Server) createResource(ctx context.Context, userID int, resource Resource) (Resource, error) {
	if resource.CostPerHour == 0 {
		resource.CostPerHour = costPerHour(resource.Type)
	}
	if resource.Region == "" {
		resource.Region = "us-east-1"
	}
	if resource.Status == "" {
		resource.Status = "running"
	}
	if resource.Tags == nil {
		resource.Tags = map[string]string{}
	}

	tagsJSON, _ := json.Marshal(resource.Tags)

	var created Resource
	var createdTags []byte

	err := s.db.QueryRow(ctx,
		`INSERT INTO resources (user_id, name, type, region, cost_per_hour, status, tags)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)
		 RETURNING id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at`,
		userID, resource.Name, resource.Type, resource.Region,
		resource.CostPerHour, resource.Status, string(tagsJSON),
	).Scan(
		&created.ID, &created.UserID, &created.Name, &created.Type,
		&created.Region, &created.CostPerHour, &created.Status,
		&createdTags, &created.CreatedAt, &created.UpdatedAt,
	)
	if err != nil {
		return Resource{}, err
	}

	json.Unmarshal(createdTags, &created.Tags)
	return created, nil
}

func (s *Server) updateResource(ctx context.Context, userID, resourceID int, resource Resource) (Resource, error) {
	if resource.Tags == nil {
		resource.Tags = map[string]string{}
	}

	tagsJSON, _ := json.Marshal(resource.Tags)

	var updated Resource
	var updatedTags []byte

	err := s.db.QueryRow(ctx,
		`UPDATE resources
		 SET name=$1, type=$2, region=$3, cost_per_hour=$4, status=$5, tags=$6, updated_at=NOW()
		 WHERE id=$7 AND user_id=$8
		 RETURNING id, user_id, name, type, region, cost_per_hour, status, tags, created_at, updated_at`,
		resource.Name, resource.Type, resource.Region,
		resource.CostPerHour, resource.Status, string(tagsJSON),
		resourceID, userID,
	).Scan(
		&updated.ID, &updated.UserID, &updated.Name, &updated.Type,
		&updated.Region, &updated.CostPerHour, &updated.Status,
		&updatedTags, &updated.CreatedAt, &updated.UpdatedAt,
	)
	if err != nil {
		return Resource{}, fmt.Errorf("update failed: %w", err)
	}

	json.Unmarshal(updatedTags, &updated.Tags)
	return updated, nil
}

func (s *Server) batchAction(ctx context.Context, userID int, action string, ids []int) error {
	if len(ids) == 0 {
		return nil
	}
	for _, id := range ids {
		switch action {
		case "stop":
			_, err := s.db.Exec(ctx,
				`UPDATE resources SET status='stopped', updated_at=NOW() WHERE id=$1 AND user_id=$2`,
				id, userID)
			if err != nil {
				return err
			}
		case "terminate":
			_, err := s.db.Exec(ctx,
				`UPDATE resources SET status='terminated', updated_at=NOW() WHERE id=$1 AND user_id=$2`,
				id, userID)
			if err != nil {
				return err
			}
		case "delete":
			if err := s.deleteResource(ctx, userID, id); err != nil {
				return err
			}
		}
	}
	return nil
}

func (s *Server) deleteResource(ctx context.Context, userID, resourceID int) error {
	result, err := s.db.Exec(ctx,
		`DELETE FROM resources WHERE id = $1 AND user_id = $2`, resourceID, userID)
	if err != nil {
		return err
	}
	if result.RowsAffected() == 0 {
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
	grouped := make(map[string]*CostByType)

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
	}

	for _, group := range grouped {
		summary.ByType = append(summary.ByType, *group)
	}

	return summary, nil
}

func (s *Server) createDeployment(ctx context.Context, userID int, resourceIDs []int) (Deployment, error) {
	idsJSON, _ := json.Marshal(resourceIDs)

	var deployment Deployment
	var storedIDs []byte

	err := s.db.QueryRow(ctx,
		`INSERT INTO deployments (user_id, resource_ids, status)
		 VALUES ($1, $2, 'in_progress')
		 RETURNING id, user_id, resource_ids, status, created_at, completed_at`,
		userID, string(idsJSON),
	).Scan(&deployment.ID, &deployment.UserID, &storedIDs, &deployment.Status, &deployment.CreatedAt, &deployment.CompletedAt)
	if err != nil {
		return Deployment{}, err
	}

	json.Unmarshal(storedIDs, &deployment.ResourceIDs)

	go s.simulateDeploymentCompletion(deployment.ID)

	return deployment, nil
}

func (s *Server) simulateDeploymentCompletion(deploymentID int) {
	time.Sleep(5 * time.Second)
	s.db.Exec(context.Background(),
		`UPDATE deployments SET status = 'completed', completed_at = NOW() WHERE id = $1`,
		deploymentID,
	)
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
	json.Unmarshal(tagsJSON, &resource.Tags)
	if resource.Tags == nil {
		resource.Tags = map[string]string{}
	}
	return resource, nil
}

func (s *Server) listResourceDeployments(ctx context.Context, userID, resourceID int) ([]Deployment, error) {
	rows, err := s.db.Query(ctx,
		`SELECT id, user_id, resource_ids, status, created_at, completed_at
		 FROM deployments WHERE user_id = $1
		 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var deployments []Deployment
	for rows.Next() {
		var deployment Deployment
		var idsJSON []byte
		if err := rows.Scan(
			&deployment.ID, &deployment.UserID, &idsJSON,
			&deployment.Status, &deployment.CreatedAt, &deployment.CompletedAt,
		); err != nil {
			return nil, err
		}
		json.Unmarshal(idsJSON, &deployment.ResourceIDs)
		for _, id := range deployment.ResourceIDs {
			if id == resourceID {
				deployments = append(deployments, deployment)
				break
			}
		}
	}
	if deployments == nil {
		deployments = []Deployment{}
	}
	return deployments, nil
}

func (s *Server) listDeployments(ctx context.Context, userID int) ([]Deployment, error) {
	rows, err := s.db.Query(ctx,
		`SELECT id, user_id, resource_ids, status, created_at, completed_at
		 FROM deployments WHERE user_id = $1
		 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var deployments []Deployment
	for rows.Next() {
		var deployment Deployment
		var idsJSON []byte

		err := rows.Scan(
			&deployment.ID, &deployment.UserID, &idsJSON,
			&deployment.Status, &deployment.CreatedAt, &deployment.CompletedAt,
		)
		if err != nil {
			return nil, err
		}

		json.Unmarshal(idsJSON, &deployment.ResourceIDs)
		deployments = append(deployments, deployment)
	}
	return deployments, nil
}
