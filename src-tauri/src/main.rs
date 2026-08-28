use std::{
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
};
use tauri::Manager;

mod core_client;
use core_client::{
    core_computer_click, core_computer_context, core_computer_session, core_computer_status,
    core_computer_type, core_conversation, core_status, core_voice_state, CoreClient,
};

struct CoreProcess(Mutex<Option<Child>>);

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            core_status,
            core_conversation,
            core_voice_state,
            core_computer_status,
            core_computer_context,
            core_computer_session,
            core_computer_click,
            core_computer_type,
        ])
        .setup(|app| {
            let project_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .expect("src-tauri must have a project parent")
                .to_path_buf();
            let child = Command::new("python")
                .current_dir(&project_root)
                .env("PYTHONPATH", project_root.join("src"))
                .args(["-m", "orbit_core", "desktop", "--web-root"])
                .arg(project_root.join("dist"))
                .spawn()
                .map_err(|error| format!("Could not start Orbit Core: {error}"))?;
            let core_client = CoreClient::new()
                .map_err(|error| format!("Could not create local Core client: {error}"))?;
            app.manage(core_client);
            app.manage(CoreProcess(Mutex::new(Some(child))));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building ORBIT desktop")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::ExitRequested { .. }) {
                if let Some(state) = app.try_state::<CoreProcess>() {
                    if let Ok(mut child) = state.0.lock() {
                        if let Some(mut child) = child.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}
