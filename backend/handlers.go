package main

import (
	"encoding/json"
	"net/http"
	"strconv"
)

func userIDFromRequest(r *http.Request) int {
	id, _ := strconv.Atoi(r.Header.Get("X-User-ID"))
	return id
}

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
	userID := userIDFromRequest(r)

	if s.az != nil {
		resources, err := s.az.ListResources(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not fetch Azure resources")
			return
		}
		for i := range resources {
			resources[i].UserID = userID
		}
		writeJSON(w, http.StatusOK, resources)
		return
	}

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

func (s *Server) GetResource(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)
	resourceIDStr := r.PathValue("id")

	if s.az != nil {
		resource, err := s.az.GetResource(r.Context(), resourceIDStr)
		if err != nil {
			writeError(w, http.StatusNotFound, "resource not found")
			return
		}
		resource.UserID = userID
		result := map[string]interface{}{
			"resource":    resource,
			"deployments": []Deployment{},
		}
		writeJSON(w, http.StatusOK, result)
		return
	}

	resourceID, err := strconv.Atoi(resourceIDStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}

	resource, err := s.getResourceByID(r.Context(), userID, resourceID)
	if err != nil {
		writeError(w, http.StatusNotFound, "resource not found")
		return
	}

	deployments, _ := s.listDeployments(r.Context(), userID, resourceID)

	result := map[string]interface{}{
		"resource":    resource,
		"deployments": deployments,
	}
	writeJSON(w, http.StatusOK, result)
}

func (s *Server) BatchAction(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)

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

	if s.az != nil {
		resources, err := s.az.ListResources(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not list Azure resources")
			return
		}
		idSet := make(map[int]bool)
		for _, id := range body.IDs {
			idSet[id] = true
		}
		var selected []Resource
		for _, res := range resources {
			if idSet[res.ID] {
				selected = append(selected, res)
			}
		}
		if err := s.az.BatchAction(r.Context(), body.Action, selected); err != nil {
			writeError(w, http.StatusInternalServerError, "batch action failed on Azure")
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}

	if err := s.batchAction(r.Context(), userID, body.Action, body.IDs); err != nil {
		writeError(w, http.StatusInternalServerError, "batch action failed")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) CostSummary(w http.ResponseWriter, r *http.Request) {
	if s.az != nil {
		summary, err := s.az.GetCostSummary(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not generate cost summary")
			return
		}
		writeJSON(w, http.StatusOK, summary)
		return
	}

	userID := userIDFromRequest(r)

	summary, err := s.getCostSummary(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not generate cost summary")
		return
	}

	writeJSON(w, http.StatusOK, summary)
}

func (s *Server) TriggerDeployment(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)

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
	if s.az != nil {
		entries, err := s.az.GetCostHistory(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not fetch cost history")
			return
		}
		writeJSON(w, http.StatusOK, entries)
		return
	}

	userID := userIDFromRequest(r)

	entries, err := s.getCostHistory(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch cost history")
		return
	}

	writeJSON(w, http.StatusOK, entries)
}

func (s *Server) ListSubscriptions(w http.ResponseWriter, r *http.Request) {
	if s.az == nil {
		writeError(w, http.StatusServiceUnavailable, "Azure integration not enabled")
		return
	}
	subs, err := s.az.ListSubscriptions(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not list subscriptions")
		return
	}
	writeJSON(w, http.StatusOK, subs)
}

func (s *Server) ListDeployments(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)

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
