<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { checkHealth, createMemory, deleteMemory, listMemories, searchMemories, updateMemory } from "./api";

const backendHealthy = ref(false);
const busy = ref(false);
const errorMessage = ref("");
const memories = ref([]);
const total = ref(0);
const currentView = ref("home");
const showFilters = ref(false);
const mobileNavOpen = ref(false);
const selectedMemory = ref(null);
const editContent = ref("");
const editTags = ref("");
const editProjectPath = ref("");
const draftScope = ref("global");
const projectPathInput = ref(null);
const searchModeTabs = ref([]);
const detailDrawer = ref(null);
const detailCloseButton = ref(null);
let focusBeforeDrawer = null;

const filters = reactive({
  userId: "demo-user", conversationId: "", tags: "", startDate: "", endDate: "",
  query: "", projectPath: "", includeGlobal: true, searchMode: "semantic",
});
const draft = reactive({ content: "", conversationId: "", tags: "", projectPath: "" });
const searchModes = [
  { value: "semantic", label: "语义", hint: "Milvus" },
  { value: "keyword", label: "关键词", hint: "Elasticsearch" },
  { value: "hybrid", label: "混合", hint: "RRF" },
];
const parsedFilterTags = computed(() => parseTags(filters.tags));
const activeScope = computed(() => (filters.projectPath.trim() ? "project" : "global"));
const hasFilters = computed(() => Boolean(filters.conversationId || filters.tags || filters.startDate || filters.endDate || filters.projectPath));

function parseTags(value) {
  return value.split(",").map((tag) => tag.trim()).filter(Boolean);
}
function toIso(value, endOfDay = false) {
  if (!value) return null;
  return new Date(`${value}${endOfDay ? "T23:59:59" : "T00:00:00"}`).toISOString();
}
function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
function formatScore(value) {
  if (value === null || value === undefined) return null;
  return Number(value).toFixed(Number(value) > 1 ? 2 : 3);
}
function vectorStatus(memory) {
  return memory?.vector_status || "pending";
}
function vectorStatusLabel(memory) {
  return ({ ready: "向量已就绪", pending: "等待向量化", failed: "向量化失败", deleted: "索引已删除" })[vectorStatus(memory)] || `索引状态：${vectorStatus(memory)}`;
}
async function run(action) {
  busy.value = true;
  errorMessage.value = "";
  try { await action(); } catch (error) { errorMessage.value = error.message || "操作失败"; }
  finally { busy.value = false; }
}

async function loadList() {
  if (!filters.userId.trim()) { errorMessage.value = "请先填写用户 ID"; return; }
  await run(async () => {
    const result = await listMemories({
      userId: filters.userId.trim(), conversationId: filters.conversationId.trim(),
      tags: parsedFilterTags.value, startTime: toIso(filters.startDate),
      endTime: toIso(filters.endDate, true), limit: 100,
      projectPath: filters.projectPath.trim(), includeGlobal: filters.includeGlobal,
    });
    memories.value = result.items;
    total.value = result.total;
  });
}
async function runSearch() {
  if (!filters.query.trim()) { await loadList(); return; }
  await run(async () => {
    const result = await searchMemories({
      user_id: filters.userId.trim(), query: filters.query.trim(), top_k: 20,
      conversation_id: filters.conversationId.trim() || null, tags: parsedFilterTags.value,
      start_time: toIso(filters.startDate), end_time: toIso(filters.endDate, true),
      project_path: filters.projectPath.trim() || null, include_global: filters.includeGlobal,
      search_mode: filters.searchMode,
    });
    memories.value = result;
    total.value = result.length;
  });
}
async function loadCurrentResults() {
  if (filters.query.trim()) await runSearch();
  else await loadList();
}
async function selectScope(scope) {
  if (scope === "global") { filters.projectPath = ""; await loadCurrentResults(); return; }
  showFilters.value = true;
  await nextTick();
  projectPathInput.value?.focus();
}
function clearFilters() {
  Object.assign(filters, { conversationId: "", tags: "", startDate: "", endDate: "", projectPath: "", includeGlobal: true });
  loadCurrentResults();
}
async function selectSearchMode(index) {
  const normalizedIndex = (index + searchModes.length) % searchModes.length;
  filters.searchMode = searchModes[normalizedIndex].value;
  await nextTick();
  searchModeTabs.value[normalizedIndex]?.focus();
}
function handleSearchModeKeydown(index, event) {
  if (event.key === "ArrowRight") selectSearchMode(index + 1);
  else if (event.key === "ArrowLeft") selectSearchMode(index - 1);
  else if (event.key === "Home") selectSearchMode(0);
  else if (event.key === "End") selectSearchMode(searchModes.length - 1);
  else return;
  event.preventDefault();
}
function openWriteView() { currentView.value = "write"; mobileNavOpen.value = false; errorMessage.value = ""; }
function openHome() { currentView.value = "home"; mobileNavOpen.value = false; errorMessage.value = ""; }

