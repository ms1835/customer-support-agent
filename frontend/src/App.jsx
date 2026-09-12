import { useEffect, useState } from "react";

const API_URL = "http://localhost:8000";

const App = () => {
  const [conversationId, setConversationId] = useState(1);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function startConversation() {
      const response = await fetch(`${API_URL}/api/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: 2 }),
      });

      const conversation = await response.json();
      setConversationId(conversation.id);
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

    try {
      const response = await fetch(
        `${API_URL}/api/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: "user", content: text }),
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
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "system", content: error.message },
      ]);
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

        {loading && <div className="message system">Sending...</div>}
      </section>

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