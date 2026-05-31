package main

import (
	"encoding/json"
	"net/http"
	"strconv"
)

type registerRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type loginResponse struct {
	UserID   int    `json:"user_id"`
	Username string `json:"username"`
	Token    string `json:"token"`
}

type resourceRequest struct {
	Name        string            `json:"name"`
	Type        string            `json:"type"`
	Region      string            `json:"region,omitempty"`
	CostPerHour float64           `json:"cost_per_hour,omitempty"`
	Status      string            `json:"status,omitempty"`
	Tags        map[string]string `json:"tags,omitempty"`
}

type createDeploymentRequest struct {
	ResourceIDs []int `json:"resource_ids"`
}

func (s *Server) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Username == "" || req.Password == "" {
		respondError(w, http.StatusBadRequest, "username and password required")
		return
	}
	if len(req.Password) < 4 {
		respondError(w, http.StatusBadRequest, "password must be at least 4 characters")
		return
	}

	hash, err := hashPassword(req.Password)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to hash password")
		return
	}

	user, err := s.createUser(r.Context(), req.Username, hash)
	if err != nil {
		respondError(w, http.StatusConflict, "username already exists")
		return
	}

	token, err := generateToken()
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}
	if err := s.setToken(r.Context(), user.ID, token); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to save token")
		return
	}

	respondJSON(w, http.StatusCreated, loginResponse{
		UserID:   user.ID,
		Username: user.Username,
		Token:    token,
	})
}

func (s *Server) Login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	user, err := s.getUserByUsername(r.Context(), req.Username)
	if err != nil {
		respondError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}

	if !checkPassword(user.PasswordHash, req.Password) {
		respondError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}

	token, err := generateToken()
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}
	if err := s.setToken(r.Context(), user.ID, token); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to save token")
		return
	}

	respondJSON(w, http.StatusOK, loginResponse{
		UserID:   user.ID,
		Username: user.Username,
		Token:    token,
	})
}

func (s *Server) ListResources(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	resources, err := s.listResources(r.Context(), userID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list resources")
		return
	}
	if resources == nil {
		resources = []Resource{}
	}
	respondJSON(w, http.StatusOK, resources)
}

func (s *Server) CreateResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	var req resourceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Name == "" || req.Type == "" {
		respondError(w, http.StatusBadRequest, "name and type are required")
		return
	}

	resource := Resource{
		Name:        req.Name,
		Type:        req.Type,
		Region:      req.Region,
		CostPerHour: req.CostPerHour,
		Status:      req.Status,
		Tags:        req.Tags,
	}

	created, err := s.createResource(r.Context(), userID, resource)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create resource")
		return
	}

	respondJSON(w, http.StatusCreated, created)
}

func (s *Server) UpdateResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	resourceID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	var req resourceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Name == "" || req.Type == "" {
		respondError(w, http.StatusBadRequest, "name and type are required")
		return
	}

	resource := Resource{
		Name:        req.Name,
		Type:        req.Type,
		Region:      req.Region,
		CostPerHour: req.CostPerHour,
		Status:      req.Status,
		Tags:        req.Tags,
	}

	updated, err := s.updateResource(r.Context(), userID, resourceID, resource)
	if err != nil {
		respondError(w, http.StatusNotFound, "resource not found")
		return
	}

	respondJSON(w, http.StatusOK, updated)
}

func (s *Server) DeleteResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	resourceID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	if err := s.deleteResource(r.Context(), userID, resourceID); err != nil {
		respondError(w, http.StatusNotFound, "resource not found")
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (s *Server) CostSummary(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	summary, err := s.getCostSummary(r.Context(), userID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get cost summary")
		return
	}
	respondJSON(w, http.StatusOK, summary)
}

func (s *Server) TriggerDeployment(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	var req createDeploymentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(req.ResourceIDs) == 0 {
		respondError(w, http.StatusBadRequest, "at least one resource_id required")
		return
	}

	deployment, err := s.createDeployment(r.Context(), userID, req.ResourceIDs)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create deployment")
		return
	}

	respondJSON(w, http.StatusCreated, deployment)
}

func (s *Server) ListDeployments(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	deployments, err := s.listDeployments(r.Context(), userID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list deployments")
		return
	}
	if deployments == nil {
		deployments = []Deployment{}
	}
	respondJSON(w, http.StatusOK, deployments)
}
