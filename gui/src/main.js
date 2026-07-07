// CSB Studio frontend. All work is delegated to the `csb` binary via Tauri
// commands (see src-tauri/src/main.rs). Uses the global Tauri API
// (withGlobalTauri = true), so it runs without a bundler.

const invoke = window.__TAURI__?.core?.invoke;
const listen = window.__TAURI__?.event?.listen;

let portal = "public";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function setStatus(msg, cls = "") {
  const bar = $("#statusbar");
  bar.textContent = msg;
  bar.className = "statusbar" + (cls ? " " + cls : "");
}

// A segmented/toggle group: clicking sets .active and returns the value via cb.
function wireGroup(rootSel, attr, onSelect) {
  $$(`${rootSel} button`).forEach((b) => {
    b.addEventListener("click", () => {
      $$(`${rootSel} button`).forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      onSelect(b.dataset[attr]);
    });
  });
}
const selected = (rootSel, attr) => $(`${rootSel} button.active`)?.dataset[attr];

// --- Tabs & portal ---
wireGroup("#tabs", "tab", (tab) => {
  $$(".panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab));
});
wireGroup("#portalToggle", "portal", (p) => {
  portal = p;
  setStatus(`Working portal: ${portal}`);
});
wireGroup("#fetchKind", "kind", () => {});
wireGroup("#browseKind", "kind", () => {});
wireGroup("#searchKind", "kind", () => {});
wireGroup("#searchPortal", "portal", () => {});

// --- Fetch ---
const consoleEl = $("#console");
function logLine(line) {
  consoleEl.textContent += line + "\n";
  consoleEl.scrollTop = consoleEl.scrollHeight;
}
if (listen) {
  listen("fetch-log", (e) => logLine(e.payload));
  listen("fetch-done", (e) => {
    setStatus(e.payload ? "Fetch complete." : "Fetch finished with errors.", e.payload ? "ok" : "");
    $("#fetchBtn").disabled = false;
  });
}
$("#fetchBtn").addEventListener("click", async () => {
  const ids = $("#fetchIds").value.split(/[\s,]+/).filter(Boolean);
  if (!ids.length) { setStatus("Enter at least one ID or URL."); return; }
  consoleEl.textContent = "";
  $("#fetchBtn").disabled = true;
  setStatus("Fetching…", "busy");
  try {
    await invoke("fetch", {
      portal,
      kind: selected("#fetchKind", "kind"),
      ids,
      force: $("#optForce").checked,
      toc: $("#optToc").checked,
      noTranscript: $("#optNoTranscript").checked,
      headless: $("#optHeadless").checked,
    });
  } catch (err) {
    logLine("ERROR: " + err);
    setStatus("Fetch failed.", "");
    $("#fetchBtn").disabled = false;
  }
});

// --- Browse / Search tables ---
function renderRows(tableSel, countSel, items) {
  const tbody = $(`${tableSel} tbody`);
  tbody.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td class="cell-id">${it.id}</td>` +
      `<td>${escapeHtml(it.name)}</td>` +
      `<td class="cell-type">${it.type}</td>` +
      `<td class="cell-portal"><span class="badge badge-${it.portal}">${it.portal}</span></td>`;
    tbody.appendChild(tr);
  }
  $(countSel).textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

$("#browseBtn").addEventListener("click", async () => {
  setStatus("Loading…", "busy");
  try {
    const items = await invoke("list_items", { portal, kind: selected("#browseKind", "kind") });
    renderRows("#browseTable", "#browseCount", items);
    setStatus(`Listed ${items.length} from ${portal}.`, "ok");
  } catch (err) {
    setStatus("List failed: " + err);
  }
});

$("#searchBtn").addEventListener("click", async () => {
  const query = $("#searchQuery").value.trim();
  if (!query) { setStatus("Enter a search query."); return; }
  const kind = selected("#searchKind", "kind");
  // Search scope is chosen here (independent of the global toggle): "all"
  // queries both portals and merges, so results span the whole library.
  const scope = selected("#searchPortal", "portal");
  const portals = scope === "all" ? ["public", "partner"] : [scope];
  setStatus("Searching…", "busy");
  try {
    const batches = await Promise.all(
      portals.map((pk) => invoke("search_items", { portal: pk, query, kind }))
    );
    const items = batches.flat();
    renderRows("#searchTable", "#searchCount", items);
    const where = scope === "all" ? "both portals" : scope;
    setStatus(`${items.length} result(s) for “${query}” in ${where}.`, "ok");
  } catch (err) {
    setStatus("Search failed: " + err);
  }
});
$("#searchQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#searchBtn").click(); });

// --- Login flow ---
$("#loginBtn").addEventListener("click", async () => {
  // Launch the browser first; only reveal the "click Done" modal once csb has
  // actually started, so a launch failure surfaces as a readable status message
  // instead of a modal that flashes open and shut.
  setStatus("Opening sign-in browser…", "busy");
  $("#loginBtn").disabled = true;
  try {
    await invoke("login", { portal });
    $("#loginPortal").textContent = portal;
    $("#loginModal").hidden = false;
    setStatus(`Browser open for ${portal}. Sign in, then click Done.`, "busy");
  } catch (err) {
    setStatus("Login failed: " + err);
  } finally {
    $("#loginBtn").disabled = false;
  }
});
$("#loginDone").addEventListener("click", async () => {
  $("#loginModal").hidden = true;
  try {
    await invoke("finish_login");
    setStatus(`Signed in to ${portal}. Session saved.`, "ok");
  } catch (err) {
    setStatus("Login cleanup failed: " + err);
  }
});

$("#vaultBtn").addEventListener("click", async () => {
  try { await invoke("open_vault"); } catch (err) { setStatus("Could not open vault: " + err); }
});

setStatus("Ready.");
