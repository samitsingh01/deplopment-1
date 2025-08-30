import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [message, setMessage] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;

    setLoading(true);
    try {
      // Use relative path for API
      const result = await axios.post('/api/chat', {
        message: message
      });
      setResponse(result.data.response);
    } catch (error) {
      setResponse('Error: Unable to get response. Please try again.');
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🤖 AI Chat with Amazon Bedrock</h1>
        <div className="chat-container">
          <form onSubmit={handleSubmit}>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask me anything..."
              rows="4"
              cols="50"
              disabled={loading}
            />
            <br />
            <button type="submit" disabled={loading}>
              {loading ? 'Thinking...' : 'Send Message'}
            </button>
          </form>
          
          {response && (
            <div className="response-box">
              <h3>Response:</h3>
              <p>{response}</p>
            </div>
          )}
        </div>
      </header>
    </div>
  );
}

export default App;
