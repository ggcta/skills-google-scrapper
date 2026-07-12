// Prevent an extra console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Google Skills Scraper — a thin Tauri desktop shell over the validated
//! `skills-scraper` Go binary. Every operation shells out to it; the GUI never
//! reimplements scraping logic, so it inherits the CLI's verified behaviour.

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};

/// A list/search row, matching `skills-scraper --json` output. The fetch-status
/// fields must be declared here or they'd be silently dropped on the round-trip
/// through this struct (serde ignores unknown fields on the way in and only
/// re-emits declared ones on the way out), leaving the GUI badges blank.
#[derive(Serialize, serde::Deserialize)]
struct Item {
    id: String,
    name: String,
    #[serde(rename = "type")]
    kind: String,
    portal: String,
    #[serde(default)]
    fetched: bool,
    #[serde(default, rename = "scrapedTime")]
    scraped_time: i64,
    #[serde(default, rename = "scrapedDate")]
    scraped_date: String,
}

/// Holds the running `skills-scraper browser` child — the persistent, reusable
/// browser (backlog #13). It stays open across fetch/sync tasks (which connect to
/// it) until close_browser or the window-close teardown ends it. Deliberately NOT
/// behind BrowserGuard: fetches are meant to run WHILE it is open and reuse it.
struct BrowserSession(Mutex<Option<Child>>);

/// Single-flight guard: only ONE browser-driving op (sync / fetch / login
/// session) may run at a time, because they all share the one persistent Chrome
/// profile (.webdriver_profiles) and a second concurrent Chrome collides on its
/// SingletonLock. Try-acquire semantics → a second attempt is rejected, not
/// queued (KISS). An owned Arc clone can be moved into a background thread so the
/// guard is released when the work truly finishes (e.g. a login session spans
/// two commands, so no held MutexGuard could bridge it).
#[derive(Clone)]
struct BrowserGuard(Arc<AtomicBool>);

impl BrowserGuard {
    /// Returns true if the guard was free and is now held by the caller.
    fn try_acquire(&self) -> bool {
        self.0
            .compare_exchange(false, true, Ordering::Acquire, Ordering::Relaxed)
            .is_ok()
    }
    fn release(&self) {
        self.0.store(false, Ordering::Release);
    }
}

const BUSY_MSG: &str = "A browser task is already running — wait for it to finish.";

/// Tracks the PID of the running browser-driving subprocess (a `fetch` or a
/// `sync`, if any) so `stop_fetch` and the window-close teardown can signal it.
/// Cleared as soon as the subprocess is reaped. Single-flight (BrowserGuard)
/// guarantees at most one at a time.
#[derive(Clone)]
struct FetchState(Arc<Mutex<Option<u32>>>);

/// Holds the running fetch's stdin so `continue_fetch` can send a newline when
/// the binary asks for sign-in (@@AUTH_REQUIRED), letting the user log in in the
/// visible browser and resume the same session. Cleared when the fetch ends.
#[derive(Clone)]
struct FetchStdin(Arc<Mutex<Option<std::process::ChildStdin>>>);

/// Candidate directories to search for the repo root / skills-scraper binary: an explicit
/// CSB_PROJECT_ROOT, then every ancestor of the working dir, then every ancestor
/// of the app executable (so it works no matter where the app is launched from).
fn candidate_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Ok(p) = std::env::var("CSB_PROJECT_ROOT") {
        roots.push(PathBuf::from(p));
    }
    if let Ok(cwd) = std::env::current_dir() {
        roots.extend(cwd.ancestors().map(|a| a.to_path_buf()));
    }
    if let Ok(exe) = std::env::current_exe() {
        roots.extend(exe.ancestors().map(|a| a.to_path_buf()));
    }
    roots
}

