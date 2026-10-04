import { useEffect, useRef, useState } from "react";

const API_URL = "http://localhost:8000";
const USER_ID = 2;
const AGENT_ID = 1; 

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
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        yield JSON.parse(line.slice(6));
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
  escalation_started: "Connecting to a human agent...",
};

/* ─────────────────────────── App ─────────────────────────── */
const App = () => {
  /* ── view ── */
  const [view, setView] = useState("chat"); // "chat" | "dashboard"

  /* ── chat state ── */
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [streamStatus, setStreamStatus] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [pendingApproval, setPendingApproval] = useState(false);
  const [isEscalated, setIsEscalated] = useState(false);
  const [escalationInfo, setEscalationInfo] = useState(null); // { ticket_id, agent_name }
  const messagesEndRef = useRef(null);

  /* ── dashboard state ── */
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [ticketMessages, setTicketMessages] = useState([]);
  const [agentReply, setAgentReply] = useState("");
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardStatus, setDashboardStatus] = useState("");

  /* ── scroll ── */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, pendingApproval]);

  /* ── load conversations ── */
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── load tickets when entering dashboard ── */
  useEffect(() => {
    if (view !== "dashboard") return;
    loadTickets();
  }, [view]);

  /* ── helpers ── */
  function selectConversation(conversation) {
    setConversationId(conversation.id);
    setMessages((conversation.messages ?? []).map(displayMessage));
    setContent("");
    setStatus("");
    setStreamStatus("");
    setStreamingContent("");
    setPendingApproval(false);
    const escalated = conversation.status === "escalated";
    setIsEscalated(escalated);
    setEscalationInfo(null);
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

  /* ── SSE event handler ── */
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
      case "escalation_started":
        setStreamStatus(STATUS_LABELS.escalation_started);
        break;
      case "escalation_complete":
        setStreamStatus("");
        if (!data.error) {
          setIsEscalated(true);
          setEscalationInfo({
            ticket_id: data.ticket_id,
            agent_name: data.assigned_agent ?? null,
          });
          // Refresh conversation list to reflect ESCALATED status
          setConversations((prev) =>
            prev.map((c) =>
              c.id === conversationId ? { ...c, status: "escalated" } : c
            )
          );
        }
        break;
      case "escalated":
        // Guard node fired — conversation already escalated before this message
        setStreamStatus("");
        setIsEscalated(true);
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

  /* ── send message ── */
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

  /* ── handle approve / reject ── */
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
      setPendingApproval(true);
    } finally {
      setLoading(false);
    }
  }

  /* ────────── Dashboard helpers ────────── */

  async function loadTickets() {
    try {
      setDashboardLoading(true);
      setDashboardStatus("Loading tickets...");
      const res = await fetch(`${API_URL}/api/tickets/`);
      if (!res.ok) throw new Error("Failed to load tickets");
      setTickets(await res.json());
      setDashboardStatus("");
    } catch (err) {
      setDashboardStatus(err.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  async function selectTicket(ticket) {
    setSelectedTicket(ticket);
    setAgentReply("");
    setDashboardStatus("");
    try {
      // Load full conversation messages for this ticket
      const res = await fetch(`${API_URL}/api/conversations/${ticket.conversation_id}`);
      if (!res.ok) throw new Error("Failed to load conversation");
      const conv = await res.json();
      setTicketMessages((conv.messages ?? []).map(displayMessage));
    } catch (err) {
      setDashboardStatus(err.message);
    }
  }

  async function sendAgentReply(e) {
    e.preventDefault();
    if (!agentReply.trim() || !selectedTicket) return;
    try {
      setDashboardLoading(true);
      const res = await fetch(
        `${API_URL}/api/tickets/${selectedTicket.id}/messages?agent_id=${AGENT_ID}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: agentReply.trim() }),
        }
      );
      if (!res.ok) throw new Error("Failed to send reply");
      const msg = await res.json();
      setTicketMessages((prev) => [...prev, msg]);
      setAgentReply("");
    } catch (err) {
      setDashboardStatus(err.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  async function resolveTicket() {
    if (!selectedTicket) return;
    if (!window.confirm("Mark this ticket as resolved?")) return;
    try {
      setDashboardLoading(true);
      const res = await fetch(`${API_URL}/api/tickets/${selectedTicket.id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error("Failed to resolve ticket");
      const updated = await res.json();
      setSelectedTicket(updated);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setDashboardStatus("Ticket resolved.");
    } catch (err) {
      setDashboardStatus(err.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  /* ────────── Sidebar conversation badge ────────── */
  function convStatusBadge(conv) {
    if (conv.status === "escalated") return <span className="badge badge-escalated">Escalated</span>;
    if (conv.status === "resolved") return <span className="badge badge-resolved">Resolved</span>;
    return null;
  }

  /* ────────── Ticket priority / status badge ────────── */
  function ticketBadge(ticket) {
    const statusClass = {
      open: "badge-open",
      assigned: "badge-assigned",
      in_progress: "badge-inprogress",
      resolved: "badge-resolved",
      closed: "badge-resolved",
    }[ticket.status] ?? "badge-open";
    return <span className={`badge ${statusClass}`}>{ticket.status.replace("_", " ")}</span>;
  }

  /* ─────────────────────── Render ─────────────────────── */
  return (
    <main className="chat-shell">
      {/* ─── Sidebar (shared between views) ─── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Support desk</h1>
          <div className="sidebar-tabs">
            <button
              className={`tab-btn ${view === "chat" ? "active" : ""}`}
              onClick={() => setView("chat")}
            >
              Chat
            </button>
            <button
              className={`tab-btn ${view === "dashboard" ? "active" : ""}`}
              onClick={() => setView("dashboard")}
            >
              Agent
            </button>
          </div>
          {view === "chat" && (
            <button className="new-chat" onClick={createConversation} disabled={loading}>
              + New chat
            </button>
          )}
        </div>

        {view === "chat" ? (
          <div className="conversation-list">
            {conversations.map((conv) => (
              <button
                className={`conversation-item ${conv.id === conversationId ? "active" : ""}`}
                key={conv.id}
                onClick={() => selectConversation(conv)}
                disabled={loading}
              >
                <div className="conv-item-header">
                  <strong>Conversation #{conv.id}</strong>
                  {convStatusBadge(conv)}
                </div>
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
        ) : (
          <div className="conversation-list">
            <p className="sidebar-section-label">Tickets</p>
            {tickets.map((t) => (
              <button
                key={t.id}
                className={`conversation-item ${selectedTicket?.id === t.id ? "active" : ""}`}
                onClick={() => selectTicket(t)}
              >
                <div className="conv-item-header">
                  <strong>Ticket #{t.id}</strong>
                  {ticketBadge(t)}
                </div>
                <span>{t.escalation_reason}</span>
              </button>
            ))}
            {tickets.length === 0 && !dashboardLoading && (
              <p className="empty-list">No tickets yet.</p>
            )}
            <button className="new-chat" style={{ marginTop: 10 }} onClick={loadTickets}>
              ↻ Refresh
            </button>
          </div>
        )}
      </aside>

      {/* ─── Chat Panel ─── */}
      {view === "chat" && (
        <section className="chat-panel">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Customer support</p>
              <h2>
                {conversationId ? `Conversation #${conversationId}` : "Start a conversation"}
                {isEscalated && <span className="header-badge">Escalated</span>}
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
              <div key={`msg-${i}`} className="message-wrapper">
                {msg.role === "agent" && (
                  <p className="message-sender">Support Agent</p>
                )}
                <div className={`message ${msg.role}`}>
                  {msg.content}
                </div>
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

          {/* Escalation banner */}
          {isEscalated && (
            <div className="escalation-banner">
              <span className="escalation-icon">👤</span>
              <span>
                {escalationInfo
                  ? `Handled by ${escalationInfo.agent_name ?? "a support agent"} · Ticket #${escalationInfo.ticket_id}`
                  : "This conversation is being handled by a human support agent."}
              </span>
            </div>
          )}

          {/* Stream status indicator */}
          {streamStatus && <p className="status status-loading">{streamStatus}</p>}
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
                isEscalated
                  ? "Waiting for agent response..."
                  : pendingApproval
                  ? "Approve or reject the request above first..."
                  : "Ask something..."
              }
              disabled={!conversationId || loading || pendingApproval || isEscalated}
            />
            <button disabled={!conversationId || loading || pendingApproval || isEscalated}>
              Send
            </button>
          </form>
        </section>
      )}

      {/* ─── Agent Dashboard ─── */}
      {view === "dashboard" && (
        <section className="chat-panel dashboard-panel">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Agent dashboard</p>
              <h2>
                {selectedTicket
                  ? `Ticket #${selectedTicket.id} — ${selectedTicket.escalation_reason}`
                  : "Select a ticket"}
              </h2>
            </div>
            {selectedTicket && selectedTicket.status !== "resolved" && selectedTicket.status !== "closed" && (
              <button
                className="resolve-btn"
                onClick={resolveTicket}
                disabled={dashboardLoading}
              >
                ✓ Resolve
              </button>
            )}
            {selectedTicket && (selectedTicket.status === "resolved" || selectedTicket.status === "closed") && (
              <span className="badge badge-resolved" style={{ padding: "6px 12px" }}>Resolved</span>
            )}
          </header>

          {!selectedTicket ? (
            <div className="messages">
              <p className="empty-messages">
                {dashboardLoading ? "Loading..." : "Select a ticket from the sidebar."}
              </p>
            </div>
          ) : (
            <>
              {/* Ticket meta */}
              <div className="ticket-meta">
                <span className="meta-item">
                  <strong>Status:</strong> {selectedTicket.status.replace("_", " ")}
                </span>
                <span className="meta-item">
                  <strong>Priority:</strong> {selectedTicket.priority}
                </span>
                <span className="meta-item">
                  <strong>Type:</strong> {selectedTicket.escalation_type.replace(/_/g, " ")}
                </span>
                {selectedTicket.assigned_agent && (
                  <span className="meta-item">
                    <strong>Assigned:</strong> {selectedTicket.assigned_agent.name}
                  </span>
                )}
              </div>

              {/* Conversation thread */}
              <section className="messages">
                {ticketMessages.map((msg, i) => (
                  <div key={`tm-${i}`} className="message-wrapper">
                    {msg.role === "agent" && (
                      <p className="message-sender">Support Agent</p>
                    )}
                    <div className={`message ${msg.role}`}>{msg.content}</div>
                  </div>
                ))}
                {ticketMessages.length === 0 && (
                  <p className="empty-messages">No messages yet.</p>
                )}
              </section>

              {/* Agent reply form */}
              {selectedTicket.status !== "resolved" && selectedTicket.status !== "closed" && (
                <form onSubmit={sendAgentReply}>
                  <input
                    value={agentReply}
                    onChange={(e) => setAgentReply(e.target.value)}
                    placeholder="Type your reply to the customer..."
                    disabled={dashboardLoading}
                  />
                  <button disabled={dashboardLoading || !agentReply.trim()}>Reply</button>
                </form>
              )}
            </>
          )}

          {dashboardStatus && (
            <p className={`status ${dashboardLoading ? "status-loading" : "status-error"}`}>
              {dashboardStatus}
            </p>
          )}
        </section>
      )}
    </main>
  );
};

export default App;
