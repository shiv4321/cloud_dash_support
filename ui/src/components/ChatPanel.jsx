import { useEffect, useRef, useState } from "react";
import { sendMessage, startConversation } from "../api";
import MessageBubble from "./MessageBubble";

const CHIPS = [
  "My alerts stopped firing",
  "Upgrade to Enterprise",
  "SSO setup help",
  "Billing question",
];

function agentBg(a = "") {
  if (a.toLowerCase().includes("technical"))  return "#0f2040";
  if (a.toLowerCase().includes("billing"))    return "#2a1800";
  if (a.toLowerCase().includes("escalation")) return "#2a0a0a";
  return "#1a0a38";
}
function agentFg(a = "") {
  if (a.toLowerCase().includes("technical"))  return "#60a5fa";
  if (a.toLowerCase().includes("billing"))    return "#fbbf24";
  if (a.toLowerCase().includes("escalation")) return "#f87171";
  return "#a78bfa";
}

const SESSION_EXPIRED_MSG = {
  role: "assistant",
  content: "Session expired (server restarted). Reconnecting automatically — your message has been resent.",
  agent: "system",
  sources: [],
};

export default function ChatPanel({ conversation, onUpdate, onReset, onNew, onToggleContext, contextOpen }) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages]);

  const hasMessages = conversation?.messages?.length > 0;
  const agent = conversation?.agent || "Triage Agent";

  async function handleSend(textOverride) {
    const text = (textOverride !== undefined ? textOverride : input).trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);

    // No active conversation — create session, show user message immediately, then send
    if (!conversation) {
      try {
        const conv = await onNew();
        if (!conv) { setSending(false); return; }

        const userMsg = { role: "user", content: text, agent: null, sources: [] };
        onUpdate({ messages: [userMsg] }, conv.id);          // user message appears instantly

        const res = await sendMessage(conv.id, text);
        const assistantMsg = {
          role: "assistant", content: res.response,
          agent: res.agent, sources: res.sources || [], metadata: res.metadata || {},
        };
        onUpdate({ messages: [userMsg, assistantMsg], agent: res.agent }, conv.id);
      } catch {
        // swallow — no conv to update
      } finally {
        setSending(false);
      }
      return;
    }

    const userMsg = { role: "user", content: text, agent: null, sources: [] };
    onUpdate({ messages: [...conversation.messages, userMsg] }, conversation.id);

    try {
      let convId = conversation.id;
      let currentMessages = [...conversation.messages, userMsg];

      let res;
      try {
        res = await sendMessage(convId, text);
      } catch (err) {
        if (err.status === 404) {
          currentMessages = [...currentMessages, SESSION_EXPIRED_MSG];
          onUpdate({ messages: currentMessages });
          const fresh = await startConversation();
          convId = fresh.conversation_id;
          onReset(convId, fresh.trace_id);
          res = await sendMessage(convId, text);
        } else {
          throw err;
        }
      }

      const assistantMsg = {
        role: "assistant",
        content: res.response,
        agent: res.agent,
        sources: res.sources || [],
        metadata: res.metadata || {},
      };
      onUpdate({ messages: [...currentMessages, assistantMsg], agent: res.agent }, conversation.id);
    } catch (err) {
      onUpdate({
        messages: [
          ...conversation.messages,
          userMsg,
          { role: "assistant", content: `Something went wrong: ${err.message}`, agent: "system", sources: [] },
        ],
      }, conversation.id);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  function handleChip(chip) { handleSend(chip); }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100vh", background: "#0d0d0d", minWidth: 0 }}>

      {/* Top bar */}
      <div style={{ padding: "13px 20px", borderBottom: "1px solid #1a1a1a", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>CloudDash AI Support</span>
          {agent && (
            <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 10, background: agentBg(agent), color: agentFg(agent) }}>{agent}</span>
          )}
          {sending && <span style={{ fontSize: 11, color: "#555" }}>Routing your request…</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#555", fontSize: 18, cursor: "pointer", letterSpacing: 2 }} title="Options">···</span>
          <button onClick={onToggleContext} title="Toggle context panel"
            style={{ background: "none", border: "1px solid #2a2a2a", borderRadius: 6, padding: "3px 8px", color: contextOpen ? "#6366f1" : "#555", cursor: "pointer", fontSize: 12 }}>
            ⊞
          </button>
        </div>
      </div>

      {/* Messages area */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 14 }}>

        {!hasMessages && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18, paddingBottom: 80 }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "#1a1a2e", border: "1px solid #2d2d5e", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>✦</div>
            <div style={{ textAlign: "center" }}>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: "#e2e8f0", margin: "0 0 10px" }}>How can I help you today?</h2>
              <p style={{ fontSize: 13, color: "#555", maxWidth: 380, lineHeight: 1.6, margin: 0 }}>
                I'm your CloudDash AI assistant. Describe your issue and I'll route you to the right specialist for billing, technical support, or account management.
              </p>
            </div>
          </div>
        )}

        {hasMessages && conversation.messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {sending && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="dot-1 typing-dot" />
            <span className="dot-2 typing-dot" />
            <span className="dot-3 typing-dot" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Quick chips */}
      {!hasMessages && (
        <div style={{ display: "flex", gap: 8, padding: "0 32px 14px", flexWrap: "wrap" }}>
          {CHIPS.map(chip => (
            <button key={chip} onClick={() => handleChip(chip)} disabled={sending}
              style={{ background: "#161616", border: "1px solid #2a2a2a", borderRadius: 20, padding: "7px 14px", color: "#aaa", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#6366f1", fontSize: 13 }}>✦</span>{chip}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div style={{ padding: "0 20px 16px", flexShrink: 0 }}>
        <div style={{ background: "#161616", border: "1px solid #242424", borderRadius: 14, padding: "10px 12px", display: "flex", alignItems: "flex-end", gap: 10 }}>
          <button style={{ background: "none", border: "none", color: "#444", cursor: "pointer", padding: "4px", flexShrink: 0 }} title="Attach file">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>

          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            placeholder="Type your message…"
            rows={1}
            style={{ flex: 1, background: "none", border: "none", outline: "none", color: "#e2e8f0", fontSize: 14, resize: "none", fontFamily: "inherit", lineHeight: 1.5, maxHeight: 120, overflowY: "auto" }}
          />

          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <button style={{ background: "none", border: "none", color: "#444", cursor: "pointer", padding: "4px" }} title="Voice input">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </button>
            <button onClick={() => handleSend()} disabled={sending}
              style={{ width: 36, height: 36, borderRadius: "50%", background: sending ? "#3d3d8a" : "#6366f1", border: "none", cursor: sending ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "background .15s" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
        </div>
        <p style={{ textAlign: "center", fontSize: 11, color: "#333", margin: "8px 0 0" }}>
          CloudDash AI may produce inaccurate information. Verify critical details.
        </p>
      </div>

    </div>
  );
}
