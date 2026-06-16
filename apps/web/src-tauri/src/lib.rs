// Tauri 2 entry. The desktop shell just hosts the existing web build (../dist) in a
// system WebView; all app logic stays in the web app. Mobile (tauri android/ios) reuses
// this same run().
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running AEC BIM Platform");
}
