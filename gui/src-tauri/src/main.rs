// Prevent an extra console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! CSB Studio — a thin Tauri desktop shell over the validated `csb` Go binary.
//! Every operation shells out to `csb`; the GUI never reimplements scraping
//! logic, so it inherits the CLI's byte-for-byte-verified behaviour.

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Emitter, State};

/// A list/search row, matching `csb --json` output.
#[derive(Serialize, serde::Deserialize)]
struct Item {
    id: String,
    name: String,
    #[serde(rename = "type")]
    kind: String,
    portal: String,
}

/// Holds the running `csb login` child so finish_login can complete it.
struct LoginState(Mutex<Option<Child>>);

/// Candidate directories to search for the repo root / csb binary: an explicit
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

/// Resolve the `csb` binary. Prefers CSB_BIN, else the first candidate root that
/// contains a `csb` file. Returns an actionable error if none is found.
fn resolve_csb() -> Result<PathBuf, String> {
    if let Ok(b) = std::env::var("CSB_BIN") {
        let p = PathBuf::from(&b);
        if p.exists() {
            return Ok(p);
        }
        return Err(format!("CSB_BIN points to a missing file: {b}"));
    }
    // Prefer the extensioned build artifact (csb.bin / csb.exe on Windows),
    // falling back to a legacy extensionless `csb`.
    let names: &[&str] = if cfg!(windows) {
        &["csb.exe", "csb.bin", "csb"]
    } else {
        &["csb.bin", "csb"]
    };
    for r in candidate_roots() {
        for name in names {
            let c = r.join(name);
            if c.exists() {
                return Ok(c);
            }
        }
    }
    Err("csb binary not found. Build it from the repo root:\n  \
         cd go && go build -o ../csb.bin .\n\
         (or run `just cli`, or set CSB_BIN to its full path)."
        .to_string())
}

/// The repository root (where data/ and csbmdvault/ live), used as the working
/// directory for csb. Prefers a checkout containing both `.git` and `go`, else
/// the directory holding the resolved csb binary.
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
        .map_err(|e| format!("failed to launch csb ({}): {e}", bin.display()))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).into_owned());
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

#[tauri::command]
fn list_items(portal: String, kind: String) -> Result<Vec<Item>, String> {
    let args = vec![
        "list".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, true).into(),
        "--json".into(),
    ];
    let out = run_csb(&args)?;
    serde_json::from_str(&out).map_err(|e| e.to_string())
}

#[tauri::command]
fn search_items(portal: String, query: String, kind: String) -> Result<Vec<Item>, String> {
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
    let out = run_csb(&args)?;
    serde_json::from_str(&out).map_err(|e| e.to_string())
}

/// Stream a `csb fetch` run, emitting each output line as a `fetch-log` event
/// and a final `fetch-done` (bool success). Runs on a Tauri worker thread.
#[tauri::command]
fn fetch(
    app: AppHandle,
    portal: String,
    kind: String,
    ids: Vec<String>,
    force: bool,
    toc: bool,
    no_transcript: bool,
    headless: bool,
) -> Result<(), String> {
    let mut args: Vec<String> = vec![
        "fetch".into(),
        portal_flag(&portal).into(),
        kind_flag(&kind, false).into(),
    ];
    args.extend(ids.into_iter().filter(|s| !s.trim().is_empty()));
    if force {
        args.push("--force".into());
    }
    if toc {
        args.push("--toc".into());
    }
    if no_transcript {
        args.push("--no-transcript".into());
    }
    if headless {
        args.push("--headless".into());
    }

    let bin = resolve_csb()?;
    let mut child = Command::new(&bin)
        .args(&args)
        .current_dir(repo_root())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch csb ({}): {e}", bin.display()))?;

    // Forward stderr lines too (progress is printed there for some commands).
    if let Some(err) = child.stderr.take() {
        let app2 = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(err).lines().map_while(Result::ok) {
                let _ = app2.emit("fetch-log", line);
            }
        });
    }
    if let Some(out) = child.stdout.take() {
        for line in BufReader::new(out).lines().map_while(Result::ok) {
            let _ = app.emit("fetch-log", line);
        }
    }
    let ok = child.wait().map(|s| s.success()).unwrap_or(false);
    let _ = app.emit("fetch-done", ok);
    Ok(())
}

/// Open a visible browser to sign in; the child is held until finish_login.
#[tauri::command]
fn login(state: State<LoginState>, portal: String) -> Result<(), String> {
    let bin = resolve_csb()?;
    let child = Command::new(&bin)
        .args(["login", portal_flag(&portal)])
        .current_dir(repo_root())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch csb ({}): {e}", bin.display()))?;
    *state.0.lock().unwrap() = Some(child);
    Ok(())
}

/// Signal the pending login that the user is done (writes newline to stdin).
#[tauri::command]
fn finish_login(state: State<LoginState>) -> Result<(), String> {
    if let Some(mut child) = state.0.lock().unwrap().take() {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(b"\n");
        }
        let _ = child.wait();
    }
    Ok(())
}

/// Reveal the Markdown vault in the OS file manager.
#[tauri::command]
fn open_vault() -> Result<(), String> {
    let vault = repo_root().join("csbmdvault");
    let opener = if cfg!(target_os = "macos") {
        "open"
    } else if cfg!(target_os = "windows") {
        "explorer"
    } else {
        "xdg-open"
    };
    Command::new(opener)
        .arg(vault)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(LoginState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            list_items,
            search_items,
            fetch,
            login,
            finish_login,
            open_vault
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
