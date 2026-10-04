import { useRef } from "react";
import MessageBubble from "./MessageBubble";
import ApprovalCard from "./ApprovalCard";
import StatusBar from "./StatusBar";

export default function ChatPanel({
  conversationId,
  messages,
  streamingContent,
  pendingApproval,
  isEscalated,
  escalationInfo,
  loading,
  status,
  streamStatus,
  content,
  setContent,
  onSend,
  onDecision,
  messagesEndRef,
}) {
  const inputDisabled = !conversationId || loading || pendingApproval || isEscalated;

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <p className="eyebrow">Customer support</p>
          <h2>
            {conversationId
              ? `Conversation #${conversationId}`
              : "Start a conversation"}
            {isEscalated && (
              <span className="header-badge">Escalated</span>
            )}
          </h2>
        </div>
      </header>

      <section className="messages" aria-live="polite">
        {!conversationId && (
          <p className="empty-messages">
            Choose a past conversation or start a new chat.
          </p>
        )}
        {conversationId && messages.length === 0 && !streamingContent && (
          <p className="empty-messages">
            Ask us anything about your order.
          </p>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={`msg-${i}`} message={msg} />
        ))}

        {streamingContent && (
          <div className="message assistant streaming">
            {streamingContent}
            <span className="cursor" aria-hidden="true">▌</span>
          </div>
        )}

        {pendingApproval && (
          <ApprovalCard onDecision={onDecision} disabled={loading} />
        )}

        <div ref={messagesEndRef} />
      </section>

      {isEscalated && (
        <div className="escalation-banner">
          <span className="escalation-icon" aria-hidden="true">👤</span>
          <span>
            {escalationInfo
              ? `Handled by ${escalationInfo.agent_name ?? "a support agent"} · Ticket #${escalationInfo.ticket_id}`
              : "This conversation is being handled by a human support agent."}
          </span>
        </div>
      )}

      <StatusBar streamStatus={streamStatus} status={status} loading={loading} />

      <form className="chat-form" onSubmit={onSend}>
        <input
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={
            isEscalated
              ? "Waiting for agent response..."
              : pendingApproval
              ? "Approve or reject the request above..."
              : "Ask something..."
          }
          disabled={inputDisabled}
          aria-label="Message input"
        />
        <button type="submit" disabled={inputDisabled}>
          Send
        </button>
      </form>
    </section>
  );
}
