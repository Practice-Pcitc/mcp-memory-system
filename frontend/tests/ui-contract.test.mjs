import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const app = await readFile(new URL("../src/App.vue", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("B 方案提供应用外壳和纤细导航栏", () => {
  assert.match(app, /class="app-shell"/);
  assert.match(app, /class="side-rail"/);
  assert.match(styles, /--paper:/);
  const rail = app.match(/<nav class="rail-nav">([\s\S]*?)<\/nav>/)?.[1] || "";
  const sideRail = app.match(/<aside[^>]*class="side-rail"[\s\S]*?<\/aside>/)?.[0] || "";
  assert.equal((rail.match(/<button/g) || []).length, 2);
  assert.equal((sideRail.match(/<button/g) || []).length, 2);
  assert.match(rail, /<small>记忆<\/small>/);
  assert.match(rail, /<small>写入<\/small>/);
  assert.doesNotMatch(rail, /<small>搜索<\/small>|<small>最近<\/small>/);
  assert.match(rail, /currentView === 'home'.*aria-current="currentView === 'home' \? 'page' : undefined".*aria-label="记忆"/);
  assert.match(rail, /currentView === 'write'.*aria-current="currentView === 'write' \? 'page' : undefined".*aria-label="写入"/);
  assert.equal((rail.match(/aria-current=/g) || []).length, 2);
  assert.equal((rail.match(/aria-hidden="true"/g) || []).length, 2);
  assert.doesNotMatch(sideRail, /<small>设置<\/small>|aria-label="记忆首页"/);
  assert.match(app, /aria-controls="primaryNavigation"/);
  assert.match(app, /:aria-expanded="mobileNavOpen"/);
  assert.match(styles, /\.side-rail \{ transform: translateX\(-100%\); visibility: hidden;/);
});

test("首页明确展示三种搜索方式", () => {
  assert.match(app, /class="search-mode-tabs"/);
  assert.match(app, /label: "语义"/);
  assert.match(app, /label: "关键词"/);
  assert.match(app, /label: "混合"/);
  assert.match(app, /role="tab"/);
  assert.match(app, /:aria-selected=/);
  assert.match(app, /handleSearchModeKeydown/);
});

test("全局与项目范围及高级筛选仍可操作", () => {
  assert.match(app, /class="scope-switch"/);
  assert.match(app, /filters\.projectPath/);
  assert.match(app, /filters\.includeGlobal/);
  assert.match(app, /filters\.conversationId/);
});

test("写入记忆使用独立 SPA 视图", () => {
  assert.match(app, /currentView === ["']write["']/);
  assert.match(app, /class="write-workspace"/);
  assert.match(app, /draft\.projectPath/);
});

test("详情编辑使用右侧抽屉并保留删除确认", () => {
  assert.match(app, /class="detail-drawer"/);
  assert.match(app, /selectedMemory/);
  assert.match(app, /saveEdit/);
  assert.match(app, /removeMemory/);
  assert.match(app, /handleGlobalKeydown/);
  assert.match(app, /detailCloseButton/);
});

test("索引状态来自 API 数据而不是写死", () => {
  assert.match(app, /memory\?\.vector_status/);
  assert.match(app, /vectorStatusLabel\(memory\)/);
  assert.doesNotMatch(app, /<span class="vector-ready">● 向量已就绪<\/span>/);
});

test("刷新与筛选保持当前搜索上下文", () => {
  assert.match(app, /async function loadCurrentResults/);
  assert.match(app, /@click="loadCurrentResults">↻ 刷新/);
  assert.match(app, /@click="loadCurrentResults">应用筛选/);
});