/// Resolve the `skills-scraper` binary. Prefers CSB_BIN, else the first candidate
/// root that contains a known binary name. Returns an actionable error if none is
/// found. Legacy names (csb.bin / csb) are still accepted so old local builds keep
/// working after the rebrand.
fn resolve_csb() -> Result<PathBuf, String> {
    if let Ok(b) = std::env::var("CSB_BIN") {
        let p = PathBuf::from(&b);
        if p.exists() {
            return Ok(p);
        }
        return Err(format!("CSB_BIN points to a missing file: {b}"));
    }
    // Prefer the extensioned build artifact (skills-scraper.bin / .exe on
    // Windows); legacy csb.bin / csb names are still honoured for old builds.
    let names: &[&str] = if cfg!(windows) {
        &["skills-scraper.exe", "skills-scraper.bin", "csb.exe", "csb.bin", "csb"]
    } else {
        &["skills-scraper.bin", "skills-scraper", "csb.bin", "csb"]
    };
    for r in candidate_roots() {
        for name in names {
            let c = r.join(name);
            if c.exists() {
                return Ok(c);
            }
        }
    }
    Err("skills-scraper binary not found. Build it from the repo root:\n  \
         cd go && go build -o ../skills-scraper.bin .\n\
         (or run `just cli`, or set CSB_BIN to its full path)."
        .to_string())
}

/// The repository root (where data/ and csbmdvault/ live), used as the working
/// directory for csb. Prefers a checkout containing both `.git` and `go`, else
/// the directory holding the resolved skills-scraper binary.
fn repo_root() -> PathBuf {
    for r in candidate_roots() {
        if r.join(".git").exists() && r.join("go").exists() {
            return r;
        }
    }
    if let Ok(csb) = resolve_csb() {
        if let Some(parent) = csb.parent() {
            return parent.to_path_buf();
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn portal_flag(portal: &str) -> &'static str {
    if portal == "partner" {
        "-B"
    } else {
        "-A"
    }
}

fn kind_flag(kind: &str, long: bool) -> &'static str {
    match (kind, long) {
        ("courses", true) | ("course", true) => "--courses",
        ("labs", true) | ("lab", true) => "--labs",
        ("paths", true) | ("path", true) => "--paths",
        ("courses", false) | ("course", false) => "-c",
        ("labs", false) | ("lab", false) => "-l",
        _ => "-p",
    }
}

/// Run `csb` to completion and return stdout (used for the --json commands).
fn run_csb(args: &[String]) -> Result<String, String> {
    let bin = resolve_csb()?;
    let out = Command::new(&bin)
        .args(args)
        .current_dir(repo_root())
        .output()
        .map_err(|e| format!("failed to launch skills-scraper ({}): {e}", bin.display()))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).into_owned());
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

/// Like run_csb but records the child PID into `pid` while it runs, so a
/// browser-driving call (Sync) can be SIGTERM'd by the window-close teardown
/// instead of orphaning Chrome. The PID is cleared as soon as the child is reaped.
fn run_csb_tracked(args: &[String], pid: &Arc<Mutex<Option<u32>>>) -> Result<String, String> {
    let bin = resolve_csb()?;
    let child = Command::new(&bin)
        .args(args)
        .current_dir(repo_root())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch skills-scraper ({}): {e}", bin.display()))?;
    *pid.lock().unwrap() = Some(child.id());
    let out = child.wait_with_output();
    *pid.lock().unwrap() = None; // cleared right after reaping, before PID reuse
    let out = out.map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).into_owned());
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

// list_items reads the local database only (no browser), so it needs no guard —
// it's async purely to keep the blocking subprocess call off the UI thread.
#[tauri::command]
async fn list_items(portal: String, kind: String) -> Result<Vec<Item>, String> {
    let args = vec![
        "list".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, true).into(),
        "--json".into(),
    ];
    let out = tauri::async_runtime::spawn_blocking(move || run_csb(&args))
        .await
        .map_err(|e| format!("list task failed: {e}"))??;
    serde_json::from_str(&out).map_err(|e| e.to_string())
}

