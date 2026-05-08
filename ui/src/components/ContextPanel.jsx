const STEPS = [1, 2, 3, 4, 5];

function agentStep(agent = "") {
  const a = agent.toLowerCase();
  if (a.includes("triage"))     return 1;
  if (a.includes("technical"))  return 2;
  if (a.includes("billing"))    return 3;
  if (a.includes("escalation")) return 5;
  return 1;
}

function agentPill(agent = "") {
  const a = agent.toLowerCase();
  if (a.includes("technical"))  return { bg: "#0f2040", color: "#60a5fa" };
  if (a.includes("billing"))    return { bg: "#2a1800", color: "#fbbf24" };
  if (a.includes("escalation")) return { bg: "#2a0a0a", color: "#f87171" };
  return { bg: "#1a0a38", color: "#a78bfa" };
}

function confidence(agent = "") {
  const a = agent.toLowerCase();
  if (a.includes("triage"))     return 95;
  if (a.includes("escalation")) return 72;
  return 88;
}

export default function ContextPanel({ conversation, onClose }) {
  const agent    = conversation?.agent || "Triage Agent";
  const messages = conversation?.messages || [];
  const step     = agentStep(agent);
  const pill     = agentPill(agent);
  const conf     = confidence(agent);

  return (
    <div style={{ width: 272, minWidth: 272, background: "#111", borderLeft: "1px solid #1e1e1e", display: "flex", flexDirection: "column", height: "100vh", padding: "18px 16px", flexShrink: 0 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 26 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>Context</span>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 20, lineHeight: 1, padding: 0 }}>×</button>
      </div>

      {/* Agent Journey */}
      <div style={{ marginBottom: 26 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#444", letterSpacing: 1.2, marginBottom: 14 }}>AGENT JOURNEY</div>
        <div style={{ display: "flex", alignItems: "center" }}>
          {STEPS.map((s, i) => {
            const isActive = s === step;
            const isPast   = s < step;
            return (
              <div key={s} style={{ display: "flex", alignItems: "center" }}>
                <div style={{
                  width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                  background: isActive ? "#6366f1" : isPast ? "#2d2d60" : "transparent",
                  border: `2px solid ${isActive ? "#6366f1" : isPast ? "#4444aa" : "#333"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 700,
                  color: isActive ? "#fff" : isPast ? "#9999dd" : "#444",
                  boxShadow: isActive ? "0 0 10px rgba(99,102,241,.5)" : "none",
                  transition: "all .2s",
                }}>
                  {s}
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{ width: 12, height: 1, background: isPast ? "#4444aa" : "#222", flexShrink: 0 }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Current State */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#444", letterSpacing: 1.2, marginBottom: 14 }}>CURRENT STATE</div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <span style={{ fontSize: 12, color: "#666" }}>Active Agent</span>
          <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 10, background: pill.bg, color: pill.color }}>{agent}</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: "#666", whiteSpace: "nowrap" }}>Confidence</span>
          <div style={{ flex: 1, height: 5, background: "#222", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ width: `${conf}%`, height: "100%", background: "linear-gradient(90deg,#16a34a,#22c55e)", borderRadius: 4, transition: "width .4s ease" }} />
          </div>
          <span style={{ fontSize: 12, color: "#ccc", whiteSpace: "nowrap" }}>{conf}%</span>
        </div>
      </div>

      {/* Session stats */}
      {messages.length > 0 && (
        <div style={{ background: "#161616", borderRadius: 10, padding: "12px 14px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#444", letterSpacing: 1.2, marginBottom: 10 }}>SESSION</div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: "#666" }}>Messages</span>
            <span style={{ fontSize: 12, color: "#bbb" }}>{messages.length}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12, color: "#666" }}>Status</span>
            <span style={{ fontSize: 12, color: "#22c55e" }}>Active</span>
          </div>
        </div>
      )}

    </div>
  );
}
