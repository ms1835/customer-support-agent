import { useEffect, useRef, useState } from "react";

const API_URL = "http://localhost:8000";
const USER_ID = 2;

function displayMessage(message) {
  if (message.role === "assistant") {
    try {
      const stored = JSON.parse(message.content);
      if (stored.response) return { ...message, content: stored.response };
    } catch {
      // already plain text
    }
  }
  return message;
}

/** Parse an SSE stream from a fetch Response into discrete events. */
async function* readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop(); // keep incomplete trailing chunk
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        yield JSON.parse(line.slice(6)); // { event, data }
      } catch {
        // skip malformed
      }
    }
  }
}

const STATUS_LABELS = {
  thinking: "Thinking...",
  retrieving_documents: "Searching knowledge base...",
  approval_required: "Action requires approval",
};

const App = () => {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [streamStatus, setStreamStatus] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [pendingApproval, setPendingApproval] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, pendingApproval]);

  useEffect(() => {
    async function loadConversations() {
      try {
        setStatus("Loading conversations...");
        const res = await fetch(`${API_URL}/api/conversations?user_id=${USER_ID}`);
        if (!res.ok) throw new Error("Unable to load conversations");
        const saved = await res.json();
        setConversations(saved);
        if (saved.length > 0) selectConversation(saved[0]);
        setStatus("");
      } catch (err) {
        setStatus(err.message);
      }
    }
    loadConversations();
  }, []);

  function selectConversation(conversation) {
    setConversationId(conversation.id);
    setMessages((conversation.messages ?? []).map(displayMessage));
    setContent("");
    setStatus("");
    setStreamStatus("");
    setStreamingContent("");
    setPendingApproval(false);
  }

  async function createConversation() {
    if (loading) return;
    try {
      setStatus("Creating conversation...");
      const res = await fetch(`${API_URL}/api/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: USER_ID }),
      });
      if (!res.ok) throw new Error("Unable to create conversation");
      const conv = await res.json();
      setConversations((c) => [conv, ...c]);
      selectConversation(conv);
    } catch (err) {
      setStatus(err.message);
    }
  }

  /** Handle a single SSE event from either sendMessage or handleDecision. */
  function handleEvent({ event, data }, accRef) {
    switch (event) {
      case "thinking":
        setStreamStatus(STATUS_LABELS.thinking);
        break;
      case "retrieving_documents":
        setStreamStatus(STATUS_LABELS.retrieving_documents);
        break;
      case "tool_started":
        setStreamStatus(`Looking up ${(data.tool ?? "").replace(/_/g, " ")}...`);
        break;
      case "tool_completed":
        setStreamStatus("");
        break;
      case "approval_required":
        setStreamStatus(STATUS_LABELS.approval_required);
        break;
      case "response_token":
        accRef.current += data.token ?? "";
        setStreamingContent(accRef.current);
        setStreamStatus("");
        break;
      case "agent_completed": {
        const finalContent = data.response ?? "";
        setMessages((prev) => [...prev, { role: "assistant", content: finalContent }]);
        setStreamingContent("");
        setStreamStatus("");
        if (data.requires_approval && data.approval_status === "pending") {
          setPendingApproval(true);
        }
        break;
      }
      case "error":
        setStatus(data.message || "An error occurred");
        break;
      default:
        break;
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    const text = content.trim();
    if (!text || !conversationId || loading || pendingApproval) return;

    setContent("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    setStreamStatus("Starting...");
    setStreamingContent("");

    const accumulated = { current: "" };

    try {
      const res = await fetch(
        `${API_URL}/api/conversations/${conversationId}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        }
      );
      if (!res.ok) throw new Error("Failed to send message");

      for await (const evt of readSSE(res)) {
        handleEvent(evt, accumulated);
      }
      setStatus("");
    } catch (err) {
      setStatus(err.message);
      setStreamingContent("");
      setStreamStatus("");
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(decision) {
    if (loading) return;
    setLoading(true);
    setPendingApproval(false);
    setStreamStatus(decision === "approve" ? "Processing approval..." : "Rejecting request...");
    setStreamingContent("");

    const accumulated = { current: "" };

    try {
      const res = await fetch(`${API_URL}/api/agent/${conversationId}/resume/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      if (!res.ok) throw new Error("Failed to process decision");

      for await (const evt of readSSE(res)) {
        handleEvent(evt, accumulated);
      }
      setStatus("");
    } catch (err) {
      setStatus(err.message);
      setStreamingContent("");
      setStreamStatus("");
      setPendingApproval(true); // restore so user can retry
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
          {conversations.map((conv) => (
            <button
              className={`conversation-item ${conv.id === conversationId ? "active" : ""}`}
              key={conv.id}
              onClick={() => selectConversation(conv)}
              disabled={loading}
            >
              <strong>Conversation #{conv.id}</strong>
              <span>
                {conv.messages?.length
                  ? displayMessage(conv.messages.at(-1)).content
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
            <h2>
              {conversationId ? `Conversation #${conversationId}` : "Start a conversation"}
            </h2>
          </div>
        </header>

        <section className="messages">
          {messages.length === 0 && conversationId && !streamingContent && (
            <p className="empty-messages">Ask us anything about your order.</p>
          )}
          {!conversationId && (
            <p className="empty-messages">Choose a past conversation or start a new chat.</p>
          )}

          {messages.map((msg, i) => (
            <div className={`message ${msg.role}`} key={`msg-${i}`}>
              {msg.content}
            </div>
          ))}

          {/* In-progress streaming response */}
          {streamingContent && (
            <div className="message assistant streaming">
              {streamingContent}
              <span className="cursor">▌</span>
            </div>
          )}

          {/* Approval card */}
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

        {/* Stream status indicator */}
        {streamStatus && (
          <p className="status status-loading">{streamStatus}</p>
        )}
        {status && !streamStatus && (
          <p className={`status ${loading ? "status-loading" : "status-error"}`}>
            {status}
          </p>
        )}

        <form onSubmit={sendMessage}>
          <input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              pendingApproval
                ? "Approve or reject the request above first..."
                : "Ask something..."
            }
            disabled={!conversationId || loading || pendingApproval}
          />
          <button disabled={!conversationId || loading || pendingApproval}>Send</button>
        </form>
      </section>
    </main>
  );
};

export default App;
