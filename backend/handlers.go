package main

import (
	"encoding/json"
	"net/http"
	"strconv"
)

type RegisterRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type AuthResponse struct {
	UserID   int    `json:"user_id"`
	Username string `json:"username"`
	Token    string `json:"token"`
}

type ResourcePayload struct {
	Name        string            `json:"name"`
	Type        string            `json:"type"`
	Region      string            `json:"region,omitempty"`
	CostPerHour float64           `json:"cost_per_hour,omitempty"`
	Status      string            `json:"status,omitempty"`
	Tags        map[string]string `json:"tags,omitempty"`
}

type DeployPayload struct {
	ResourceIDs []int `json:"resource_ids"`
}

type BatchPayload struct {
	Action string `json:"action"`
	IDs    []int  `json:"ids"`
}

func (s *Server) Register(w http.ResponseWriter, r *http.Request) {
	var body RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if body.Username == "" || body.Password == "" {
		writeError(w, http.StatusBadRequest, "username and password are required")
		return
	}
	if len(body.Password) < 4 {
		writeError(w, http.StatusBadRequest, "password must be at least 4 characters")
		return
	}

	hash, err := hashPassword(body.Password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not process password")
		return
	}

	user, err := s.createUser(r.Context(), body.Username, hash)
	if err != nil {
		writeError(w, http.StatusConflict, "username already exists")
		return
	}

	token, err := newSessionToken()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not generate session token")
		return
	}
	if err := s.setToken(r.Context(), user.ID, token); err != nil {
		writeError(w, http.StatusInternalServerError, "could not save session token")
		return
	}

	writeJSON(w, http.StatusCreated, AuthResponse{
		UserID:   user.ID,
		Username: user.Username,
		Token:    token,
	})
}

func (s *Server) Login(w http.ResponseWriter, r *http.Request) {
	var body LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	user, err := s.getUserByUsername(r.Context(), body.Username)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "incorrect username or password")
		return
	}

	if !checkPassword(user.PasswordHash, body.Password) {
		writeError(w, http.StatusUnauthorized, "incorrect username or password")
		return
	}

	token, err := newSessionToken()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not generate session token")
		return
	}
	if err := s.setToken(r.Context(), user.ID, token); err != nil {
		writeError(w, http.StatusInternalServerError, "could not save session token")
		return
	}

	writeJSON(w, http.StatusOK, AuthResponse{
		UserID:   user.ID,
		Username: user.Username,
		Token:    token,
	})
}

func (s *Server) ListResources(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	resources, err := s.listResources(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch resources")
		return
	}
	if resources == nil {
		resources = []Resource{}
	}

	writeJSON(w, http.StatusOK, resources)
}

func (s *Server) CreateResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	var body ResourcePayload
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.Name == "" || body.Type == "" {
		writeError(w, http.StatusBadRequest, "resource name and type are required")
		return
	}

	resource := Resource{
		Name:        body.Name,
		Type:        body.Type,
		Region:      body.Region,
		CostPerHour: body.CostPerHour,
		Status:      body.Status,
		Tags:        body.Tags,
	}

	created, err := s.createResource(r.Context(), userID, resource)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not create resource")
		return
	}

	writeJSON(w, http.StatusCreated, created)
}

func (s *Server) GetResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	resourceID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	resource, err := s.getResourceByID(r.Context(), userID, resourceID)
	if err != nil {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	deployments, _ := s.listResourceDeployments(r.Context(), userID, resourceID)

	result := map[string]interface{}{
		"resource":    resource,
		"deployments": deployments,
	}
	writeJSON(w, http.StatusOK, result)
}

func (s *Server) UpdateResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	resourceID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	var body ResourcePayload
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.Name == "" || body.Type == "" {
		writeError(w, http.StatusBadRequest, "resource name and type are required")
		return
	}

	resource := Resource{
		Name:        body.Name,
		Type:        body.Type,
		Region:      body.Region,
		CostPerHour: body.CostPerHour,
		Status:      body.Status,
		Tags:        body.Tags,
	}

	updated, err := s.updateResource(r.Context(), userID, resourceID, resource)
	if err != nil {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	writeJSON(w, http.StatusOK, updated)
}

func (s *Server) DeleteResource(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	resourceID, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	if err := s.deleteResource(r.Context(), userID, resourceID); err != nil {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (s *Server) BatchAction(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	var body BatchPayload
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.Action == "" || len(body.IDs) == 0 {
		writeError(w, http.StatusBadRequest, "action and ids are required")
		return
	}
	if body.Action != "stop" && body.Action != "terminate" && body.Action != "delete" {
		writeError(w, http.StatusBadRequest, "action must be stop, terminate, or delete")
		return
	}

	if err := s.batchAction(r.Context(), userID, body.Action, body.IDs); err != nil {
		writeError(w, http.StatusInternalServerError, "batch action failed")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) CostSummary(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	summary, err := s.getCostSummary(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not generate cost summary")
		return
	}

	writeJSON(w, http.StatusOK, summary)
}

func (s *Server) TriggerDeployment(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	var body DeployPayload
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(body.ResourceIDs) == 0 {
		writeError(w, http.StatusBadRequest, "select at least one resource to deploy")
		return
	}

	deployment, err := s.createDeployment(r.Context(), userID, body.ResourceIDs)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not start deployment")
		return
	}

	writeJSON(w, http.StatusCreated, deployment)
}

func (s *Server) CostHistory(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	entries, err := s.getCostHistory(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch cost history")
		return
	}

	writeJSON(w, http.StatusOK, entries)
}

func (s *Server) ListDeployments(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.Header.Get("X-User-ID"))

	deployments, err := s.listDeployments(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch deployments")
		return
	}
	if deployments == nil {
		deployments = []Deployment{}
	}

	writeJSON(w, http.StatusOK, deployments)
}
