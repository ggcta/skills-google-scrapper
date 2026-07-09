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
  if (portal === "all") {
    logLine("Note: portal is 'All' — bare IDs fetch as Public; full URLs use their own portal.");
  }
  try {
    await invoke("fetch", {
      portal: concretePortal(),
      kind: selected("#fetchKind", "kind"),
      ids,
      force: toggleOn("force"),
      toc: toggleOn("toc"),
      noTranscript: toggleOn("noTranscript"),
      headless: toggleOn("headless"),
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
  const btn = $("#browseSyncBtn");
  btn.disabled = true;
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
    btn.disabled = false;
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

// --- Login flow ---
$("#loginBtn").addEventListener("click", async () => {
  // Launch the browser first; only reveal the "click Done" modal once skills-scraper has
  // actually started, so a launch failure surfaces as a readable status message
  // instead of a modal that flashes open and shut.
  const lp = concretePortal();
  setStatus("Opening sign-in browser…", "busy");
  $("#loginBtn").disabled = true;
  try {
    await invoke("login", { portal: lp });
    $("#loginPortal").textContent = lp;
    $("#loginModal").hidden = false;
    setStatus(`Browser open for ${lp}. Sign in, then click Done.`, "busy");
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