/// Refresh the catalog (paths/courses/labs) from the website, then return the
/// stored list. Runs `skills-scraper list --reload --headless --json`, which opens a
/// headless browser and pages through the site's catalog API. This is the only
/// way to populate an empty first-run database, so the GUI exposes it as a
/// distinct "Sync" action (slower than the local-only Refresh).
#[tauri::command]
async fn sync_items(
    guard: State<'_, BrowserGuard>,
    fetch_state: State<'_, FetchState>,
    portal: String,
    kind: String,
) -> Result<Vec<Item>, String> {
    // Browser op: hold the single-flight guard for the whole reload, and track
    // the child PID so a window close mid-sync tears Chrome down (backlog #1).
    let guard = guard.inner().clone();
    let fetch_state = fetch_state.inner().clone();
    if !guard.try_acquire() {
        return Err(BUSY_MSG.into());
    }
    let args = vec![
        "list".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, true).into(),
        "--reload".into(),
        "--headless".into(),
        "--json".into(),
    ];
    let joined =
        tauri::async_runtime::spawn_blocking(move || run_csb_tracked(&args, &fetch_state.0)).await;
    guard.release(); // release on every path, before propagating any error
    let out = joined.map_err(|e| format!("sync task failed: {e}"))??;
    serde_json::from_str(&out).map_err(|e| e.to_string())
}

// search_items reads the local database only (no browser), so no guard.
#[tauri::command]
async fn search_items(portal: String, query: String, kind: String) -> Result<Vec<Item>, String> {
    let mut args = vec!["search".into(), query, portal_flag(&portal).into()];
    if kind != "all" {
        // search uses the singular flags (--course/--path/--lab)
        let flag = match kind.as_str() {
            "courses" | "course" => "--course",
            "labs" | "lab" => "--lab",
            _ => "--path",
        };
        args.push(flag.into());
    }
    args.push("--json".into());
    let out = tauri::async_runtime::spawn_blocking(move || run_csb(&args))
        .await
        .map_err(|e| format!("search task failed: {e}"))??;
    serde_json::from_str(&out).map_err(|e| e.to_string())
}

/// Stream a `skills-scraper fetch` run, emitting each output line as a `fetch-log`
/// event, `@@ITEM` markers as `fetch-item`, and a final `fetch-done` (bool
/// success). The subprocess is spawned in-command (so a launch failure rejects
/// the invoke promise), then drained/waited on a background thread — the command
/// returns immediately so the UI never blocks. The browser guard is released when
/// the subprocess actually finishes, not at return.
#[tauri::command]
async fn fetch(
    app: AppHandle,
    guard: State<'_, BrowserGuard>,
    fetch_state: State<'_, FetchState>,
    fetch_stdin: State<'_, FetchStdin>,
    portal: String,
    kind: String,
    ids: Vec<String>,
    force: bool,
    signin: bool,
    toc: bool,
    no_transcript: bool,
    headless: bool,
) -> Result<(), String> {
    let guard = guard.inner().clone();
    let fetch_state = fetch_state.inner().clone();
    let fetch_stdin = fetch_stdin.inner().clone();
    if !guard.try_acquire() {
        return Err(BUSY_MSG.into());
    }

    let mut args: Vec<String> = vec![
        "fetch".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, false).into(),
    ];
    args.extend(ids.into_iter().filter(|s| !s.trim().is_empty()));
    if force {
        args.push("--force".into());
    }
    // #11: open the sign-in page and wait (the fetch-auth-required event drives
    // the modal; Continue answers it via continue_fetch).
    if signin {
        args.push("--signin".into());
    }
    if toc {
        args.push("--toc".into());
    }
    // #12: transcripts are always fetched into the JSON; this only omits them from
    // the generated Markdown.
    if no_transcript {
        args.push("--md-no-transcript".into());
    }
    if headless {
        args.push("--headless".into());
    }
    // Ask the binary for machine-readable "@@ITEM {json}" markers so we can
    // refresh the Browse badges live as each item is saved.
    args.push("--emit-progress".into());

    // Spawn in-command so a launch failure rejects the promise (and frees the
    // guard); release on every early-error path.
    let bin = match resolve_csb() {
        Ok(b) => b,
        Err(e) => {
            guard.release();
            return Err(e);
        }
    };
    let mut child = match Command::new(&bin)
        .args(&args)
        .current_dir(repo_root())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            guard.release();
            return Err(format!(
                "failed to launch skills-scraper ({}): {e}",
                bin.display()
            ));
        }
    };

    // Record the PID so stop_fetch can signal it (Ctrl+C style), and the stdin so
    // continue_fetch can answer an @@AUTH_REQUIRED sign-in prompt.
    *fetch_state.0.lock().unwrap() = Some(child.id());
    *fetch_stdin.0.lock().unwrap() = child.stdin.take();

    // Forward stderr lines on their own thread (progress is printed there).
    if let Some(err) = child.stderr.take() {
        let app2 = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(err).lines().map_while(Result::ok) {
                let _ = app2.emit("fetch-log", line);
            }
        });
    }

    // Drain stdout, wait, signal done, and release the guard — all off the UI
    // thread. The command returns immediately below (fire-and-forget past spawn).
    std::thread::spawn(move || {
        if let Some(out) = child.stdout.take() {
            for line in BufReader::new(out).lines().map_while(Result::ok) {
                // Structured markers: @@ITEM → fetch-item (live badge), and
                // @@AUTH_REQUIRED → fetch-auth-required (prompt the user to sign
                // in in the visible browser, then continue_fetch). Everything else
                // is a normal console log line.
                if let Some(json) = line.strip_prefix("@@ITEM ") {
                    let _ = app.emit("fetch-item", json.to_string());
                } else if let Some(url) = line.strip_prefix("@@AUTH_REQUIRED ") {
                    let _ = app.emit("fetch-auth-required", url.to_string());
                } else {
                    let _ = app.emit("fetch-log", line);
                }
            }
        }
        let ok = child.wait().map(|s| s.success()).unwrap_or(false);
        // Clear the PID + stdin right after reaping, before anything can reuse them.
        *fetch_state.0.lock().unwrap() = None;
        *fetch_stdin.0.lock().unwrap() = None;
        let _ = app.emit("fetch-done", ok);
        guard.release(); // released when the browser op truly finishes
    });

    Ok(())
}

