import SwiftUI
import CSBHelperCore

@main
struct CSBHelperApp: App {
    @StateObject private var dataService = DataService()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(dataService)
                .task {
                    await dataService.loadAllData()
                }
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        
        Settings {
            SettingsView()
                .environmentObject(dataService)
        }
    }
}
