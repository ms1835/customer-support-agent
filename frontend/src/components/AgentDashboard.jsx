import MessageBubble from "./MessageBubble";
import StatusBar from "./StatusBar";

const RESOLVED = ["resolved", "closed"];

export default function AgentDashboard({
  selectedTicket,
  ticketMessages,
  agentReply,
  setAgentReply,
  onSendReply,
  onResolve,
  dashboardLoading,
  dashboardStatus,
}) {
  return (
    <section className="chat-panel dashboard-panel">
      <header className="chat-header dashboard-header">
        <div className="dashboard-header-text">
          <p className="eyebrow">Agent dashboard</p>
          <h2 className="dashboard-title">
            {selectedTicket
              ? `Ticket #${selectedTicket.id}`
              : "Select a ticket"}
          </h2>
          {selectedTicket && (
            <p className="dashboard-subtitle">{selectedTicket.escalation_reason}</p>
          )}
        </div>

        {selectedTicket && (
          <div className="dashboard-header-actions">
            {!RESOLVED.includes(selectedTicket.status) ? (
              <button
                className="resolve-btn"
                onClick={onResolve}
                disabled={dashboardLoading}
              >
                ✓ Resolve
              </button>
            ) : (
              <span className="badge badge-resolved resolved-pill">
                Resolved
              </span>
            )}
          </div>
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
          <div className="ticket-meta">
            <span className="meta-item">
              <strong>Status</strong>
              {selectedTicket.status.replace(/_/g, " ")}
            </span>
            <span className="meta-item">
              <strong>Priority</strong>
              {selectedTicket.priority}
            </span>
            <span className="meta-item">
              <strong>Type</strong>
              {selectedTicket.escalation_type.replace(/_/g, " ")}
            </span>
            {selectedTicket.assigned_agent && (
              <span className="meta-item">
                <strong>Agent</strong>
                {selectedTicket.assigned_agent.name}
              </span>
            )}
          </div>

          <section className="messages" aria-live="polite">
            {ticketMessages.length === 0 ? (
              <p className="empty-messages">No messages in this conversation yet.</p>
            ) : (
              ticketMessages.map((msg, i) => (
                <MessageBubble key={`tm-${i}`} message={msg} />
              ))
            )}
          </section>

          {!RESOLVED.includes(selectedTicket.status) && (
            <form className="chat-form" onSubmit={onSendReply}>
              <input
                value={agentReply}
                onChange={(e) => setAgentReply(e.target.value)}
                placeholder="Reply to the customer..."
                disabled={dashboardLoading}
                aria-label="Agent reply"
              />
              <button
                type="submit"
                disabled={dashboardLoading || !agentReply.trim()}
              >
                Reply
              </button>
            </form>
          )}
        </>
      )}

      <StatusBar
        streamStatus=""
        status={dashboardStatus}
        loading={dashboardLoading}
      />
    </section>
  );
}
