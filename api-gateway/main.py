from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="API Gateway", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get Bedrock service URL from environment
BEDROCK_SERVICE_URL = os.getenv("BEDROCK_SERVICE_URL", "http://localhost:9000")

# Request/Response models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class HealthResponse(BaseModel):
    status: str
    service: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "API Gateway is running", "version": "1.0.0"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Forward chat requests to the Bedrock service
    """
    try:
        logger.info(f"Received chat request: {request.message[:50]}...")
        
        # Forward request to Bedrock service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BEDROCK_SERVICE_URL}/generate",
                json={"prompt": request.message}
            )
            
            if response.status_code != 200:
                logger.error(f"Bedrock service returned status {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Error from Bedrock service"
                )
            
            result = response.json()
            logger.info("Successfully received response from Bedrock service")
            
            return ChatResponse(response=result.get("response", "No response generated"))
            
    except httpx.RequestError as e:
        logger.error(f"Error connecting to Bedrock service: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Bedrock service is unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@app.get("/services/status")
async def services_status():
    """
    Check the status of all backend services
    """
    services = {
        "api-gateway": "healthy",
        "bedrock-service": "unknown"
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BEDROCK_SERVICE_URL}/health")
            if response.status_code == 200:
                services["bedrock-service"] = "healthy"
            else:
                services["bedrock-service"] = "unhealthy"
    except:
        services["bedrock-service"] = "unreachable"
    
    return {"services": services}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
