import SwiftUI
import CSBHelperCore

struct LabsView: View {
    @EnvironmentObject var dataService: DataService
    @State private var selectedLab: Lab?
    @State private var sortOrder: LabSortOrder = .name
    
    enum LabSortOrder: String, CaseIterable {
        case name = "Name"
        case datePublished = "Date Published"
        case stepCount = "Step Count"
        
        var systemImage: String {
            switch self {
            case .name: return "textformat"
            case .datePublished: return "calendar"
            case .stepCount: return "list.number"
            }
        }
    }
    
    private var sortedLabs: [Lab] {
        dataService.labs.allEntities.sorted { first, second in
            switch sortOrder {
            case .name:
                return first.name < second.name
            case .datePublished:
                return (first.datePublished ?? "") > (second.datePublished ?? "")
            case .stepCount:
                return first.steps.count > second.steps.count
            }
        }
    }
    
    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 16) {
                // Sort control
                HStack {
                    Text("Sort by:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Picker("Sort", selection: $sortOrder) {
                        ForEach(LabSortOrder.allCases, id: \.self) { order in
                            Label(order.rawValue, systemImage: order.systemImage)
                                .tag(order)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Spacer()
                }
                .padding(.horizontal)
                
                Divider()
                
                // Lab list
                List(sortedLabs, selection: $selectedLab) { lab in
                    LabRowView(lab: lab)
                        .tag(lab)
                }
                .listStyle(.sidebar)
            }
            .navigationTitle("Labs (\(sortedLabs.count))")
        } detail: {
            if let lab = selectedLab {
                LabDetailView(lab: lab)
            } else {
                ContentUnavailableView(
                    "Select a Lab",
                    systemImage: "flask.fill",
                    description: Text("Choose a lab from the sidebar to view its details")
                )
            }
        }
    }
}

struct LabRowView: View {
    let lab: Lab
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lab.name)
                .font(.headline)
                .lineLimit(2)
            
            HStack {
                Label("\(lab.steps.count) steps", systemImage: "list.number")
                    .font(.caption)
                    .foregroundColor(.orange)
                
                if let published = lab.datePublished {
                    Text("• \(published)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if let language = lab.inLanguage {
                    Text("• \(language.uppercased())")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Text(lab.description)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(3)
        }
        .padding(.vertical, 2)
    }
}

struct LabDetailView: View {
    let lab: Lab
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 12) {
                    Text(lab.name)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    HStack {
                        Label("\(lab.steps.count) steps", systemImage: "list.number")
                            .font(.subheadline)
                            .foregroundColor(.orange)
                        
                        if let published = lab.datePublished {
                            Text("• Published: \(published)")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        
                        if let language = lab.inLanguage {
                            Text("• \(language.uppercased())")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Divider()
                
                // Description
                VStack(alignment: .leading, spacing: 8) {
                    Text("Description")
                        .font(.headline)
                    Text(lab.description)
                        .font(.body)
                }
                
                // Lab Steps
                if !lab.steps.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Lab Steps")
                            .font(.headline)
                        
                        ForEach(lab.orderedSteps, id: \.key) { step in
                            LabStepView(stepNumber: step.key, stepTitle: step.value)
                        }
                    }
                }
                
                // Actions
                HStack(spacing: 12) {
                    Button("Open in Browser") {
                        NSWorkspace.shared.open(lab.url)
                    }
                    .buttonStyle(.borderedProminent)
                    
                    Button("Copy URL") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(lab.url.absoluteString, forType: .string)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
        .navigationTitle(lab.name)
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct LabStepView: View {
    let stepNumber: String
    let stepTitle: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Step number circle
            Text(stepNumber)
                .font(.caption)
                .fontWeight(.bold)
                .foregroundColor(.white)
                .frame(width: 28, height: 28)
                .background(Circle().fill(stepColor))
            
            VStack(alignment: .leading, spacing: 4) {
                Text(stepTitle)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if isSpecialStep {
                    Text(stepCategory)
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(stepColor.opacity(0.2))
                        .foregroundColor(stepColor)
                        .cornerRadius(4)
                }
            }
            
            Spacer()
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private var stepColor: Color {
        if stepTitle.lowercased().contains("overview") {
            return .blue
        } else if stepTitle.lowercased().contains("objective") {
            return .green
        } else if stepTitle.lowercased().contains("task") {
            return .orange
        } else if stepTitle.lowercased().contains("congratulation") {
            return .purple
        } else if stepTitle.lowercased().contains("end") {
            return .red
        } else {
            return .gray
        }
    }
    
    private var isSpecialStep: Bool {
        let title = stepTitle.lowercased()
        return title.contains("overview") || 
               title.contains("objective") || 
               title.contains("congratulation") || 
               title.contains("end")
    }
    
    private var stepCategory: String {
        let title = stepTitle.lowercased()
        if title.contains("overview") {
            return "Overview"
        } else if title.contains("objective") {
            return "Objectives"
        } else if title.contains("congratulation") {
            return "Completion"
        } else if title.contains("end") {
            return "Cleanup"
        } else {
            return "Task"
        }
    }
}
