package main

import (
	"os"
	"testing"
)

func TestHashPassword(t *testing.T) {
	hash, err := hashPassword("testpass123")
	if err != nil {
		t.Fatalf("hashPassword failed: %v", err)
	}
	if !checkPassword(hash, "testpass123") {
		t.Error("checkPassword should match correct password")
	}
	if checkPassword(hash, "wrongpass") {
		t.Error("checkPassword should reject wrong password")
	}
}

func TestEnvWithFallback(t *testing.T) {
	os.Setenv("TEST_EXISTS", "hello")
	if v := env("TEST_EXISTS", "fallback"); v != "hello" {
		t.Errorf("expected 'hello', got '%s'", v)
	}
	os.Unsetenv("TEST_EXISTS")
	if v := env("TEST_EXISTS", "fallback"); v != "fallback" {
		t.Errorf("expected 'fallback', got '%s'", v)
	}
}
