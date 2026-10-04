import { useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthContext";
import LoginPage from "./LoginPage";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import AgentDashboard from "./components/AgentDashboard";

const API_URL = "http://localhost:8000";

/* ── Helpers ── */

export function displayMessage(message) {
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
      try { yield JSON.parse(line.slice(6)); } catch { /* skip */ }
    }
  }
}

/* ── Root ── */
export default function App() {
  const { user, apiFetch, logout } = useAuth();
  if (!user) return <LoginPage />;
  return <AuthenticatedApp user={user} apiFetch={apiFetch} logout={logout} />;
}

/* ── Authenticated shell ── */
function AuthenticatedApp({ user, apiFetch, logout }) {
  const isAgent = user.role === "agent" || user.role === "admin";
  const [view, setView] = useState(isAgent ? "dashboard" : "chat");

  /* chat state */
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
  const [escalationInfo, setEscalationInfo] = useState(null);
  const messagesEndRef = useRef(null);

  /* dashboard state */
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [ticketMessages, setTicketMessages] = useState([]);
  const [agentReply, setAgentReply] = useState("");
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardStatus, setDashboardStatus] = useState("");

  /* scroll to bottom */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, pendingApproval]);

  /* load conversations when entering chat view */
  useEffect(() => {
    if (view !== "chat") return;
    loadConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  /* load tickets when entering dashboard view */
  useEffect(() => {
    if (view !== "dashboard") return;
    loadTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  /* ── Chat actions ── */

  async function loadConversations() {
    try {
      setStatus("Loading...");
      const res = await apiFetch(`${API_URL}/api/conversations?user_id=${user.id}`);
      if (!res.ok) throw new Error("Unable to load conversations");
      const saved = await res.json();
      setConversations(saved);
      if (saved.length > 0) applyConversation(saved[0]);
      setStatus("");
    } catch (err) {
      setStatus(err.message);
    }
  }

  function applyConversation(conv) {
    setConversationId(conv.id);
    setMessages((conv.messages ?? []).map(displayMessage));
    setContent("");
    setStatus("");
    setStreamStatus("");
    setStreamingContent("");
    setPendingApproval(false);
    setIsEscalated(conv.status === "escalated");
    setEscalationInfo(null);
  }

  async function createConversation() {
    if (loading) return;
    try {
      setStatus("Creating...");
      const res = await apiFetch(`${API_URL}/api/conversations`, {
        method: "POST",
        body: JSON.stringify({ user_id: user.id }),
      });
      if (!res.ok) throw new Error("Unable to create conversation");
      const conv = await res.json();
      setConversations((c) => [conv, ...c]);
      applyConversation(conv);
    } catch (err) {
      setStatus(err.message);
    }
  }

  function handleSSEEvent({ event, data }, accRef) {
    switch (event) {
      case "thinking":
        setStreamStatus("Thinking...");
        break;
      case "retrieving_documents":
        setStreamStatus("Searching knowledge base...");
        break;
      case "tool_started":
        setStreamStatus(`Looking up ${(data.tool ?? "").replace(/_/g, " ")}...`);
        break;
      case "tool_completed":
        setStreamStatus("");
        break;
      case "approval_required":
        setStreamStatus("Action requires approval");
        break;
      case "escalation_started":
        setStreamStatus("Connecting to a human agent...");
        break;
      case "escalation_complete":
        setStreamStatus("");
        if (!data.error) {
          setIsEscalated(true);
          setEscalationInfo({ ticket_id: data.ticket_id, agent_name: data.assigned_agent ?? null });
          setConversations((prev) =>
            prev.map((c) => c.id === conversationId ? { ...c, status: "escalated" } : c)
          );
        }
        break;
      case "escalated":
        setStreamStatus("");
        setIsEscalated(true);
        break;
      case "response_token":
        accRef.current += data.token ?? "";
        setStreamingContent(accRef.current);
        setStreamStatus("");
        break;
      case "agent_completed":
        setMessages((prev) => [...prev, { role: "assistant", content: data.response ?? "" }]);
        setStreamingContent("");
        setStreamStatus("");
        if (data.requires_approval && data.approval_status === "pending") {
          setPendingApproval(true);
        }
        break;
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
    const acc = { current: "" };

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(
        `${API_URL}/api/conversations/${conversationId}/messages/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ content: text }),
        }
      );
      if (!res.ok) throw new Error("Failed to send message");
      for await (const evt of readSSE(res)) handleSSEEvent(evt, acc);
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
    setStreamStatus(decision === "approve" ? "Processing approval..." : "Rejecting...");
    setStreamingContent("");
    const acc = { current: "" };

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_URL}/api/agent/${conversationId}/resume/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ decision }),
      });
      if (!res.ok) throw new Error("Failed to process decision");
      for await (const evt of readSSE(res)) handleSSEEvent(evt, acc);
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

  /* ── Dashboard actions ── */

  async function loadTickets() {
    try {
      setDashboardLoading(true);
      setDashboardStatus("Loading tickets...");
      const res = await apiFetch(`${API_URL}/api/tickets/`);
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
      const res = await apiFetch(`${API_URL}/api/conversations/${ticket.conversation_id}`);
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
      const res = await apiFetch(`${API_URL}/api/tickets/${selectedTicket.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: agentReply.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to send reply");
      }
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
    if (!selectedTicket || !window.confirm("Mark this ticket as resolved?")) return;
    try {
      setDashboardLoading(true);
      const res = await apiFetch(`${API_URL}/api/tickets/${selectedTicket.id}/resolve`, {
        method: "POST",
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

  /* ── Render ── */
  return (
    <main className="chat-shell">
      <Sidebar
        view={view}
        setView={setView}
        isAgent={isAgent}
        user={user}
        onLogout={logout}
        conversations={conversations}
        conversationId={conversationId}
        onSelectConversation={applyConversation}
        onNewConversation={createConversation}
        loading={loading}
        displayMessage={displayMessage}
        tickets={tickets}
        selectedTicketId={selectedTicket?.id}
        onSelectTicket={selectTicket}
        onRefreshTickets={loadTickets}
        dashboardLoading={dashboardLoading}
      />

      {view === "chat" && (
        <ChatPanel
          conversationId={conversationId}
          messages={messages}
          streamingContent={streamingContent}
          pendingApproval={pendingApproval}
          isEscalated={isEscalated}
          escalationInfo={escalationInfo}
          loading={loading}
          status={status}
          streamStatus={streamStatus}
          content={content}
          setContent={setContent}
          onSend={sendMessage}
          onDecision={handleDecision}
          messagesEndRef={messagesEndRef}
        />
      )}

      {view === "dashboard" && (
        <AgentDashboard
          selectedTicket={selectedTicket}
          ticketMessages={ticketMessages}
          agentReply={agentReply}
          setAgentReply={setAgentReply}
          onSendReply={sendAgentReply}
          onResolve={resolveTicket}
          dashboardLoading={dashboardLoading}
          dashboardStatus={dashboardStatus}
        />
      )}
    </main>
  );
}
