package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
    "time"

    "github.com/aws/aws-sdk-go-v2/aws"
    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/credentials"
    "github.com/aws/aws-sdk-go-v2/service/bedrockruntime"
    "github.com/gorilla/mux"
)

// Request and Response structs
type GenerateRequest struct {
    Prompt string `json:"prompt"`
}

type GenerateResponse struct {
    Response string `json:"response"`
}

type HealthResponse struct {
    Status  string `json:"status"`
    Service string `json:"service"`
}

// BedrockClient wraps the AWS Bedrock client
type BedrockClient struct {
    client *bedrockruntime.Client
}

// NewBedrockClient creates a new Bedrock client
func NewBedrockClient() (*BedrockClient, error) {
    // Get AWS credentials from environment variables
    awsAccessKey := os.Getenv("AWS_ACCESS_KEY_ID")
    awsSecretKey := os.Getenv("AWS_SECRET_ACCESS_KEY")
    awsRegion := os.Getenv("AWS_REGION")
    
    if awsRegion == "" {
        awsRegion = "us-east-1" // Default region
    }

    // Create AWS config
    cfg, err := config.LoadDefaultConfig(context.TODO(),
        config.WithRegion(awsRegion),
        config.WithCredentialsProvider(
            credentials.NewStaticCredentialsProvider(awsAccessKey, awsSecretKey, ""),
        ),
    )
    if err != nil {
        return nil, fmt.Errorf("unable to load SDK config: %v", err)
    }

    // Create Bedrock client
    client := bedrockruntime.NewFromConfig(cfg)
    
    return &BedrockClient{client: client}, nil
}

// GenerateText calls Amazon Bedrock to generate text
func (bc *BedrockClient) GenerateText(prompt string) (string, error) {
    // Prepare the request body for Claude model
    requestBody := map[string]interface{}{
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": []map[string]string{
            {
                "role": "user",
                "content": prompt,
            },
        },
        "temperature": 0.7,
    }

    bodyBytes, err := json.Marshal(requestBody)
    if err != nil {
        return "", fmt.Errorf("error marshaling request: %v", err)
    }

    // Model ID for Claude 3 Haiku (faster and cheaper for demos)
    modelID := "anthropic.claude-3-haiku-20240307-v1:0"
    
    // Invoke the model
    resp, err := bc.client.InvokeModel(context.TODO(), &bedrockruntime.InvokeModelInput{
        Body:        bodyBytes,
        ModelId:     aws.String(modelID),
        ContentType: aws.String("application/json"),
    })
    
    if err != nil {
        return "", fmt.Errorf("error invoking Bedrock: %v", err)
    }

    // Parse the response
    var response map[string]interface{}
    if err := json.Unmarshal(resp.Body, &response); err != nil {
        return "", fmt.Errorf("error parsing response: %v", err)
    }

    // Extract the text from Claude's response format
    if content, ok := response["content"].([]interface{}); ok && len(content) > 0 {
        if firstContent, ok := content[0].(map[string]interface{}); ok {
            if text, ok := firstContent["text"].(string); ok {
                return text, nil
            }
        }
    }

    return "Unable to generate response", nil
}

// Handlers
func healthHandler(w http.ResponseWriter, r *http.Request) {
    response := HealthResponse{
        Status:  "healthy",
        Service: "bedrock-service",
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}

func rootHandler(w http.ResponseWriter, r *http.Request) {
    response := map[string]string{
        "message": "Bedrock Service is running",
        "version": "1.0.0",
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}

func generateHandler(bc *BedrockClient) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var req GenerateRequest
        
        // Parse request body
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
            http.Error(w, "Invalid request body", http.StatusBadRequest)
            return
        }

        // Validate prompt
        if req.Prompt == "" {
            http.Error(w, "Prompt is required", http.StatusBadRequest)
            return
        }

        log.Printf("Received prompt: %s", req.Prompt[:min(50, len(req.Prompt))])

        // Generate text using Bedrock
        response, err := bc.GenerateText(req.Prompt)
        if err != nil {
            log.Printf("Error generating text: %v", err)
            http.Error(w, "Error generating response", http.StatusInternalServerError)
            return
        }

        // Send response
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(GenerateResponse{
            Response: response,
        })
    }
}

func min(a, b int) int {
    if a < b {
        return a
    }
    return b
}

func main() {
    // Initialize Bedrock client
    bc, err := NewBedrockClient()
    if err != nil {
        log.Printf("Warning: Bedrock client initialization failed: %v", err)
        log.Println("Service will run but Bedrock calls will fail")
    }

    // Create router
    router := mux.NewRouter()
    
    // Register routes
    router.HandleFunc("/", rootHandler).Methods("GET")
    router.HandleFunc("/health", healthHandler).Methods("GET")
    router.HandleFunc("/generate", generateHandler(bc)).Methods("POST")

    // Configure server
    srv := &http.Server{
        Handler:      router,
        Addr:         ":9000",
        WriteTimeout: 30 * time.Second,
        ReadTimeout:  30 * time.Second,
    }

    log.Println("Bedrock Service starting on port 9000...")
    if err := srv.ListenAndServe(); err != nil {
        log.Fatal(err)
    }
}
