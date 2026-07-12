// Google Skills Scraper frontend. All work is delegated to the `skills-scraper` binary via Tauri
// commands (see src-tauri/src/main.rs). Uses the global Tauri API
// (withGlobalTauri = true), so it runs without a bundler.

const invoke = window.__TAURI__?.core?.invoke;
const listen = window.__TAURI__?.event?.listen;

let portal = "public";
// Last-loaded rows per tab, kept so a sort change can re-render without re-fetching.
let browseItems = [];
let searchItems = [];
// The last query actually run, so portal/type changes can re-run the search.
let lastSearchQuery = "";

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

// Selector changes take effect immediately — no extra button press. Explicit
// buttons remain only where input/confirmation is needed (Fetch IDs, Search query).
function refreshActiveTab() {
  const active = $(".panel.active")?.dataset.panel;
  if (active === "browse") $("#browseBtn").click();
  else if (active === "search" && lastSearchQuery) $("#searchBtn").click();
}

// --- Tabs & portal ---
wireGroup("#tabs", "tab", (tab) => {
  $$(".panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab));
  // Entering Browse shows the current portal's items right away.
  if (tab === "browse") $("#browseBtn").click();
  else if (tab === "search" && lastSearchQuery) $("#searchBtn").click();
});
wireGroup("#portalToggle", "portal", (p) => {
  portal = p;
  setStatus(portal === "all" ? "Portal: All (public + partner)" : `Portal: ${portal}`);
  // Portal is global: reflect it in the active tab immediately.
  refreshActiveTab();
});
wireGroup("#fetchKind", "kind", () => {});
wireGroup("#browseKind", "kind", () => $("#browseBtn").click());
wireGroup("#searchKind", "kind", () => { if (lastSearchQuery) $("#searchBtn").click(); });
// Fetch option toggles are independent (multi-select), so each just flips its
// own active state on click.
$$("#fetchToggles .toggle").forEach((b) =>
  b.addEventListener("click", () => b.classList.toggle("active"))
);
const toggleOn = (opt) => $(`#fetchToggles [data-opt="${opt}"]`)?.classList.contains("active");

// Changing the sort re-applies immediately (no need to click List/Search again):
// re-sort what's already shown, or run the list if nothing is loaded yet.
wireGroup("#browseSort", "sort", () => {
  if (browseItems.length) renderBrowse();
  else $("#browseBtn").click();
});
wireGroup("#searchSort", "sort", () => {
  if (searchItems.length) renderSearch();
});

// The topbar portal is the single source of truth for every tab.
// "All" means both portals for the read tabs (Browse/Search); the concrete
// actions (Fetch/Login) fall back to public while full URLs still infer.
const portalsFor = () => (portal === "all" ? ["public", "partner"] : [portal]);
const concretePortal = () => (portal === "all" ? "public" : portal);

// Client-side sort so it works across merged "All" results without a re-fetch.
function sortItems(items, by) {
  const arr = items.slice();
  const byName = (a, b) => String(a.name).localeCompare(String(b.name), undefined, { sensitivity: "base" });
  if (by === "id") {
    arr.sort((a, b) => {
      const na = parseInt(a.id, 10), nb = parseInt(b.id, 10);
      if (!isNaN(na) && !isNaN(nb) && na !== nb) return na - nb;
      return String(a.id).localeCompare(String(b.id));
    });
  } else if (by === "status") {
    // Fetched first (newest download first), then unfetched, each by name.
    arr.sort((a, b) => {
      if (!!a.fetched !== !!b.fetched) return a.fetched ? -1 : 1;
      if (a.fetched && (b.scrapedTime || 0) !== (a.scrapedTime || 0)) {
        return (b.scrapedTime || 0) - (a.scrapedTime || 0);
      }
      return byName(a, b);
    });
  } else {
    arr.sort(byName);
  }
  return arr;
}

// --- Fetch ---
const consoleEl = $("#console");
function logLine(line) {
  consoleEl.textContent += line + "\n";
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

// While a browser-driving op runs (fetch / sync / login session), disable the
// controls that would start another. The backend also rejects concurrent browser
// ops (they share one Chrome profile), but this avoids the rejection entirely.
// Local-only actions (browse, search, open) stay usable throughout.
function setBrowserBusy(on) {
  // Note: the Browser button is intentionally NOT disabled — fetches are meant to
  // run while the persistent browser is open and reuse it (backlog #13).
  ["#fetchBtn", "#browseSyncBtn"].forEach((sel) => {
    const b = $(sel);
    if (b) b.disabled = on;
  });
}

// Tracks whether the persistent, reusable browser is open (backlog #13).
let browserOpen = false;
if (listen) {
  listen("fetch-log", (e) => logLine(e.payload));
  // Each item the binary saves arrives as a fetch-item event, so Browse/Search
  // badges flip to "✓ fetched" live while a fetch is running.
  listen("fetch-item", (e) => applyItemSaved(e.payload));
  // The fetch hit a sign-in redirect: prompt the user to sign in in the visible
  // browser window, then resume the same session via continue_fetch.
  listen("fetch-auth-required", () => {
    $("#authModal").hidden = false;
    setStatus("Sign in in the browser window, then click Continue.", "busy");
  });
  listen("fetch-done", (e) => {
    setStatus(e.payload ? "Fetch complete." : "Fetch finished with errors.", e.payload ? "ok" : "");
    setBrowserBusy(false);
    $("#stopBtn").hidden = true;
    $("#authModal").hidden = true;
    // Re-list the visible read tab so newly-fetched items (e.g. labs found by
    // cascading a path) appear with their status and the counts settle.
    const active = $(".panel.active")?.dataset.panel;
    if (active === "browse") $("#browseBtn").click();
    else if (active === "search" && lastSearchQuery) $("#searchBtn").click();
  });
}

// applyItemSaved patches the loaded Browse/Search rows in place from a fetch-item
// payload ({portal, kind, id, name, scrapedTime, scrapedDate}) and re-renders the
// affected table (debounced, so a burst of saves doesn't thrash the DOM).
function applyItemSaved(payload) {
  let it;
  try { it = JSON.parse(payload); } catch { return; }
  const patch = (rows) => {
    let hit = false;
    for (const r of rows) {
      if (String(r.id) === String(it.id) && r.portal === it.portal) {
        r.fetched = true;
        r.scrapedTime = it.scrapedTime;
        r.scrapedDate = it.scrapedDate;
        hit = true;
      }
    }
    return hit;
  };
  if (patch(browseItems)) scheduleRender("browse");
  if (patch(searchItems)) scheduleRender("search");
}

const renderTimers = {};
function scheduleRender(which) {
  if (renderTimers[which]) return;
  renderTimers[which] = setTimeout(() => {
    renderTimers[which] = null;
    if (which === "browse") renderBrowse();
    else renderSearch();
  }, 250);
}
async function runFetch() {
  const ids = $("#fetchIds").value.split(/[\s,]+/).filter(Boolean);
  if (!ids.length) { setStatus("Enter at least one ID or URL."); return; }
  consoleEl.textContent = "";
  setBrowserBusy(true);
  $("#stopBtn").hidden = false;
  $("#stopBtn").disabled = false;
  setStatus("Fetching…", "busy");
  if (portal === "all") {
    logLine("Note: portal is 'All' — bare IDs fetch as Public; full URLs use their own portal.");
  }
  try {
    await invoke("fetch", {
      portal: concretePortal(),
      kind: selected("#fetchKind", "kind"),
      ids,
      force: toggleOn("force"),
      signin: toggleOn("signin"),
      toc: toggleOn("toc"),
      noTranscript: toggleOn("noTranscript"),
      headless: toggleOn("headless"),
    });
  } catch (err) {
    logLine("ERROR: " + err);
    setStatus("Fetch failed.", "");
    setBrowserBusy(false);
    $("#stopBtn").hidden = true;
  }
}
$("#fetchBtn").addEventListener("click", async () => {
  // If a persistent browser is open but stopped responding, a fetch can't reuse
  // it — ask the user to acknowledge closing it before launching a fresh one (#13).
  if (browserOpen) {
    try {
      const status = await invoke("browser_status");
      if (status === "stale") { $("#browserStaleModal").hidden = false; return; }
      if (status === "none") { browserOpen = false; }
    } catch (_) { /* probe failed; just proceed */ }
  }
  runFetch();
});

// Stop mirrors Ctrl+C on the CLI: SIGTERM the fetch subprocess so it stops
// cleanly (already-fetched items are kept). The fetch-done event then hides this
// button and re-enables the controls when the process actually exits.
$("#stopBtn").addEventListener("click", async () => {
  $("#stopBtn").disabled = true;
  setStatus("Stopping…", "busy");
  logLine("Stopping… (finishing safely, like Ctrl+C — completed items are kept)");
  try {
    await invoke("stop_fetch");
  } catch (err) {
    logLine("Stop failed: " + err);
    setStatus("Stop failed: " + err);
    $("#stopBtn").disabled = false;
  }
});

// --- Browse / Search tables ---
function renderRows(tableSel, countSel, items) {
  const tbody = $(`${tableSel} tbody`);
  tbody.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    // Carry what a double-click needs to open (or explain) this row's Markdown.
    tr.dataset.id = it.id;
    tr.dataset.portal = it.portal;
    tr.dataset.kind = String(it.type).toLowerCase(); // path / course / lab
    tr.dataset.name = it.name;
    tr.dataset.fetched = it.fetched ? "1" : "";
    tr.title = it.fetched
      ? "Double-click to open its Markdown"
      : "Not fetched yet — fetch it to open its Markdown";
    if (it.fetched) tr.classList.add("openable");
    tr.innerHTML =
      `<td class="cell-id">${it.id}</td>` +
      `<td>${escapeHtml(it.name)}</td>` +
      `<td class="cell-type">${it.type}</td>` +
      `<td class="cell-portal"><span class="badge badge-${it.portal}">${it.portal}</span></td>` +
      `<td class="cell-status">${statusCell(it)}</td>`;
    tbody.appendChild(tr);
  }
  const fetched = items.filter((it) => it.fetched).length;
  $(countSel).textContent =
    `${items.length} item${items.length === 1 ? "" : "s"} · ${fetched} fetched`;
}

// statusCell renders the fetch status: a green "✓ date" when downloaded, a dim
// dash when not yet fetched.
function statusCell(it) {
  if (it.fetched) {
    const label = it.scrapedDate || "fetched";
    const title = it.scrapedDate ? `Fetched on ${it.scrapedDate}` : "Fetched";
    return `<span class="badge badge-fetched" title="${title}">✓ ${label}</span>`;
  }
  return `<span class="badge badge-unfetched" title="Not fetched yet">— not fetched</span>`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderBrowse() {
  renderRows("#browseTable", "#browseCount", sortItems(browseItems, selected("#browseSort", "sort")));
}
function renderSearch() {
  renderRows("#searchTable", "#searchCount", sortItems(searchItems, selected("#searchSort", "sort")));
}

// Double-click a row to open its Markdown in the OS default app. If the item
// isn't fetched yet, say so instead. Delegated on the tbody so it keeps working
// across re-renders.
async function onRowOpen(tr) {
  if (!tr) return;
  const { id, portal, kind, name } = tr.dataset;
  if (tr.dataset.fetched !== "1") {
    setStatus(`“${name}” isn’t fetched yet — fetch it first to open its Markdown.`);
    return;
  }
  setStatus(`Opening “${name}”…`, "busy");
  try {
    await invoke("open_md", { portal, kind, id });
    setStatus(`Opened “${name}”.`, "ok");
  } catch (err) {
    setStatus("Could not open Markdown: " + err);
  }
}
["#browseTable", "#searchTable"].forEach((sel) => {
  const tbody = $(`${sel} tbody`);
  if (tbody) tbody.addEventListener("dblclick", (e) => onRowOpen(e.target.closest("tr")));
});

$("#browseBtn").addEventListener("click", async () => {
  const kind = selected("#browseKind", "kind");
  setStatus("Loading…", "busy");
  try {
    const batches = await Promise.all(
      portalsFor().map((pk) => invoke("list_items", { portal: pk, kind }))
    );
    browseItems = batches.flat();
    renderBrowse();
    const where = portal === "all" ? "both portals" : portal;
    if (browseItems.length === 0) {
      setStatus(`No ${kind} stored yet — click Sync to fetch the catalog from the website.`, "");
    } else {
      setStatus(`Listed ${browseItems.length} from ${where}.`, "ok");
    }
  } catch (err) {
    setStatus("List failed: " + err);
  }
});

// Sync = pull the catalog from the website (opens a headless browser; slower).
// This is how an empty first-run database gets populated.
$("#browseSyncBtn").addEventListener("click", async () => {
  const kind = selected("#browseKind", "kind");
  setBrowserBusy(true);
  setStatus(`Syncing ${kind} from the website… (this can take a minute)`, "busy");
  try {
    const batches = await Promise.all(
      portalsFor().map((pk) => invoke("sync_items", { portal: pk, kind }))
    );
    browseItems = batches.flat();
    renderBrowse();
    setStatus(`Synced ${browseItems.length} ${kind} from the website.`, "ok");
  } catch (err) {
    setStatus("Sync failed: " + err);
  } finally {
    setBrowserBusy(false);
  }
});

$("#searchBtn").addEventListener("click", async () => {
  const query = $("#searchQuery").value.trim();
  if (!query) { setStatus("Enter a search query."); return; }
  lastSearchQuery = query;
  const kind = selected("#searchKind", "kind");
  // Portal scope comes from the global topbar control; "All" spans both.
  setStatus("Searching…", "busy");
  try {
    const batches = await Promise.all(
      portalsFor().map((pk) => invoke("search_items", { portal: pk, query, kind }))
    );
    searchItems = batches.flat();
    renderSearch();
    const where = portal === "all" ? "both portals" : portal;
    setStatus(`${searchItems.length} result(s) for “${query}” in ${where}.`, "ok");
  } catch (err) {
    setStatus("Search failed: " + err);
  }
});
$("#searchQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#searchBtn").click(); });

