<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import {
  checkHealth,
  createMemory,
  deleteMemory,
  listMemories,
  searchMemories,
  updateMemory,
} from "./api";

const backendHealthy = ref(false);
const busy = ref(false);
const errorMessage = ref("");
const memories = ref([]);
const total = ref(0);
const editingId = ref(null);
const editContent = ref("");
const editTags = ref("");

const filters = reactive({
  userId: "demo-user",
  conversationId: "",
  tags: "",
  startDate: "",
  endDate: "",
  query: "",
});

const draft = reactive({
  content: "",
  conversationId: "",
  tags: "",
});

const parsedFilterTags = computed(() => parseTags(filters.tags));

function parseTags(value) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function toIso(value, endOfDay = false) {
  if (!value) return null;
  const suffix = endOfDay ? "T23:59:59" : "T00:00:00";
  return new Date(`${value}${suffix}`).toISOString();
}

function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function run(action) {
  busy.value = true;
  errorMessage.value = "";
  try {
    await action();
  } catch (error) {
    errorMessage.value = error.message || "操作失败";
  } finally {
    busy.value = false;
  }
}

async function loadList() {
  if (!filters.userId.trim()) {
    errorMessage.value = "请先填写用户 ID";
    return;
  }
  await run(async () => {
    const result = await listMemories({
      userId: filters.userId.trim(),
      conversationId: filters.conversationId.trim(),
      tags: parsedFilterTags.value,
      startTime: toIso(filters.startDate),
      endTime: toIso(filters.endDate, true),
      limit: 100,
    });
    memories.value = result.items;
    total.value = result.total;
  });
}

async function semanticSearch() {
  if (!filters.query.trim()) {
    await loadList();
    return;
  }
  await run(async () => {
    const result = await searchMemories({
      user_id: filters.userId.trim(),
      query: filters.query.trim(),
      top_k: 20,
      conversation_id: filters.conversationId.trim() || null,
      tags: parsedFilterTags.value,
      start_time: toIso(filters.startDate),
      end_time: toIso(filters.endDate, true),
    });
    memories.value = result;
    total.value = result.length;
  });
}

async function submitMemory() {
  if (!draft.content.trim()) {
    errorMessage.value = "记忆内容不能为空";
    return;
  }
  await run(async () => {
    await createMemory({
      user_id: filters.userId.trim(),
      conversation_id: draft.conversationId.trim() || null,
      content: draft.content.trim(),
      tags: parseTags(draft.tags),
      metadata: { source: "vue-admin" },
    });
    draft.content = "";
    draft.conversationId = "";
    draft.tags = "";
    await loadList();
  });
}

function beginEdit(memory) {
  editingId.value = memory.id;
  editContent.value = memory.content;
  editTags.value = memory.tags.join(", ");
}

function cancelEdit() {
  editingId.value = null;
  editContent.value = "";
  editTags.value = "";
}

async function saveEdit(memory) {
  await run(async () => {
    await updateMemory(memory.id, filters.userId.trim(), {
      content: editContent.value.trim(),
      tags: parseTags(editTags.value),
    });
    cancelEdit();
    await loadList();
  });
}

async function removeMemory(memory) {
  if (!window.confirm("确定删除这条记忆吗？删除后不会出现在检索结果中。")) {
    return;
  }
  await run(async () => {
    await deleteMemory(memory.id, filters.userId.trim());
    await loadList();
  });
}

