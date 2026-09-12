import { useEffect, useState } from "react";

const API_URL = "http://localhost:8000";
const USER_ID = 2;

const App = () => {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function loadConversations() {
      try {
        setStatus("Loading conversations...");
        const response = await fetch(
          `${API_URL}/api/conversations?user_id=${USER_ID}`
        );

        if (!response.ok) {
          throw new Error("Unable to load conversations");
        }

        const savedConversations = await response.json();
        setConversations(savedConversations);

        if (savedConversations.length > 0) {
          selectConversation(savedConversations[0]);
        }
        setStatus("");
      } catch (error) {
        setStatus(error.message);
      }
    }

    loadConversations();
  }, []);

  function selectConversation(conversation) {
    setConversationId(conversation.id);
    setMessages(conversation.messages ?? []);
    setContent("");
    setStatus("");
  }

  async function createConversation() {
    if (loading) return;

    try {
      setStatus("Creating conversation...");
      const response = await fetch(`${API_URL}/api/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: USER_ID }),
      });

      if (!response.ok) {
        throw new Error("Unable to create conversation");
      }

      const conversation = await response.json();
      setConversations((current) => [conversation, ...current]);
      selectConversation(conversation);
    } catch (error) {
      setStatus(error.message);
    }
  }

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
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === conversationId
            ? { ...conversation, messages: [...(conversation.messages ?? []), { role: "user", content: text }, message] }
            : conversation
        )
      );
      setStatus("");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="chat-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Support desk</h1>
          <button className="new-chat" onClick={createConversation} disabled={loading}>
            + New chat
          </button>
        </div>

        <div className="conversation-list">
          {conversations.map((conversation) => (
            <button
              className={`conversation-item ${conversation.id === conversationId ? "active" : ""}`}
              key={conversation.id}
              onClick={() => selectConversation(conversation)}
              disabled={loading}
            >
              <strong>Conversation #{conversation.id}</strong>
              <span>{conversation.messages?.at(-1)?.content ?? "No messages yet"}</span>
            </button>
          ))}
          {conversations.length === 0 && !status && (
            <p className="empty-list">No conversations yet.</p>
          )}
        </div>
      </aside>

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Customer support</p>
            <h2>{conversationId ? `Conversation #${conversationId}` : "Start a conversation"}</h2>
          </div>
        </header>

        <section className="messages">
          {messages.length === 0 && conversationId && (
            <p className="empty-messages">Ask us anything about your order.</p>
          )}
          {!conversationId && !status && (
            <p className="empty-messages">Choose a past conversation or start a new chat.</p>
          )}
          {messages.map((message, index) => (
            <div className={`message ${message.role}`} key={`${message.id ?? "message"}-${index}`}>
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
      </section>
    </main>
  );
}

export default App;