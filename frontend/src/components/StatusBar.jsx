export default function StatusBar({ streamStatus, status, loading }) {
  if (streamStatus) {
    return <p className="status status-loading">{streamStatus}</p>;
  }
  if (status) {
    return (
      <p className={`status ${loading ? "status-loading" : "status-error"}`}>
        {status}
      </p>
    );
  }
  return null;
}
