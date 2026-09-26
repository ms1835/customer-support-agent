import { useEffect, useRef, useState } from "react";

const API_URL = "http://localhost:8000";
const USER_ID = 2;

function displayMessage(message) {
  if (message.role === "assistant") {
    try {
      const storedResponse = JSON.parse(message.content);
      if (storedResponse.response) {
        return { ...message, content: storedResponse.response };
      }
    } catch {
      // Current assistant messages are already plain text.
    }
  }
  return message;
}

const App = () => {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [pendingApproval, setPendingApproval] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingApproval]);

  useEffect(() => {
    async function loadConversations() {
      try {
        setStatus("Loading conversations...");
        const response = await fetch(
          `${API_URL}/api/conversations?user_id=${USER_ID}`
        );
        if (!response.ok) throw new Error("Unable to load conversations");
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
    setMessages((conversation.messages ?? []).map(displayMessage));
    setContent("");
    setStatus("");
    setPendingApproval(false);
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
      if (!response.ok) throw new Error("Unable to create conversation");
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
    if (!text || !conversationId || loading || pendingApproval) return;

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
      if (!response.ok) throw new Error("Unable to send message");

      const data = await response.json();
      const assistantMessage = { role: "assistant", content: data.response };
      setMessages((current) => [...current, assistantMessage]);
      setConversations((current) =>
        current.map((c) =>
          c.id === conversationId
            ? {
                ...c,
                messages: [
                  ...(c.messages ?? []),
                  { role: "user", content: text },
                  assistantMessage,
                ],
              }
            : c
        )
      );

      if (data.requires_approval && data.approval_status === "pending") {
        setPendingApproval(true);
      }
      setStatus("");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(decision) {
    if (loading) return;
    setLoading(true);
    setPendingApproval(false);
    setStatus(decision === "approve" ? "Processing approval..." : "Rejecting request...");

    try {
      const response = await fetch(
        `${API_URL}/api/agent/${conversationId}/resume`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        }
      );
      if (!response.ok) throw new Error("Unable to process decision");

      const data = await response.json();
      const assistantMessage = { role: "assistant", content: data.response };
      setMessages((current) => [...current, assistantMessage]);
      setConversations((current) =>
        current.map((c) =>
          c.id === conversationId
            ? { ...c, messages: [...(c.messages ?? []), assistantMessage] }
            : c
        )
      );
      setStatus("");
    } catch (error) {
      setStatus(error.message);
      setPendingApproval(true);
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
              <span>
                {conversation.messages?.length
                  ? displayMessage(conversation.messages.at(-1)).content
                  : "No messages yet"}
              </span>
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

          {pendingApproval && (
            <div className="approval-card">
              <p className="approval-prompt">
                This action requires your approval. Would you like to proceed?
              </p>
              <div className="approval-actions">
                <button
                  className="approve-btn"
                  onClick={() => handleDecision("approve")}
                  disabled={loading}
                >
                  Approve
                </button>
                <button
                  className="reject-btn"
                  onClick={() => handleDecision("reject")}
                  disabled={loading}
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
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
            placeholder={pendingApproval ? "Approve or reject the request above first..." : "Ask about an order..."}
            disabled={!conversationId || loading || pendingApproval}
          />
          <button disabled={!conversationId || loading || pendingApproval}>Send</button>
        </form>
      </section>
    </main>
  );
};

export default App;
