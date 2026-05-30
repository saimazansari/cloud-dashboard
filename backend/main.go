package main

import (
    "fmt"
    "net/http"
)

func home(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "Hello from Go Backend")
}

func main() {
    http.HandleFunc("/", home)
    http.ListenAndServe(":8080", nil)
}