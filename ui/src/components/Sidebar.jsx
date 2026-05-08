import { useState } from "react";

const CAT_STYLE = {
  "Technical Support": { bg: "#0f2040", color: "#60a5fa" },
  "Billing Support":   { bg: "#2a1800", color: "#fbbf24" },
  "Human Specialist":  { bg: "#1a0a38", color: "#a78bfa" },
};

function getCategory(agent = "") {
  const a = agent.toLowerCase();
  if (a.includes("billing")) return "Billing Support";
  if (a.includes("escalation")) return "Human Specialist";
  return "Technical Support";
}

const SEEDS = [
  { id: "__s1", label: "AWS Credential Issue",    preview: "My alerts stopped firing after rotating AWS keys", category: "Technical Support", time: "5m", unread: true },
  { id: "__s2", label: "Billing Question",         preview: "I need to upgrade to Enterprise plan",            category: "Billing Support",   msgCount: 2 },
  { id: "__s3", label: "SSO Configuration",        preview: "Help setting up SAML authentication",             category: "Technical Support", msgCount: 1 },
  { id: "__s4", label: "Account Access",           preview: "Team member locked out of dashboard",             category: "Human Specialist",  msgCount: 2 },
];

export default function Sidebar({ conversations, activeId, onSelect, onNew, onClearAll, loading }) {
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch]       = useState("");

  const list = conversations.length > 0 ? conversations : SEEDS;
  const q    = search.toLowerCase();
  const filtered = list.filter(c =>
    c.label.toLowerCase().includes(q) || (c.preview || "").toLowerCase().includes(q)
  );

  if (collapsed) {
    return (
      <div style={{ width: 52, background: "#111", borderRight: "1px solid #1e1e1e", display: "flex", flexDirection: "column", alignItems: "center", padding: "14px 0", gap: 16, transition: "width .2s" }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: "#6366f1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15, cursor: "pointer" }} onClick={() => setCollapsed(false)}>⚡</div>
        <button onClick={() => setCollapsed(false)} style={btnReset}>›</button>
      </div>
    );
  }

  return (
    <div style={{ width: 240, minWidth: 240, background: "#111", borderRight: "1px solid #1e1e1e", display: "flex", flexDirection: "column", height: "100vh" }}>

      {/* Logo row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 12px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: "#6366f1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>⚡</div>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>CloudDash AI</span>
        </div>
        <button onClick={() => setCollapsed(true)} style={{ ...btnReset, border: "1px solid #2a2a2a", borderRadius: 6, padding: "3px 7px", color: "#555", fontSize: 11 }}>‹</button>
      </div>

      {/* New conversation */}
      <div style={{ padding: "0 10px 10px" }}>
        <button onClick={onNew} disabled={loading} style={{ width: "100%", background: "transparent", border: "1px solid #2a2a2a", borderRadius: 8, padding: "9px 12px", color: "#ccc", fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ fontSize: 17 }}>+</span>{loading ? "Starting…" : "New Conversation"}
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: "0 10px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, background: "#1a1a1a", border: "1px solid #242424", borderRadius: 8, padding: "7px 10px" }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#555" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search conversations..." style={{ background: "none", border: "none", outline: "none", color: "#bbb", fontSize: 12, flex: 1, fontFamily: "inherit" }} />
        </div>
      </div>

      {/* Conversation list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 6px" }}>
        {filtered.map(c => {
          const isSeed   = c.id?.startsWith("__s");
          const isActive = c.id === activeId;
          const category = c.category || getCategory(c.agent);
          const cs       = CAT_STYLE[category] || CAT_STYLE["Technical Support"];
          return (
            <div key={c.id} onClick={() => !isSeed && onSelect(c.id)}
              style={{ padding: "9px 9px", borderRadius: 8, marginBottom: 2, cursor: isSeed ? "default" : "pointer", background: isActive ? "#16163a" : "transparent", borderLeft: `2px solid ${isActive ? "#6366f1" : "transparent"}`, transition: "background .15s" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#dde", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginRight: 6 }}>{c.label}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                  {c.unread && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#6366f1" }} />}
                  <span style={{ fontSize: 10, color: "#555" }}>{c.time || (c.msgCount ? `${c.msgCount}` : "")}</span>
                </div>
              </div>
              <p style={{ fontSize: 11, color: "#555", margin: "0 0 5px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.preview || ""}</p>
              <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 10, background: cs.bg, color: cs.color }}>{category}</span>
            </div>
          );
        })}
      </div>

      {/* Bottom nav */}
      <div style={{ borderTop: "1px solid #1e1e1e", padding: "10px 6px" }}>
        <a href="https://drive.google.com/drive/folders/1LqvnFS2ZEwXPmbTtJUslLYrfOV3N9_Rq?usp=drive_link" target="_blank" rel="noopener noreferrer" style={navItem}>
          <BookIcon /> Knowledge Base
        </a>
        <div style={navItem}><AlertIcon /> Escalations</div>
        <div style={navItem}><GearIcon /> Settings</div>

        <div style={{ borderTop: "1px solid #1e1e1e", marginTop: 6, paddingTop: 6 }}>
          <button
            onClick={onClearAll}
            disabled={conversations.length === 0}
            style={{ ...btnReset, display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 10px", borderRadius: 8, color: conversations.length > 0 ? "#ef4444" : "#333", fontSize: 12, cursor: conversations.length > 0 ? "pointer" : "not-allowed", transition: "background .15s" }}
            onMouseEnter={e => { if (conversations.length > 0) e.currentTarget.style.background = "#1f0a0a"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
          >
            <TrashIcon /> Clear All Sessions
          </button>
        </div>
      </div>

    </div>
  );
}

const btnReset = { background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" };
const navItem  = { display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 8, color: "#666", fontSize: 12, textDecoration: "none", cursor: "pointer" };

function BookIcon()  { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>; }
function AlertIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>; }
function GearIcon()  { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>; }
function TrashIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>; }
