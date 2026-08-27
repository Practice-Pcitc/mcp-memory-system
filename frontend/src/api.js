const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败（${response.status}）`);
  }
  return response.json();
}

export function checkHealth() {
  return request("/health");
}

export function listMemories(filters) {
  const params = new URLSearchParams();
  params.set("user_id", filters.userId);
  params.set("offset", String(filters.offset || 0));
  params.set("limit", String(filters.limit || 100));
  if (filters.conversationId) {
    params.set("conversation_id", filters.conversationId);
  }
  for (const tag of filters.tags || []) {
    params.append("tags", tag);
  }
  if (filters.startTime) params.set("start_time", filters.startTime);
  if (filters.endTime) params.set("end_time", filters.endTime);
  return request(`/memories?${params.toString()}`);
}

export function searchMemories(payload) {
  return request("/memories/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createMemory(payload) {
  return request("/memories", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMemory(memoryId, userId, payload) {
  return request(`/memories/${memoryId}?user_id=${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteMemory(memoryId, userId) {
  return request(`/memories/${memoryId}?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}