// --- Persistent browser flow (backlog #13) ---
// The Browser button opens a browser that stays open; fetches reuse it, so the
// user doesn't get re-challenged for sign-in or need "Sign in first" each time.
$("#browserBtn").addEventListener("click", async () => {
  if (browserOpen) { $("#browserModal").hidden = false; return; }
  const lp = concretePortal();
  setStatus("Opening browser…", "busy");
  try {
    await invoke("open_browser", { portal: lp });
    browserOpen = true;
    $("#browserModal").hidden = false;
    setStatus(`Browser open for ${lp}. Sign in and browse; fetches reuse it.`, "ok");
  } catch (err) {
    setStatus("Could not open browser: " + err);
  }
});
$("#browserDismiss").addEventListener("click", () => { $("#browserModal").hidden = true; });
$("#browserClose").addEventListener("click", async () => {
  $("#browserModal").hidden = true;
  setStatus("Closing browser…", "busy");
  try {
    await invoke("close_browser");
    browserOpen = false;
    setStatus("Browser closed.", "");
  } catch (err) {
    setStatus("Could not close browser: " + err);
  }
});
// Reuse-impossible ack: the open browser stopped responding, so a fetch can't
// reuse it. Confirm before closing it and launching a fresh one.
$("#staleCancel").addEventListener("click", () => {
  $("#browserStaleModal").hidden = true;
  setStatus("Fetch canceled.");
});
$("#staleContinue").addEventListener("click", async () => {
  $("#browserStaleModal").hidden = true;
  try { await invoke("close_browser"); } catch (_) { /* best effort */ }
  browserOpen = false;
  runFetch();
});

// Continue a fetch that paused for sign-in: the user has signed in in the
// browser, so resume the same session.
$("#authContinue").addEventListener("click", async () => {
  $("#authModal").hidden = true;
  setStatus("Resuming fetch…", "busy");
  try {
    await invoke("continue_fetch");
  } catch (err) {
    setStatus("Could not resume: " + err);
  }
});

$("#vaultBtn").addEventListener("click", async () => {
  try { await invoke("open_vault"); } catch (err) { setStatus("Could not open vault: " + err); }
});

setStatus("Ready.");