/// Send SIGTERM to a subprocess so the Go binary handles it gracefully (Ctrl+C
/// style: it closes Chrome and keeps already-saved items). No-op on non-unix.
fn sigterm(pid: u32) {
    #[cfg(unix)]
    unsafe {
        libc::kill(pid as libc::pid_t, libc::SIGTERM);
    }
    #[cfg(not(unix))]
    {
        let _ = pid;
    }
}

/// Stop the running fetch the way Ctrl+C does on the CLI. Completion still
/// arrives via `fetch-done`. No-op with a message if nothing is running.
#[tauri::command]
fn stop_fetch(fetch_state: State<FetchState>) -> Result<(), String> {
    match *fetch_state.0.lock().unwrap() {
        Some(pid) => {
            sigterm(pid);
            Ok(())
        }
        None => Err("No fetch is running.".into()),
    }
}

/// Answer a fetch's @@AUTH_REQUIRED prompt: write a newline to its stdin (the
/// user has signed in in the visible browser), so the binary reloads and resumes
/// the same session.
#[tauri::command]
fn continue_fetch(fetch_stdin: State<FetchStdin>) -> Result<(), String> {
    match fetch_stdin.0.lock().unwrap().as_mut() {
        Some(stdin) => stdin.write_all(b"\n").map_err(|e| e.to_string()),
        None => Err("No fetch is waiting for sign-in.".into()),
    }
}

/// Open the persistent, reusable browser (backlog #13): spawn `skills-scraper
/// browser`, which opens a visible Chrome, advertises a reuse endpoint, and stays
/// open. The user signs in / browses freely; later fetches connect to this same
/// Chrome. It does NOT take BrowserGuard — fetches are meant to run alongside it.
/// Rejects a second open while one is already running.
#[tauri::command]
fn open_browser(state: State<BrowserSession>, portal: String) -> Result<(), String> {
    let mut slot = state.0.lock().unwrap();
    if slot.is_some() {
        return Err("A browser is already open.".into());
    }
    let bin = resolve_csb()?;
    let child = Command::new(&bin)
        .args(["browser", portal_flag(&portal)])
        .current_dir(repo_root())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch skills-scraper ({}): {e}", bin.display()))?;
    *slot = Some(child);
    Ok(())
}

