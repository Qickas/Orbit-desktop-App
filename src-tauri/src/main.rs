use tauri::Manager;

mod core_client;
use core_client::{
    core_conversation, core_status, core_voice_state, CoreClient,
};

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            core_status,
            core_conversation,
            core_voice_state,
        ])
        .setup(|app| {
            let core_client = CoreClient::new()
                .map_err(|error| format!("Could not create local Core client: {error}"))?;
            app.manage(core_client);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building ORBIT desktop")
        .run(|_, _| {});
}
