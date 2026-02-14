import SwiftUI
import CSBHelperCore

struct CoursesView: View {
    @EnvironmentObject var dataService: DataService
    @State private var selectedCourse: Course?
    @State private var sortOrder: SortOrder = .name
    @State private var filterLevel: String = "All"
    
    enum SortOrder: String, CaseIterable {
        case name = "Name"
        case datePublished = "Date Published"
        case level = "Level"
        
        var systemImage: String {
            switch self {
            case .name: return "textformat"
            case .datePublished: return "calendar"
            case .level: return "chart.bar"
            }
        }
    }
    
    private var filteredAndSortedCourses: [Course] {
        let courses = dataService.courses.allEntities
        
        // Filter by level
        let filtered = filterLevel == "All" ? courses : courses.filter { 
            $0.educationalLevel?.lowercased() == filterLevel.lowercased() 
        }
        
        // Sort
        return filtered.sorted { first, second in
            switch sortOrder {
            case .name:
                return first.name < second.name
            case .datePublished:
                return (first.datePublished ?? "") > (second.datePublished ?? "")
            case .level:
                return (first.educationalLevel ?? "") < (second.educationalLevel ?? "")
            }
        }
    }
    
    private var availableLevels: [String] {
        let levels = Set(dataService.courses.allEntities.compactMap { $0.educationalLevel })
        return ["All"] + Array(levels).sorted()
    }
    
    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 16) {
                // Controls
                VStack(alignment: .leading, spacing: 12) {
                    // Sort picker
                    HStack {
                        Text("Sort by:")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Picker("Sort", selection: $sortOrder) {
                            ForEach(SortOrder.allCases, id: \.self) { order in
                                Label(order.rawValue, systemImage: order.systemImage)
                                    .tag(order)
                            }
                        }
                        .pickerStyle(.menu)
                    }
                    
                    // Level filter
                    HStack {
                        Text("Level:")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Picker("Level", selection: $filterLevel) {
                            ForEach(availableLevels, id: \.self) { level in
                                Text(level).tag(level)
                            }
                        }
                        .pickerStyle(.menu)
                    }
                }
                .padding(.horizontal)
                
                Divider()
                
                // Course list
                List(filteredAndSortedCourses, selection: $selectedCourse) { course in
                    CourseRowView(course: course)
                        .tag(course)
                }
                .listStyle(.sidebar)
            }
            .navigationTitle("Courses (\(filteredAndSortedCourses.count))")
        } detail: {
            if let course = selectedCourse {
                CourseDetailView(course: course)
            } else {
                ContentUnavailableView(
                    "Select a Course",
                    systemImage: "book.fill",
                    description: Text("Choose a course from the sidebar to view its details")
                )
            }
        }
    }
}

struct CourseRowView: View {
    let course: Course
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(course.name)
                .font(.headline)
                .lineLimit(2)
            
            if let level = course.educationalLevel {
                Text(level)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(levelColor(level).opacity(0.2))
                    .foregroundColor(levelColor(level))
                    .cornerRadius(4)
            }
            
            if !course.topics.isEmpty {
                Text(course.topics.prefix(3).joined(separator: " • "))
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            
            if let rating = course.aggregateRating {
                HStack(spacing: 4) {
                    Image(systemName: "star.fill")
                        .foregroundColor(.yellow)
                        .font(.caption)
                    Text(rating.ratingValue)
                        .font(.caption)
                        .fontWeight(.medium)
                    Text("(\(rating.reviewCount))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(.vertical, 2)
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

struct CourseDetailView: View {
    let course: Course
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 12) {
                    Text(course.name)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    if let level = course.educationalLevel {
                        HStack {
                            Text(level)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 4)
                                .background(levelColor(level).opacity(0.2))
                                .foregroundColor(levelColor(level))
                                .cornerRadius(8)
                            
                            if let published = course.datePublished {
                                Text("Published: \(published)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    
                    if let rating = course.aggregateRating {
                        HStack(spacing: 8) {
                            HStack(spacing: 2) {
                                ForEach(0..<5) { index in
                                    Image(systemName: index < Int(Double(rating.ratingValue) ?? 0) ? "star.fill" : "star")
                                        .foregroundColor(.yellow)
                                        .font(.caption)
                                }
                            }
                            Text(rating.ratingValue)
                                .fontWeight(.medium)
                            Text("(\(rating.reviewCount) reviews)")
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Divider()
                
                // Description
                VStack(alignment: .leading, spacing: 8) {
                    Text("Description")
                        .font(.headline)
                    Text(course.description)
                        .font(.body)
                }
                
                // Topics
                if !course.topics.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Topics")
                            .font(.headline)
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 8) {
                            ForEach(course.topics, id: \.self) { topic in
                                Text(topic)
                                    .font(.caption)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(Color.blue.opacity(0.1))
                                    .foregroundColor(.blue)
                                    .cornerRadius(6)
                            }
                        }
                    }
                }
                
                // Learning Objectives
                if !course.objectives.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Learning Objectives")
                            .font(.headline)
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(course.objectives, id: \.self) { objective in
                                HStack(alignment: .top, spacing: 8) {
                                    Text("•")
                                        .foregroundColor(.blue)
                                        .fontWeight(.bold)
                                    Text(objective)
                                        .font(.body)
                                }
                            }
                        }
                    }
                }
                
                // Modules
                if !course.modules.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Course Modules (\(course.modules.count))")
                            .font(.headline)
                        
                        ForEach(course.modules) { module in
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(module.title)
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                    Spacer()
                                    Text("\(module.steps.count) steps")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                
                                if !module.description.isEmpty {
                                    Text(module.description)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding()
                            .background(Color(.controlBackgroundColor))
                            .cornerRadius(8)
                        }
                    }
                }
                
                // Additional Info
                if let additionalInfo = course.additionalInfo {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Additional Information")
                            .font(.headline)
                        
                        if !additionalInfo.prerequisites.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Prerequisites:")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                ForEach(additionalInfo.prerequisites, id: \.self) { prerequisite in
                                    HStack(alignment: .top, spacing: 8) {
                                        Text("•")
                                            .foregroundColor(.orange)
                                        Text(prerequisite)
                                            .font(.body)
                                    }
                                }
                            }
                        }
                        
                        Text("Duration: \(additionalInfo.duration)")
                            .font(.subheadline)
                    }
                }
                
                // Actions
                HStack(spacing: 12) {
                    Button("Open in Browser") {
                        NSWorkspace.shared.open(course.url)
                    }
                    .buttonStyle(.borderedProminent)
                    
                    Button("Copy URL") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(course.url.absoluteString, forType: .string)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
        .navigationTitle(course.name)
        .navigationBarTitleDisplayMode(.inline)
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
