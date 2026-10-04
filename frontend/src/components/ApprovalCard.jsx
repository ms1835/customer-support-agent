export default function ApprovalCard({ onDecision, disabled }) {
  return (
    <div className="approval-card">
      <p className="approval-prompt">
        This action requires your approval. Would you like to proceed?
      </p>
      <div className="approval-actions">
        <button
          className="approve-btn"
          onClick={() => onDecision("approve")}
          disabled={disabled}
        >
          Approve
        </button>
        <button
          className="reject-btn"
          onClick={() => onDecision("reject")}
          disabled={disabled}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
