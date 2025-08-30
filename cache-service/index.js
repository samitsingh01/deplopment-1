const express = require('express');
const redis = require('redis');
const axios = require('axios');
const crypto = require('crypto');

const app = express();
app.use(express.json());

// Redis client setup
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || 'redis://redis:6379'
});

redisClient.on('error', (err) => {
  console.error('Redis Client Error', err);
});

redisClient.on('connect', () => {
  console.log('Connected to Redis');
});

// Connect to Redis
(async () => {
  await redisClient.connect();
})();

// Bedrock service URL
const BEDROCK_SERVICE_URL = process.env.BEDROCK_SERVICE_URL || 'http://bedrock-service:9000';

// Helper function to create cache key
function getCacheKey(prompt) {
  return `prompt:${crypto.createHash('md5').update(prompt).digest('hex')}`;
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'cache-service' });
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({ 
    message: 'Cache Service is running', 
    version: '1.0.0',
    features: ['response-caching', 'ttl-management', 'cache-stats']
  });
});

// Get cache statistics
app.get('/stats', async (req, res) => {
  try {
    const info = await redisClient.info('stats');
    const dbSize = await redisClient.dbSize();
    
    res.json({
      cacheSize: dbSize,
      info: info
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to get cache stats' });
  }
});

// Clear cache endpoint
app.delete('/cache', async (req, res) => {
  try {
    await redisClient.flushAll();
    res.json({ message: 'Cache cleared successfully' });
  } catch (error) {
    res.status(500).json({ error: 'Failed to clear cache' });
  }
});

// Main generate endpoint with caching
app.post('/generate', async (req, res) => {
  const { prompt, useCache = true } = req.body;
  
  if (!prompt) {
    return res.status(400).json({ error: 'Prompt is required' });
  }

  const cacheKey = getCacheKey(prompt);
  console.log(`Processing prompt: ${prompt.substring(0, 50)}...`);

  try {
    // Check cache first if caching is enabled
    if (useCache) {
      const cachedResponse = await redisClient.get(cacheKey);
      if (cachedResponse) {
        console.log('Cache hit for prompt');
        return res.json({
          response: cachedResponse,
          cached: true,
          cacheKey: cacheKey
        });
      }
      console.log('Cache miss for prompt');
    }

    // Call Bedrock service
    console.log('Calling Bedrock service...');
    const bedrockResponse = await axios.post(`${BEDROCK_SERVICE_URL}/generate`, {
      prompt: prompt
    });

    const aiResponse = bedrockResponse.data.response;

    // Cache the response (TTL: 1 hour)
    if (useCache && aiResponse) {
      await redisClient.setEx(cacheKey, 3600, aiResponse);
      console.log('Response cached');
    }

    res.json({
      response: aiResponse,
      cached: false,
      cacheKey: cacheKey
    });

  } catch (error) {
    console.error('Error:', error.message);
    
    if (error.response) {
      res.status(error.response.status).json({
        error: error.response.data || 'Error from Bedrock service'
      });
    } else {
      res.status(500).json({
        error: 'Failed to generate response'
      });
    }
  }
});

// Get cached response by key
app.get('/cache/:key', async (req, res) => {
  try {
    const value = await redisClient.get(req.params.key);
    if (value) {
      res.json({ cached: true, response: value });
    } else {
      res.status(404).json({ cached: false, message: 'Key not found' });
    }
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve from cache' });
  }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Cache Service running on port ${PORT}`);
});
