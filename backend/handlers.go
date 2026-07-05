package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"
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

	user, err := s.createUser(r.Context(), body.Username, "", hash)
	if err != nil {
		writeError(w, http.StatusConflict, "username already exists")
		return
	}

	token := user.Token
	if token == "" {
		token, err = newSessionToken()
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not generate session token")
			return
		}
		if err := s.setToken(r.Context(), user.ID, token); err != nil {
			writeError(w, http.StatusInternalServerError, "could not save session token")
			return
		}
	}

	writeJSON(w, http.StatusOK, AuthResponse{
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

func (s *Server) GoogleAuth(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Credential string `json:"credential"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.Credential == "" {
		writeError(w, http.StatusBadRequest, "credential is required")
		return
	}

	payload, err := verifyGoogleToken(r.Context(), body.Credential, s.googleClientID)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "invalid Google token: "+err.Error())
		return
	}

	email := payload.Email
	name := payload.Name
	if email == "" {
		writeError(w, http.StatusBadRequest, "email not provided by Google")
		return
	}
	if name == "" {
		name = email
	}

	user, err := s.findUserByEmail(r.Context(), email)
	if err != nil {
		hash, _ := hashPassword(body.Credential)
		user, err = s.createUser(r.Context(), name, email, hash)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not create user")
			return
		}
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

func (s *Server) GitHubAuth(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Code string `json:"code"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.Code == "" {
		writeError(w, http.StatusBadRequest, "code is required")
		return
	}

	ghID, username, _, err := exchangeGitHubCode(r.Context(), body.Code, s.githubClientID, s.githubClientSecret)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "GitHub auth failed: "+err.Error())
		return
	}
	if username == "" {
		username = "github-user"
	}

	user, err := s.findUserByGitHubID(r.Context(), ghID)
	if err != nil {
		user, err = s.createUser(r.Context(), username, "github:"+ghID, "")
		if err != nil {
			log.Printf("create github user failed (username=%q, ghID=%s): %v", username, ghID, err)
			user, err = s.createUser(r.Context(), username+"-gh", "github:"+ghID, "")
			if err != nil {
				writeError(w, http.StatusInternalServerError, "could not create user after retry: "+err.Error())
				return
			}
		}
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

func (s *Server) mockResourcesWithStatus() []Resource {
	s.mockMu.RLock()
	defer s.mockMu.RUnlock()
	out := make([]Resource, len(s.mockResources))
	copy(out, s.mockResources)
	for i := range out {
		if st, ok := s.getPendingStatus(out[i].Tags["_mock_id"]); ok {
			out[i].Status = st
		}
	}
	return out
}

func (s *Server) findMockResource(id string) (*Resource, bool) {
	s.mockMu.RLock()
	defer s.mockMu.RUnlock()
	for _, r := range s.mockResources {
		if r.Tags["_mock_id"] == id {
			cp := r
			if st, ok := s.getPendingStatus(cp.Tags["_mock_id"]); ok {
				cp.Status = st
			}
			return &cp, true
		}
	}
	return nil, false
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
			if st, ok := s.getPendingStatus(resources[i].Tags["_azure_id"]); ok {
				resources[i].Status = st
			}
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
		if err == nil {
			resource.UserID = userID
			if st, ok := s.getPendingStatus(resource.Tags["_azure_id"]); ok {
				resource.Status = st
			}
			writeJSON(w, http.StatusOK, map[string]interface{}{"resource": resource})
			return
		}
		if mock, ok := s.findMockResource(resourceIDStr); ok {
			mock.UserID = userID
			writeJSON(w, http.StatusOK, map[string]interface{}{"resource": mock})
			return
		}
		writeError(w, http.StatusNotFound, "resource not found")
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

	result := map[string]interface{}{
		"resource": resource,
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
	if body.Action != "start" && body.Action != "stop" && body.Action != "terminate" && body.Action != "delete" {
		writeError(w, http.StatusBadRequest, "action must be start, stop, terminate, or delete")
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
			writeError(w, http.StatusInternalServerError, "batch action failed on Azure: "+err.Error())
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

func (s *Server) StopResource(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)
	idStr := r.PathValue("id")

	if s.az != nil {
		if mock, ok := s.findMockResource(idStr); ok {
			s.setPendingStatus(mock.Tags["_mock_id"], "stopping")
			go func(mid string) {
				time.Sleep(3 * time.Second)
				s.setPendingStatus(mid, "stopped")
				time.Sleep(30 * time.Second)
				s.clearPendingStatus(mid)
			}(mock.Tags["_mock_id"])
			writeJSON(w, http.StatusOK, map[string]string{"status": "stopping"})
			return
		}
		resource, err := s.az.GetResource(r.Context(), idStr)
		if err != nil {
			writeError(w, http.StatusNotFound, "resource not found in Azure")
			return
		}
		azID := resource.Tags["_azure_id"]
		if azID == "" {
			writeError(w, http.StatusBadRequest, "resource has no Azure ID")
			return
		}

		s.setPendingStatus(azID, "stopping")
		go func() {
			ctx := context.Background()
			if err := s.az.StopResource(ctx, azID); err != nil {
				log.Printf("async stop failed for %s: %v", azID, err)
				s.clearPendingStatus(azID)
				return
			}
			s.setPendingStatus(azID, "stopped")
			time.Sleep(30 * time.Second)
			s.clearPendingStatus(azID)
		}()
		writeJSON(w, http.StatusOK, map[string]string{"status": "stopping"})
		return
	}

	id, err := strconv.Atoi(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}
	if err := s.updateResourceStatus(r.Context(), userID, id, "stopped"); err != nil {
		writeError(w, http.StatusInternalServerError, "could not stop resource")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "stopped"})
}

func (s *Server) StartResource(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)
	idStr := r.PathValue("id")

	if s.az != nil {
		if mock, ok := s.findMockResource(idStr); ok {
			s.setPendingStatus(mock.Tags["_mock_id"], "starting")
			go func(mid string) {
				time.Sleep(3 * time.Second)
				s.setPendingStatus(mid, "running")
				time.Sleep(30 * time.Second)
				s.clearPendingStatus(mid)
			}(mock.Tags["_mock_id"])
			writeJSON(w, http.StatusOK, map[string]string{"status": "starting"})
			return
		}
		resource, err := s.az.GetResource(r.Context(), idStr)
		if err != nil {
			writeError(w, http.StatusNotFound, "resource not found in Azure")
			return
		}
		azID := resource.Tags["_azure_id"]
		if azID == "" {
			writeError(w, http.StatusBadRequest, "resource has no Azure ID")
			return
		}

		s.setPendingStatus(azID, "starting")
		go func() {
			ctx := context.Background()
			if err := s.az.StartResource(ctx, azID); err != nil {
				log.Printf("async start failed for %s: %v", azID, err)
				s.clearPendingStatus(azID)
				return
			}
			s.setPendingStatus(azID, "running")
			time.Sleep(30 * time.Second)
			s.clearPendingStatus(azID)
		}()
		writeJSON(w, http.StatusOK, map[string]string{"status": "starting"})
		return
	}

	id, err := strconv.Atoi(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid resource id")
		return
	}
	if err := s.updateResourceStatus(r.Context(), userID, id, "running"); err != nil {
		writeError(w, http.StatusInternalServerError, "could not start resource")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "running"})
}

func (s *Server) CostSummary(w http.ResponseWriter, r *http.Request) {
	if s.az != nil {
		summary, err := s.az.GetCostSummary(r.Context())
		if err != nil {
			writeError(w, http.StatusInternalServerError, "could not generate cost summary")
			return
		}
		summary.TotalMonthly = summary.TotalHourly * 730
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

func (s *Server) initMockResources() {
	s.mockMu.Lock()
	defer s.mockMu.Unlock()
	base := 1000
	s.mockResources = []Resource{
		{Name: "web-prod-01", Type: "Virtual Machine", Region: "east-us", CostPerHour: 0.0860, Status: "stopped", Sku: "Standard_B2s", Tags: map[string]string{"_mock_id": fmt.Sprintf("%d", base+0)}},
		{Name: "web-staging-01", Type: "Virtual Machine", Region: "west-europe", CostPerHour: 0.0480, Status: "stopped", Sku: "Standard_B1s", Tags: map[string]string{"_mock_id": fmt.Sprintf("%d", base+2)}},
		{Name: "prod-db-mysql", Type: "Database", Region: "east-us", CostPerHour: 0.0500, Status: "stopped", Sku: "MySQL Flexible Server", Tags: map[string]string{"_mock_id": fmt.Sprintf("%d", base+6)}},
		{Name: "cdn-prod", Type: "CDN Profile", Region: "east-us", CostPerHour: 0.0100, Status: "running", Tags: map[string]string{"_mock_id": fmt.Sprintf("%d", base+8)}},
		{Name: "serverless-api", Type: "Serverless Function", Region: "east-us", CostPerHour: 0.0000, Status: "running", Sku: "Consumption Plan", Tags: map[string]string{"_mock_id": fmt.Sprintf("%d", base+10)}},
	}
}

func (s *Server) SeedResources(w http.ResponseWriter, r *http.Request) {
	s.initMockResources()
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"count":     len(s.mockResources),
		"resources": s.mockResources,
	})
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

type PasswordUpdate struct {
	OldPassword string `json:"old_password"`
	NewPassword string `json:"new_password"`
}

func (s *Server) UpdatePassword(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)

	var body PasswordUpdate
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if body.OldPassword == "" || body.NewPassword == "" {
		writeError(w, http.StatusBadRequest, "old and new password are required")
		return
	}

	var storedHash string
	err := s.db.QueryRow(r.Context(),
		`SELECT password_hash FROM users WHERE id = $1`, userID,
	).Scan(&storedHash)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch user")
		return
	}

	if !checkPassword(storedHash, body.OldPassword) {
		writeError(w, http.StatusUnauthorized, "current password is incorrect")
		return
	}

	newHash, err := hashPassword(body.NewPassword)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not hash password")
		return
	}

	if err := s.updatePassword(r.Context(), userID, newHash); err != nil {
		writeError(w, http.StatusInternalServerError, "could not update password")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"message": "password updated"})
}

func (s *Server) GetPreferences(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)
	prefs, err := s.getPreferences(r.Context(), userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not fetch preferences")
		return
	}
	writeJSON(w, http.StatusOK, prefs)
}

func (s *Server) UpdatePreferences(w http.ResponseWriter, r *http.Request) {
	userID := userIDFromRequest(r)
	var prefs map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&prefs); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if err := s.updatePreferences(r.Context(), userID, prefs); err != nil {
		writeError(w, http.StatusInternalServerError, "could not update preferences")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"message": "preferences updated"})
}


