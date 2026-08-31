/* 生成工具：pg-ui-structure-html V1.6 | 生成时间：2026-08-28 */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function showToast(message) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 2200);
}

const menuButton = $("#menuButton");
if (menuButton) menuButton.addEventListener("click", () => $("#sidebar")?.classList.toggle("open"));

$$('.mode').forEach((button) => button.addEventListener('click', () => {
  $$('.mode').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  showToast(`已切换为${button.textContent.trim()}（原型演示）`);
}));

function applyScope(scope) {
  $$('.scope-tab').forEach((item) => item.classList.toggle('active', item.dataset.scope === scope));
  const rows = $$('.memory-row');
  rows.forEach((row) => { row.hidden = scope !== 'all' && row.dataset.memoryScope !== scope; });
  const visible = rows.filter((row) => !row.hidden).length;
  const count = $('#resultCount');
  if (count) count.textContent = `${visible} 条结果（原型示例）`;
}

$$('[data-scope]').forEach((button) => button.addEventListener('click', () => applyScope(button.dataset.scope)));

const searchButton = $('#searchButton');
if (searchButton) searchButton.addEventListener('click', () => {
  const value = $('#searchInput')?.value.trim();
  showToast(value ? `已搜索“${value}”（原型演示）` : '请输入搜索内容');
});

const drawer = $('#detailDrawer');
const overlay = $('#drawerOverlay');
function openDrawer() {
  if (!drawer || !overlay) return;
  overlay.hidden = false;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
}
function closeDrawer() {
  if (!drawer || !overlay) return;
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  window.setTimeout(() => { overlay.hidden = true; }, 180);
}
$$('.row-menu').forEach((button) => button.addEventListener('click', openDrawer));
$('#closeDrawer')?.addEventListener('click', closeDrawer);
$('#cancelEdit')?.addEventListener('click', closeDrawer);
overlay?.addEventListener('click', closeDrawer);
$('#saveEdit')?.addEventListener('click', () => { closeDrawer(); showToast('修改已保存（原型演示）'); });

const modal = $('#deleteModal');
$('#deleteButton')?.addEventListener('click', () => { if (modal) modal.hidden = false; });
$('#cancelDelete')?.addEventListener('click', () => { if (modal) modal.hidden = true; });
$('#confirmDelete')?.addEventListener('click', () => {
  if (modal) modal.hidden = true;
  closeDrawer();
  showToast('记忆已删除（原型演示）');
});

$$('input[name="scope"]').forEach((radio) => radio.addEventListener('change', () => {
  $$('.choice-card').forEach((card) => card.classList.toggle('selected', card.contains(radio)));
  const pathField = $('#projectPathField');
  if (pathField) pathField.hidden = radio.value !== 'project';
}));

const contentField = $('#contentField');
contentField?.addEventListener('input', () => { const count = $('#charCount'); if (count) count.textContent = `${contentField.value.length} / 10000`; });
$('#memoryForm')?.addEventListener('submit', (event) => {
  event.preventDefault();
  showToast('记忆已保存（原型演示）');
  window.setTimeout(() => { window.location.href = 'index.html'; }, 900);
});
