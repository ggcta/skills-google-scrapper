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

/// Resolve the repository root (where data/ and csbmdvault/ live). Prefers
/// CSB_PROJECT_ROOT, else walks up for a checkout that has both `.git` and `go`.
fn project_root() -> PathBuf {
    if let Ok(p) = std::env::var("CSB_PROJECT_ROOT") {
        return PathBuf::from(p);
    }
    let start = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut dir = start.clone();
    loop {
        if dir.join(".git").exists() && dir.join("go").exists() {
            return dir;
        }
        match dir.parent() {
            Some(p) => dir = p.to_path_buf(),
            None => break,
        }
    }
    start
}

/// Resolve the `csb` binary path. Prefers CSB_BIN, else <root>/csb, else PATH.
fn csb_bin() -> String {
    if let Ok(b) = std::env::var("CSB_BIN") {
        return b;
    }
    let local = project_root().join("csb");
    if local.exists() {
        return local.to_string_lossy().into_owned();
    }
    "csb".to_string()
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
    let out = Command::new(csb_bin())
        .args(args)
        .current_dir(project_root())
        .output()
        .map_err(|e| format!("failed to launch csb: {e}"))?;
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

    let mut child = Command::new(csb_bin())
        .args(&args)
        .current_dir(project_root())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch csb: {e}"))?;

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
    let child = Command::new(csb_bin())
        .args(["login", portal_flag(&portal)])
        .current_dir(project_root())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to launch csb: {e}"))?;
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
    let vault = project_root().join("csbmdvault");
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
