import { useEffect, useState } from "react";

const API_URL = "http://localhost:8000";

const App = () => {
  const [conversationId, setConversationId] = useState(1);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function startConversation() {
      try {
        setStatus("Starting conversation...");
        const response = await fetch(`${API_URL}/api/conversations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: 2 }),
        });

        if (!response.ok) {
          throw new Error("Unable to start conversation");
        }

        const conversation = await response.json();
        setConversationId(conversation.id);
        setStatus("");
      } catch (error) {
        setStatus(error.message);
      }
    }

    startConversation();
  }, []);

  async function sendMessage(event) {
    event.preventDefault();

    const text = content.trim();
    if (!text || !conversationId || loading) return;

    setContent("");
    setMessages((current) => [...current, { role: "user", content: text }]);
    setLoading(true);
    setStatus("Sending...");

    try {
      const response = await fetch(
        `${API_URL}/api/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        }
      );

      if (!response.ok) {
        throw new Error("Unable to send message");
      }

      const message = await response.json();

      setMessages((current) => [
        ...current,
        { role: message.role, content: message.content },
      ]);
      setStatus("");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="chat">
      <h1>Customer Support</h1>

      <section className="messages">
        {messages.map((message, index) => (
          <div className={`message ${message.role}`} key={index}>
            {message.content}
          </div>
        ))}
      </section>

      {status && (
        <p className={`status ${loading ? "status-loading" : "status-error"}`}>
          {status}
        </p>
      )}

      <form onSubmit={sendMessage}>
        <input
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Ask about an order..."
          disabled={!conversationId || loading}
        />
        <button disabled={!conversationId || loading}>Send</button>
      </form>
    </main>
  );
}

export default App;