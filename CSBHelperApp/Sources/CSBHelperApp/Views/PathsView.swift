import SwiftUI
import CSBHelperCore

struct PathsView: View {
    @EnvironmentObject var dataService: DataService
    @State private var selectedPath: Path?
    @State private var sortOrder: PathSortOrder = .name
    
    enum PathSortOrder: String, CaseIterable {
        case name = "Name"
        case datePublished = "Date Published"
        case courseCount = "Course Count"
        
        var systemImage: String {
            switch self {
            case .name: return "textformat"
            case .datePublished: return "calendar"
            case .courseCount: return "number"
            }
        }
    }
    
    private var sortedPaths: [Path] {
        dataService.paths.allEntities.sorted { first, second in
            switch sortOrder {
            case .name:
                return first.name < second.name
            case .datePublished:
                return (first.datePublished ?? "") > (second.datePublished ?? "")
            case .courseCount:
                return first.courses.count > second.courses.count
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
                        ForEach(PathSortOrder.allCases, id: \.self) { order in
                            Label(order.rawValue, systemImage: order.systemImage)
                                .tag(order)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Spacer()
                }
                .padding(.horizontal)
                
                Divider()
                
                // Path list
                List(sortedPaths, selection: $selectedPath) { path in
                    PathRowView(path: path)
                        .tag(path)
                }
                .listStyle(.sidebar)
            }
            .navigationTitle("Paths (\(sortedPaths.count))")
        } detail: {
            if let path = selectedPath {
                PathDetailView(path: path)
            } else {
                ContentUnavailableView(
                    "Select a Path",
                    systemImage: "map.fill",
                    description: Text("Choose a learning path from the sidebar to view its details")
                )
            }
        }
    }
}

struct PathRowView: View {
    let path: Path
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(path.name)
                .font(.headline)
                .lineLimit(2)
            
            HStack {
                Label("\(path.courses.count)", systemImage: "book.fill")
                    .font(.caption)
                    .foregroundColor(.blue)
                
                if let published = path.datePublished {
                    Text("• \(published)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Text(path.description)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(3)
        }
        .padding(.vertical, 2)
    }
}

struct PathDetailView: View {
    let path: Path
    @EnvironmentObject var dataService: DataService
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 12) {
                    Text(path.name)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    HStack {
                        Label("\(path.courses.count) courses", systemImage: "book.fill")
                            .font(.subheadline)
                            .foregroundColor(.blue)
                        
                        if let published = path.datePublished {
                            Text("• Published: \(published)")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        
                        if let language = path.inLanguage {
                            Text("• \(language.uppercased())")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    if path.availableLanguage.count > 1 {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Available Languages:")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 4) {
                                ForEach(path.availableLanguage, id: \.self) { lang in
                                    Text(lang.uppercased())
                                        .font(.caption2)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(Color.gray.opacity(0.2))
                                        .cornerRadius(4)
                                }
                            }
                        }
                    }
                }
                
                Divider()
                
                // Description
                VStack(alignment: .leading, spacing: 8) {
                    Text("Description")
                        .font(.headline)
                    Text(path.description)
                        .font(.body)
                }
                
                // Courses in Path
                if !path.courses.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Courses in this Path")
                            .font(.headline)
                        
                        ForEach(Array(path.courses.enumerated()), id: \.element.id) { index, pathCourse in
                            PathCourseRowView(
                                pathCourse: pathCourse,
                                index: index + 1,
                                course: dataService.courses.entity(withId: pathCourse.id)
                            )
                        }
                    }
                }
                
                // Actions
                HStack(spacing: 12) {
                    Button("Open in Browser") {
                        NSWorkspace.shared.open(path.url)
                    }
                    .buttonStyle(.borderedProminent)
                    
                    Button("Copy URL") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(path.url.absoluteString, forType: .string)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
        .navigationTitle(path.name)
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct PathCourseRowView: View {
    let pathCourse: PathCourse
    let index: Int
    let course: Course?
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Step number
            Text("\(index)")
                .font(.caption)
                .fontWeight(.bold)
                .foregroundColor(.white)
                .frame(width: 24, height: 24)
                .background(Circle().fill(Color.blue))
            
            VStack(alignment: .leading, spacing: 4) {
                Text(pathCourse.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(pathCourse.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                
                HStack {
                    if let course = course {
                        if let level = course.educationalLevel {
                            Text(level)
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(levelColor(level).opacity(0.2))
                                .foregroundColor(levelColor(level))
                                .cornerRadius(4)
                        }
                        
                        if let rating = course.aggregateRating {
                            HStack(spacing: 2) {
                                Image(systemName: "star.fill")
                                    .foregroundColor(.yellow)
                                    .font(.caption2)
                                Text(rating.ratingValue)
                                    .font(.caption2)
                                    .fontWeight(.medium)
                            }
                        }
                    }
                    
                    Spacer()
                    
                    Button("Open") {
                        NSWorkspace.shared.open(pathCourse.url)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.mini)
                }
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func levelColor(_ level: String) -> Color {
        switch level.lowercased() {
        case "beginner":
            return .green
        case "intermediate":
            return .orange
        case "advanced":
            return .red
        default:
            return .blue
        }
    }
}