onMounted(async () => {
  try {
    backendHealthy.value = (await checkHealth()).status === "ok";
  } catch {
    backendHealthy.value = false;
  }
  await loadList();
});
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">MCP LONG-TERM MEMORY</p>
        <h1>记忆控制台</h1>
        <p class="subtitle">查看、写入和检索属于每个用户的长期记忆。</p>
      </div>
      <div class="health" :class="{ online: backendHealthy }">
        <span class="health-dot"></span>
        {{ backendHealthy ? "后端在线" : "后端离线" }}
      </div>
    </header>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

    <section class="control-grid">
      <article class="panel write-panel">
        <div class="section-heading">
          <span>01</span>
          <div>
            <h2>写入记忆</h2>
            <p>内容会同步写入 MySQL，并在 Milvus 中建立语义向量。</p>
          </div>
        </div>
        <label>
          记忆内容
          <textarea
            v-model="draft.content"
            rows="6"
            placeholder="例如：用户喜欢简洁的中文技术说明。"
          ></textarea>
        </label>
        <div class="two-columns">
          <label>
            会话 ID（可选）
            <input v-model="draft.conversationId" placeholder="conversation-001" />
          </label>
          <label>
            标签（逗号分隔）
            <input v-model="draft.tags" placeholder="偏好, 技术" />
          </label>
        </div>
        <button class="primary" :disabled="busy" @click="submitMemory">
          {{ busy ? "处理中…" : "保存记忆" }}
        </button>
      </article>

      <article class="panel filter-panel">
        <div class="section-heading">
          <span>02</span>
          <div>
            <h2>检索与筛选</h2>
            <p>用户 ID 是强制隔离边界，搜索不会跨用户返回结果。</p>
          </div>
        </div>
        <label>
          用户 ID
          <input v-model="filters.userId" placeholder="demo-user" />
        </label>
        <label>
          语义搜索
          <div class="search-row">
            <input v-model="filters.query" placeholder="用户偏好什么？" @keyup.enter="semanticSearch" />
            <button class="dark" :disabled="busy" @click="semanticSearch">搜索</button>
          </div>
        </label>
        <div class="two-columns">
          <label>
            会话 ID
            <input v-model="filters.conversationId" placeholder="全部会话" />
          </label>
          <label>
            标签
            <input v-model="filters.tags" placeholder="偏好, 技术" />
          </label>
          <label>
            开始日期
            <input v-model="filters.startDate" type="date" />
          </label>
          <label>
            结束日期
            <input v-model="filters.endDate" type="date" />
          </label>
        </div>
        <button class="secondary" :disabled="busy" @click="loadList">应用筛选</button>
      </article>
    </section>

    <section class="memory-section">
      <div class="memory-header">
        <div>
          <p class="eyebrow">MEMORY INDEX</p>
          <h2>记忆列表</h2>
        </div>
        <strong>{{ total }} 条</strong>
      </div>

      <div v-if="!memories.length && !busy" class="empty-state">
        <span>∅</span>
        <h3>还没有匹配的记忆</h3>
        <p>在上方写入第一条记忆，或调整用户与筛选条件。</p>
      </div>

      <div class="memory-list">
        <article v-for="memory in memories" :key="memory.id" class="memory-card">
          <template v-if="editingId === memory.id">
            <textarea v-model="editContent" rows="4"></textarea>
            <input v-model="editTags" placeholder="标签（逗号分隔）" />
            <div class="card-actions">
              <button class="primary small" @click="saveEdit(memory)">保存</button>
              <button class="ghost small" @click="cancelEdit">取消</button>
            </div>
          </template>
          <template v-else>
            <div class="card-topline">
              <div class="tag-list">
                <span v-for="tag in memory.tags" :key="tag" class="tag">{{ tag }}</span>
                <span v-if="!memory.tags.length" class="tag muted">无标签</span>
              </div>
              <span v-if="memory.score !== null" class="score">
                相似度 {{ Number(memory.score).toFixed(3) }}
              </span>
            </div>
            <p class="memory-content">{{ memory.content }}</p>
            <div class="memory-meta">
              <span>{{ formatDate(memory.updated_at) }}</span>
              <span>{{ memory.conversation_id || "无会话" }}</span>
              <span class="memory-id">{{ memory.id }}</span>
            </div>
            <div class="card-actions">
              <button class="ghost small" @click="beginEdit(memory)">编辑</button>
              <button class="danger small" @click="removeMemory(memory)">删除</button>
            </div>
          </template>
        </article>
      </div>
    </section>
  </main>
</template>

