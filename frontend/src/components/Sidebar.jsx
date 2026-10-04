function convStatusBadge(conv) {
  if (conv.status === "escalated")
    return <span className="badge badge-escalated">Escalated</span>;
  if (conv.status === "resolved")
    return <span className="badge badge-resolved">Resolved</span>;
  return null;
}

function ticketBadge(ticket) {
  const cls = {
    open: "badge-open",
    assigned: "badge-assigned",
    in_progress: "badge-inprogress",
    resolved: "badge-resolved",
    closed: "badge-resolved",
  }[ticket.status] ?? "badge-open";
  return <span className={`badge ${cls}`}>{ticket.status.replace(/_/g, " ")}</span>;
}

export default function Sidebar({
  view,
  setView,
  isAgent,
  user,
  onLogout,
  // chat props
  conversations,
  conversationId,
  onSelectConversation,
  onNewConversation,
  loading,
  displayMessage,
  // dashboard props
  tickets,
  selectedTicketId,
  onSelectTicket,
  onRefreshTickets,
  dashboardLoading,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">Support desk</h1>

        {/* Only show tabs if user has access to both views (admin) */}
        {user.role === "admin" && (
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
              Tickets
            </button>
          </div>
        )}

        {view === "chat" && (
          <button
            className="new-chat"
            onClick={onNewConversation}
            disabled={loading}
          >
            + New chat
          </button>
        )}

        <div className="auth-bar">
          <div className="auth-info">
            <span className="auth-role">{user.role}</span>
          </div>
          <button className="logout-btn" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </div>

      {view === "chat" ? (
        <div className="conversation-list">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              className={`conversation-item ${conv.id === conversationId ? "active" : ""}`}
              onClick={() => onSelectConversation(conv)}
              disabled={loading}
            >
              <div className="conv-item-header">
                <strong>#{conv.id}</strong>
                {convStatusBadge(conv)}
              </div>
              <span>
                {conv.messages?.length
                  ? displayMessage(conv.messages.at(-1)).content
                  : "No messages yet"}
              </span>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="empty-list">No conversations yet.</p>
          )}
        </div>
      ) : (
        <div className="conversation-list">
          <p className="sidebar-section-label">Tickets</p>
          {tickets.map((t) => (
            <button
              key={t.id}
              className={`conversation-item ${selectedTicketId === t.id ? "active" : ""}`}
              onClick={() => onSelectTicket(t)}
            >
              <div className="conv-item-header">
                <strong>#{t.id}</strong>
                {ticketBadge(t)}
              </div>
              <span className="item-reason">{t.escalation_reason}</span>
            </button>
          ))}
          {tickets.length === 0 && !dashboardLoading && (
            <p className="empty-list">No tickets yet.</p>
          )}
          <button
            className="refresh-btn"
            onClick={onRefreshTickets}
            disabled={dashboardLoading}
          >
            ↻ Refresh
          </button>
        </div>
      )}
    </aside>
  );
}