/// Close the persistent browser: send a newline to its stdin so it clears the
/// reuse endpoint and shuts Chrome down gracefully, then wait — off the UI thread.
#[tauri::command]
async fn close_browser(state: State<'_, BrowserSession>) -> Result<(), String> {
    // Take the child out under the lock, then drop the MutexGuard before awaiting.
    let child_opt = state.0.lock().unwrap().take();
    if let Some(mut child) = child_opt {
        let _ = tauri::async_runtime::spawn_blocking(move || {
            if let Some(mut stdin) = child.stdin.take() {
                let _ = stdin.write_all(b"\n");
            }
            let _ = child.wait();
        })
        .await;
    }
    Ok(())
}

/// Report the reusable browser's state: "none", "alive" (a fetch will reuse it),
/// or "stale" (advertised but unresponsive — the GUI asks the user to close it).
/// Off the UI thread since it does a quick network probe via the binary.
#[tauri::command]
async fn browser_status() -> Result<String, String> {
    let out = tauri::async_runtime::spawn_blocking(|| run_csb(&["browser-status".into()]))
        .await
        .map_err(|e| format!("browser-status task failed: {e}"))??;
    Ok(out.trim().to_string())
}

/// Open a file or folder with the OS default handler.
fn os_open(path: &str) -> Result<(), String> {
    let opener = if cfg!(target_os = "macos") {
        "open"
    } else if cfg!(target_os = "windows") {
        "explorer"
    } else {
        "xdg-open"
    };
    Command::new(opener)
        .arg(path)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

/// Reveal the Markdown vault in the OS file manager.
#[tauri::command]
fn open_vault() -> Result<(), String> {
    let vault = repo_root().join("csbmdvault");
    os_open(&vault.to_string_lossy())
}

/// Open a stored item's Markdown file in the OS default app. Resolves the path
/// via `skills-scraper mdpath`, so the GUI never reimplements the vault layout or
/// filename sanitization. Returns the binary's error (e.g. "not fetched yet…")
/// on failure, for the frontend to surface.
// open_md resolves a local path (mdpath) then opens it — no browser, no guard;
// async only to keep the blocking mdpath call off the UI thread.
#[tauri::command]
async fn open_md(portal: String, kind: String, id: String) -> Result<(), String> {
    let args = vec![
        "mdpath".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, false).into(),
        id,
    ];
    let path = tauri::async_runtime::spawn_blocking(move || run_csb(&args))
        .await
        .map_err(|e| format!("mdpath task failed: {e}"))??
        .trim()
        .to_string();
    if path.is_empty() {
        return Err("Markdown path not found.".into());
    }
    os_open(&path)
}

fn main() {
    tauri::Builder::default()
        .manage(BrowserSession(Mutex::new(None)))
        .manage(BrowserGuard(Arc::new(AtomicBool::new(false))))
        .manage(FetchState(Arc::new(Mutex::new(None))))
        .manage(FetchStdin(Arc::new(Mutex::new(None))))
        // Closing the window must not orphan a browser. SIGTERM any running
        // fetch and any open login subprocess so the Go binary shuts Chrome down
        // cleanly and releases the profile lock (otherwise the next run launches
        // on a locked profile and loads without the signed-in session).
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(pid) = *window.state::<FetchState>().0.lock().unwrap() {
                    sigterm(pid);
                }
                if let Some(child) = window.state::<BrowserSession>().0.lock().unwrap().as_ref() {
                    sigterm(child.id());
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            list_items,
            sync_items,
            search_items,
            fetch,
            stop_fetch,
            continue_fetch,
            open_browser,
            close_browser,
            browser_status,
            open_vault,
            open_md
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn browser_guard_is_single_flight() {
        let g = BrowserGuard(Arc::new(AtomicBool::new(false)));
        assert!(g.try_acquire(), "first acquire should succeed");
        assert!(!g.try_acquire(), "second acquire must fail while held");
        g.release();
        assert!(g.try_acquire(), "acquire should succeed again after release");
        // A clone shares the same flag, so it also sees "held".
        assert!(!g.clone().try_acquire(), "clone must observe the held flag");
        g.release();
    }
}