async function submitMemory() {
  if (!draft.content.trim()) { errorMessage.value = "记忆内容不能为空"; return; }
  if (draftScope.value === "project" && !draft.projectPath.trim()) { errorMessage.value = "项目记忆需要填写项目绝对路径"; return; }
  await run(async () => {
    await createMemory({
      user_id: filters.userId.trim(), conversation_id: draft.conversationId.trim() || null,
      content: draft.content.trim(), tags: parseTags(draft.tags), metadata: { source: "vue-admin" },
      project_path: draftScope.value === "project" ? draft.projectPath.trim() : null,
    });
    Object.assign(draft, { content: "", conversationId: "", tags: "", projectPath: "" });
    draftScope.value = "global";
    currentView.value = "home";
    await loadCurrentResults();
  });
}
function openDetail(memory) {
  focusBeforeDrawer = document.activeElement;
  selectedMemory.value = memory;
  editContent.value = memory.content;
  editTags.value = memory.tags.join(", ");
  editProjectPath.value = memory.project_path || "";
  nextTick(() => detailCloseButton.value?.focus());
}
function closeDetail() {
  selectedMemory.value = null; editContent.value = ""; editTags.value = ""; editProjectPath.value = "";
  nextTick(() => focusBeforeDrawer?.focus?.());
}
function handleGlobalKeydown(event) {
  if (!selectedMemory.value) return;
  if (event.key === "Escape") { event.preventDefault(); closeDetail(); return; }
  if (event.key !== "Tab") return;
  if (!detailDrawer.value) return;
  const focusable = [...detailDrawer.value.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')];
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
async function saveEdit() {
  if (!selectedMemory.value) return;
  if (!editContent.value.trim()) { errorMessage.value = "记忆内容不能为空"; return; }
  await run(async () => {
    await updateMemory(selectedMemory.value.id, filters.userId.trim(), {
      content: editContent.value.trim(), tags: parseTags(editTags.value), project_path: editProjectPath.value.trim() || null,
    });
    closeDetail();
    await loadCurrentResults();
  });
}
async function removeMemory(memory = selectedMemory.value) {
  if (!memory || !window.confirm("确定删除这条记忆吗？删除后不会出现在检索结果中。")) return;
  await run(async () => { await deleteMemory(memory.id, filters.userId.trim()); closeDetail(); await loadCurrentResults(); });
}

onMounted(async () => {
  document.addEventListener("keydown", handleGlobalKeydown);
  try { backendHealthy.value = (await checkHealth()).status === "ok"; } catch { backendHealthy.value = false; }
  await loadList();
});
onBeforeUnmount(() => document.removeEventListener("keydown", handleGlobalKeydown));
</script>

<template>
  <div class="app-shell">
    <button v-if="mobileNavOpen" class="nav-backdrop" aria-label="关闭导航" @click="mobileNavOpen = false"></button>
    <aside id="primaryNavigation" class="side-rail" :class="{ open: mobileNavOpen }" :inert="Boolean(selectedMemory)" aria-label="主导航">
      <div class="brand-button" aria-hidden="true"><span class="brain-mark">◌</span></div>
      <nav class="rail-nav">
        <button :class="{ active: currentView === 'home' }" :aria-current="currentView === 'home' ? 'page' : undefined" aria-label="记忆" title="记忆列表" @click="openHome"><span aria-hidden="true">◇</span><small>记忆</small></button>
        <button :class="{ active: currentView === 'write' }" :aria-current="currentView === 'write' ? 'page' : undefined" aria-label="写入" title="写入记忆" @click="openWriteView"><span aria-hidden="true">＋</span><small>写入</small></button>
      </nav>
      <div class="rail-footer">
        <span class="service-indicator" :class="{ online: backendHealthy }" :title="backendHealthy ? '后端在线' : '后端离线'"></span>
      </div>
    </aside>

    <main class="main-workspace" :inert="Boolean(selectedMemory)">
      <button class="mobile-menu" aria-label="打开导航" aria-controls="primaryNavigation" :aria-expanded="mobileNavOpen" @click="mobileNavOpen = true">☰</button>
      <p v-if="errorMessage" class="error-banner" role="alert"><span>!</span>{{ errorMessage }}<button aria-label="关闭错误提示" @click="errorMessage = ''">×</button></p>

      <template v-if="currentView === 'home'">
        <header class="page-header">
          <div><p class="eyebrow">MCP LONG-TERM MEMORY</p><h1>长期记忆</h1><p>沉淀你的知识，赋能未来的每一次思考。</p></div>
          <label class="user-picker"><span class="user-avatar">DU</span><span><small>当前用户</small><input v-model="filters.userId" aria-label="用户 ID" @change="loadList" /></span></label>
        </header>

        <section class="search-workspace" aria-labelledby="searchTitle">
          <h2 id="searchTitle" class="sr-only">搜索记忆</h2>
          <div class="hero-search">
            <span class="search-symbol">⌕</span>
            <input v-model="filters.query" aria-label="搜索你的记忆" placeholder="搜索你的记忆" @keyup.enter="runSearch" />
            <button :disabled="busy" aria-label="执行搜索" @click="runSearch"><span v-if="!busy">→</span><span v-else class="spinner"></span></button>
          </div>
          <div class="search-mode-tabs" role="tablist" aria-label="搜索方式">
            <button v-for="(mode, index) in searchModes" :key="mode.value" ref="searchModeTabs" role="tab" :aria-selected="filters.searchMode === mode.value" :tabindex="filters.searchMode === mode.value ? 0 : -1" :class="{ active: filters.searchMode === mode.value }" :title="mode.hint" @click="filters.searchMode = mode.value" @keydown="handleSearchModeKeydown(index, $event)">{{ mode.label }}</button>
          </div>
          <div class="filter-toolbar">
            <div class="scope-switch" aria-label="记忆范围">
              <button :class="{ active: activeScope === 'global' }" @click="selectScope('global')"><span>◎</span>全局记忆</button>
              <button :class="{ active: activeScope === 'project' }" @click="selectScope('project')"><span>▢</span>项目记忆</button>
            </div>
            <button class="filter-trigger" :class="{ active: showFilters || hasFilters }" @click="showFilters = !showFilters"><span>☷</span>筛选<i v-if="hasFilters" class="filter-dot"></i></button>
          </div>
          <div v-if="showFilters" class="advanced-filters">
            <label>项目路径<input ref="projectPathInput" v-model="filters.projectPath" placeholder="留空只看全局，例如 D:\work\memory-system" /></label>
            <label>标签<input v-model="filters.tags" placeholder="MCP, 测试" /></label>
            <label>会话 ID<input v-model="filters.conversationId" placeholder="全部会话" /></label>
            <label>开始日期<input v-model="filters.startDate" type="date" /></label>
            <label>结束日期<input v-model="filters.endDate" type="date" /></label>
            <label class="include-global"><input v-model="filters.includeGlobal" type="checkbox" />项目检索时包含全局记忆</label>
            <div class="filter-actions"><button class="text-button" @click="clearFilters">清除</button><button class="sage-button" :disabled="busy" @click="loadCurrentResults">应用筛选</button></div>
          </div>
        </section>

        <section class="memory-index" aria-labelledby="memoryTitle">
          <div class="index-header"><div><p class="eyebrow">MEMORY INDEX</p><h2 id="memoryTitle">找到 {{ total }} 条记忆</h2></div><button class="refresh-button" :disabled="busy" @click="loadCurrentResults">↻ 刷新</button></div>
          <div v-if="!memories.length && !busy" class="empty-state"><span>◇</span><h3>还没有匹配的记忆</h3><p>调整搜索条件，或者写入第一条长期记忆。</p><button class="orange-button" @click="openWriteView">新建记忆</button></div>
          <div v-else class="memory-grid">
            <article v-for="memory in memories" :key="memory.id" class="memory-card">
              <button class="card-open" :aria-label="`查看记忆：${memory.content}`" @click="openDetail(memory)">
                <div class="card-heading"><span class="memory-icon" :class="memory.project_path ? 'project' : 'global'">{{ memory.project_path ? "◇" : "◎" }}</span><span class="scope-badge">{{ memory.project_path ? "项目记忆" : "全局记忆" }}</span><span v-if="memory.score !== null" class="score">相关度 {{ formatScore(memory.score) }}</span></div>
                <p class="memory-content">{{ memory.content }}</p>
                <div class="tag-list"><span v-for="tag in memory.tags" :key="tag" class="tag">{{ tag }}</span><span v-if="!memory.tags.length" class="tag muted">无标签</span></div>
                <div class="memory-meta"><span>{{ memory.project_path || memory.conversation_id || "无会话" }}</span><span>{{ formatDate(memory.updated_at) }}</span><span class="vector-state" :class="`status-${vectorStatus(memory)}`">● {{ vectorStatusLabel(memory) }}</span></div>
              </button>
            </article>
          </div>
        </section>
        <button class="floating-write" @click="openWriteView"><span>✎</span>新建记忆</button>
      </template>

      <section v-else-if="currentView === 'write'" class="write-workspace">
        <header class="page-header write-header"><div><p class="eyebrow">NEW MEMORY</p><h1>写入记忆</h1><p>将重要的信息和经验沉淀为长期记忆，便于后续检索与复用。</p></div><button class="close-page" @click="openHome">×</button></header>
        <form class="memory-form" @submit.prevent="submitMemory">
          <label class="content-field"><span><b>*</b> 记忆内容</span><textarea v-model="draft.content" rows="7" maxlength="10000" placeholder="请输入记忆内容，尽量清晰、具体和结构化，便于后续检索与复用…"></textarea><small>{{ draft.content.length }} / 10000</small></label>
          <fieldset class="scope-fieldset"><legend><b>*</b> 记忆范围</legend><div class="scope-cards">
            <label :class="{ selected: draftScope === 'global' }"><input v-model="draftScope" type="radio" value="global" /><span><strong>全局记忆</strong><small>适用于跨项目通用的知识、经验或规则</small></span></label>
            <label :class="{ selected: draftScope === 'project' }"><input v-model="draftScope" type="radio" value="project" /><span><strong>项目记忆</strong><small>仅在指定项目路径内检索和使用</small></span></label>
          </div></fieldset>
          <label v-if="draftScope === 'project'">项目路径<input v-model="draft.projectPath" placeholder="D:\work\memory-system" /><small>请输入项目绝对路径，用于隔离项目记忆。</small></label>
          <div class="form-grid"><label><span><b>*</b> 用户 ID</span><input v-model="filters.userId" required /></label><label>会话 ID（可选）<input v-model="draft.conversationId" placeholder="conversation-001" /></label><label>标签<input v-model="draft.tags" placeholder="输入标签，使用逗号分隔" /></label></div>
          <p class="storage-note"><span>ⓘ</span>内容存储在 MySQL，并由 Milvus 和 Elasticsearch 建立向量与关键词索引。</p>
          <div class="form-actions"><button type="button" class="outline-button" @click="openHome">取消</button><button type="submit" class="orange-button" :disabled="busy">{{ busy ? "保存中…" : "保存记忆" }}</button></div>
        </form>
      </section>
    </main>

    <div v-if="selectedMemory" class="drawer-overlay" @click.self="closeDetail">
      <aside ref="detailDrawer" class="detail-drawer" aria-modal="true" aria-labelledby="detailTitle" role="dialog">
        <header><div><p class="eyebrow">MEMORY DETAIL</p><h2 id="detailTitle">记忆详情</h2></div><button ref="detailCloseButton" aria-label="关闭详情" @click="closeDetail">×</button></header>
        <div class="drawer-body">
          <span class="drawer-scope">{{ selectedMemory.project_path ? "◇ 项目记忆" : "◎ 全局记忆" }}</span>
          <label>内容<textarea v-model="editContent" rows="7"></textarea></label>
          <label>项目路径<input v-model="editProjectPath" placeholder="留空为全局记忆" /></label>
          <label>标签<input v-model="editTags" placeholder="MCP, 测试" /></label>
          <dl class="metadata-list"><div><dt>向量状态</dt><dd class="vector-state" :class="`status-${vectorStatus(selectedMemory)}`">● {{ vectorStatusLabel(selectedMemory) }}</dd></div><div><dt>用户 ID</dt><dd>{{ selectedMemory.user_id }}</dd></div><div><dt>会话 ID</dt><dd>{{ selectedMemory.conversation_id || "无会话" }}</dd></div><div><dt>更新时间</dt><dd>{{ formatDate(selectedMemory.updated_at) }}</dd></div><div><dt>记忆 ID</dt><dd class="memory-id">{{ selectedMemory.id }}</dd></div></dl>
        </div>
        <footer><button class="delete-button" :disabled="busy" @click="removeMemory()">删除</button><div><button class="outline-button" @click="closeDetail">取消</button><button class="orange-button" :disabled="busy" @click="saveEdit">保存修改</button></div></footer>
      </aside>
    </div>
  </div>
</template>
