const BASE = "/api/v1";
const TIMEOUT_MS = 30000;

function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  return fetch(url, { ...options, signal: controller.signal })
    .then((res) => { clearTimeout(timer); return res; })
    .catch((err) => {
      clearTimeout(timer);
      if (err.name === "AbortError") throw Object.assign(new Error("Request timed out — please try again."), { status: 408 });
      throw err;
    });
}

export async function startConversation(customerId, initialMessage) {
  const res = await fetchWithTimeout(`${BASE}/conversation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      customer_id: customerId || undefined,
      initial_message: initialMessage || undefined,
    }),
  });
  if (!res.ok) throw new Error("Failed to start conversation");
  return res.json();
}

export async function sendMessage(conversationId, message) {
  const res = await fetchWithTimeout(`${BASE}/conversation/${conversationId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const err = new Error(res.status === 404 ? "Session not found" : "Failed to send message");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function getHistory(conversationId) {
  const res = await fetchWithTimeout(`${BASE}/conversation/${conversationId}/history`);
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}
