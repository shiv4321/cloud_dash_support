import { useState, useEffect } from "react";
import Sidebar      from "./components/Sidebar";
import ChatPanel    from "./components/ChatPanel";
import ContextPanel from "./components/ContextPanel";
import { startConversation } from "./api";

const STORAGE_KEY = "clouddash_conversations";
const ACTIVE_KEY  = "clouddash_active_id";

function loadFromStorage() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

export default function App() {
  const [conversations, setConversations] = useState(() => loadFromStorage());
  const [activeId, setActiveId]           = useState(null); // always start fresh on reload
  const [loading, setLoading]             = useState(false);
  const [contextOpen, setContextOpen]     = useState(true);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations)); } catch {}
  }, [conversations]);

  async function handleNewConversation(prebuilt) {
    if (prebuilt) {
      setConversations(prev => [prebuilt, ...prev]);
      setActiveId(prebuilt.id);
      return prebuilt;
    }
    setLoading(true);
    try {
      const data = await startConversation();
      const conv = {
        id:       data.conversation_id,
        traceId:  data.trace_id,
        label:    `Session ${conversations.length + 1}`,
        preview:  "",
        messages: [],
        agent:    "Triage Agent",
        entities: {},
      };
      setConversations(prev => [conv, ...prev]);
      setActiveId(conv.id);
      return conv;
    } finally {
      setLoading(false);
    }
  }

  function updateConversation(id, patch) {
    setConversations(prev =>
      prev.map(c => {
        if (c.id !== id) return c;
        const updated = { ...c, ...patch };
        if (patch.messages?.length) {
          const last = patch.messages[patch.messages.length - 1];
          if (last?.content) updated.preview = last.content.replace(/[#*`]/g, "").slice(0, 60);
        }
        return updated;
      })
    );
  }

  function handleReset(oldId, newId, newTraceId) {
    setConversations(prev =>
      prev.map(c => c.id === oldId ? { ...c, id: newId, traceId: newTraceId } : c)
    );
    setActiveId(newId);
  }

  function handleClearAll() {
    setConversations([]);
    setActiveId(null);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(ACTIVE_KEY);
  }

  const active = conversations.find(c => c.id === activeId) || null;

  return (
    <div style={{ display: "flex", height: "100vh", width: "100%", background: "#0d0d0d" }}>
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={handleNewConversation}
        onClearAll={handleClearAll}
        loading={loading}
      />
      <ChatPanel
        conversation={active}
        onUpdate={(patch, convId) => updateConversation(convId ?? active?.id, patch)}
        onReset={(newId, newTraceId) => active && handleReset(active.id, newId, newTraceId)}
        onNew={handleNewConversation}
        onToggleContext={() => setContextOpen(o => !o)}
        contextOpen={contextOpen}
      />
      {contextOpen && (
        <ContextPanel
          conversation={active}
          onClose={() => setContextOpen(false)}
        />
      )}
    </div>
  );
}
