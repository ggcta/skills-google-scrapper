import SwiftUI
import CSBHelperCore

struct SettingsView: View {
    @EnvironmentObject var dataService: DataService
    @AppStorage("dataFolderPath") private var dataFolderPath = "data"
    @AppStorage("autoRefreshInterval") private var autoRefreshInterval = 300.0
    @AppStorage("enableAutoRefresh") private var enableAutoRefresh = true
    @State private var showingFolderPicker = false
    @State private var isRefreshing = false
    
    var body: some View {
        Form {
            Section("Data Settings") {
                HStack {
                    Text("Data Folder:")
                    Spacer()
                    Text(dataFolderPath)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    
                    Button("Choose...") {
                        showingFolderPicker = true
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                
                HStack {
                    Button(isRefreshing ? "Refreshing..." : "Refresh Data") {
                        refreshData()
                    }
                    .disabled(isRefreshing)
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("Last updated: Now") // Could be enhanced with actual timestamp
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            Section("Auto Refresh") {
                Toggle("Enable Auto Refresh", isOn: $enableAutoRefresh)
                
                if enableAutoRefresh {
                    HStack {
                        Text("Refresh Interval:")
                        Spacer()
                        Text("\(Int(autoRefreshInterval / 60)) minutes")
                            .foregroundColor(.secondary)
                    }
                    
                    Slider(value: $autoRefreshInterval, in: 60...3600, step: 60) {
                        Text("Interval")
                    } minimumValueLabel: {
                        Text("1m")
                            .font(.caption)
                    } maximumValueLabel: {
                        Text("60m")
                            .font(.caption)
                    }
                }
            }
            
            Section("Statistics") {
                StatisticRow(title: "Courses", value: "\(dataService.courses.count)")
                StatisticRow(title: "Paths", value: "\(dataService.paths.count)")
                StatisticRow(title: "Labs", value: "\(dataService.labs.count)")
                StatisticRow(title: "Topics", value: "\(dataService.topics.allTopics.count)")
            }
            
            Section("About") {
                HStack {
                    Text("Version:")
                    Spacer()
                    Text("1.0.0")
                        .foregroundColor(.secondary)
                }
                
                HStack {
                    Text("Build:")
                    Spacer()
                    Text("Swift Edition")
                        .foregroundColor(.secondary)
                }
                
                Link("GitHub Repository", destination: URL(string: "https://github.com/samdx/cloudskillsboost-helper")!)
                    .foregroundColor(.blue)
            }
            
            Section("Actions") {
                Button("Reset to Defaults") {
                    resetToDefaults()
                }
                .foregroundColor(.red)
                
                Button("Clear Cache") {
                    clearCache()
                }
                .foregroundColor(.orange)
            }
        }
        .formStyle(.grouped)
        .frame(width: 500, height: 600)
        .fileImporter(
            isPresented: $showingFolderPicker,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            handleFolderSelection(result)
        }
    }
    
    private func refreshData() {
        isRefreshing = true
        Task {
            await dataService.loadAllData()
            await MainActor.run {
                isRefreshing = false
            }
        }
    }
    
    private func handleFolderSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            if let url = urls.first {
                dataFolderPath = url.path
                // Reinitialize data service with new path
                // Note: This would require updating DataService to support path changes
                refreshData()
            }
        case .failure(let error):
            print("Error selecting folder: \(error)")
        }
    }
    
    private func resetToDefaults() {
        dataFolderPath = "data"
        autoRefreshInterval = 300.0
        enableAutoRefresh = true
    }
    
    private func clearCache() {
        // Clear any cached data
        // This could be enhanced to actually clear cached files
        refreshData()
    }
}

struct StatisticRow: View {
    let title: String
    let value: String
    
    var body: some View {
        HStack {
            Text(title)
            Spacer()
            Text(value)
                .foregroundColor(.secondary)
                .fontWeight(.medium)
        }
    }
}
