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
app = FastAPI(title="API Gateway", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs
CACHE_SERVICE_URL = os.getenv("CACHE_SERVICE_URL", "http://cache-service:5000")
BEDROCK_SERVICE_URL = os.getenv("BEDROCK_SERVICE_URL", "http://bedrock-service:9000")

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    useCache: bool = True

class ChatResponse(BaseModel):
    response: str
    cached: bool = False

class HealthResponse(BaseModel):
    status: str
    service: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "API Gateway is running", 
        "version": "2.0.0",
        "features": ["caching", "bedrock-integration"]
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Forward chat requests to the Cache service (which handles Bedrock)
    """
    try:
        logger.info(f"Received chat request: {request.message[:50]}...")
        logger.info(f"Use cache: {request.useCache}")
        
        # Forward to cache service
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{CACHE_SERVICE_URL}/generate",
                json={
                    "prompt": request.message,
                    "useCache": request.useCache
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Cache service returned status {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Error from cache service"
                )
            
            result = response.json()
            logger.info(f"Response received (cached: {result.get('cached', False)})")
            
            return ChatResponse(
                response=result.get("response", "No response generated"),
                cached=result.get("cached", False)
            )
            
    except httpx.RequestError as e:
        logger.error(f"Error connecting to cache service: {str(e)}")
        # Fallback to direct Bedrock call
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{BEDROCK_SERVICE_URL}/generate",
                    json={"prompt": request.message}
                )
                result = response.json()
                return ChatResponse(
                    response=result.get("response", "No response generated"),
                    cached=False
                )
        except:
            raise HTTPException(status_code=503, detail="Services unavailable")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/services/status")
async def services_status():
    """Check the status of all backend services"""
    services = {
        "api-gateway": "healthy",
        "cache-service": "unknown",
        "bedrock-service": "unknown"
    }
    
    # Check cache service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{CACHE_SERVICE_URL}/health")
            if response.status_code == 200:
                services["cache-service"] = "healthy"
    except:
        services["cache-service"] = "unreachable"
    
    # Check bedrock service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BEDROCK_SERVICE_URL}/health")
            if response.status_code == 200:
                services["bedrock-service"] = "healthy"
    except:
        services["bedrock-service"] = "unreachable"
    
    return {"services": services}

@app.delete("/cache")
async def clear_cache():
    """Clear the cache"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.delete(f"{CACHE_SERVICE_URL}/cache")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
