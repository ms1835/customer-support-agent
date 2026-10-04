export default function MessageBubble({ message }) {
  return (
    <div className="message-wrapper">
      {message.role === "agent" && (
        <p className="message-sender">Support Agent</p>
      )}
      <div className={`message ${message.role}`}>{message.content}</div>
    </div>
  );
}
