const S = {
  wrapper: (role) => ({
    display: "flex",
    flexDirection: "column",
    alignItems: role === "user" ? "flex-end" : "flex-start",
    gap: 4,
  }),
  bubble: (role) => ({
    maxWidth: "72%",
    padding: "10px 14px",
    borderRadius: role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
    background: role === "user" ? "#1d4ed8" : "#1e293b",
    color: "#e2e8f0",
    fontSize: 14,
    lineHeight: 1.6,
    wordBreak: "break-word",
  }),
  agentLabel: { fontSize: 11, color: "#475569", marginBottom: 2 },
  sources: {
    fontSize: 11,
    color: "#64748b",
    borderTop: "1px solid #334155",
    marginTop: 6,
    paddingTop: 6,
    display: "flex",
    flexWrap: "wrap",
    gap: 4,
  },
  sourceChip: {
    background: "#0f2744",
    color: "#38bdf8",
    padding: "1px 7px",
    borderRadius: 10,
    fontSize: 10,
  },
  ticket: {
    marginTop: 8,
    padding: "6px 10px",
    background: "#1a1a2e",
    border: "1px solid #334155",
    borderRadius: 8,
    fontSize: 11,
    color: "#94a3b8",
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  ticketRef: {
    fontFamily: "monospace",
    color: "#fbbf24",
    fontWeight: 700,
    letterSpacing: 1,
  },
  sla: {
    color: "#64748b",
  },
  systemBubble: {
    maxWidth: "72%",
    padding: "8px 12px",
    borderRadius: 8,
    background: "#1c1c1c",
    border: "1px solid #334155",
    color: "#64748b",
    fontSize: 12,
    fontStyle: "italic",
  },
};

import ReactMarkdown from "react-markdown";

export default function MessageBubble({ msg }) {
  const isSystem = msg.agent === "system" || msg.agent === "guardrail";

  if (isSystem) {
    return (
      <div style={S.wrapper("assistant")}>
        <div style={S.systemBubble}>{msg.content}</div>
      </div>
    );
  }

  const ticket = msg.metadata?.ticket_ref;
  const sla = msg.metadata?.sla;
  const urgency = msg.metadata?.urgency;

  return (
    <div style={S.wrapper(msg.role)}>
      {msg.role === "assistant" && msg.agent && (
        <div style={S.agentLabel}>{msg.agent}</div>
      )}
      <div style={S.bubble(msg.role)}>
        <div className="md"><ReactMarkdown>{msg.content}</ReactMarkdown></div>

        {msg.sources?.length > 0 && (
          <div style={S.sources}>
            {msg.sources.map((s, i) => (
              <span key={i} style={S.sourceChip}>{s}</span>
            ))}
          </div>
        )}

        {ticket && (
          <div style={S.ticket}>
            <span>Ticket</span>
            <span style={S.ticketRef}>#{ticket}</span>
            {urgency && <span style={{ color: urgency === "high" || urgency === "critical" ? "#f87171" : "#64748b" }}>
              {urgency.toUpperCase()}
            </span>}
            {sla && <span style={S.sla}>· Response within {sla}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
