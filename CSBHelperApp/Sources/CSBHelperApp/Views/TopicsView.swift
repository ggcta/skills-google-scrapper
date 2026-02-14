import SwiftUI
import CSBHelperCore

struct TopicsView: View {
    @EnvironmentObject var dataService: DataService
    @State private var selectedTopic: String?
    @State private var sortOrder: TopicSortOrder = .alphabetical
    
    enum TopicSortOrder: String, CaseIterable {
        case alphabetical = "Alphabetical"
        case courseCount = "Course Count"
        
        var systemImage: String {
            switch self {
            case .alphabetical: return "textformat"
            case .courseCount: return "number"
            }
        }
    }
    
    private var sortedTopics: [String] {
        let topics = dataService.topics.allTopics
        
        switch sortOrder {
        case .alphabetical:
            return topics.sorted()
        case .courseCount:
            return topics.sorted { first, second in
                let firstCount = dataService.topics.courses(for: first).count
                let secondCount = dataService.topics.courses(for: second).count
                return firstCount > secondCount
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
                        ForEach(TopicSortOrder.allCases, id: \.self) { order in
                            Label(order.rawValue, systemImage: order.systemImage)
                                .tag(order)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Spacer()
                }
                .padding(.horizontal)
                
                Divider()
                
                // Topics list
                List(sortedTopics, id: \.self, selection: $selectedTopic) { topic in
                    TopicRowView(topic: topic, courseCount: dataService.topics.courses(for: topic).count)
                        .tag(topic)
                }
                .listStyle(.sidebar)
            }
            .navigationTitle("Topics (\(sortedTopics.count))")
        } detail: {
            if let topic = selectedTopic {
                TopicDetailView(topic: topic, courses: dataService.topics.courses(for: topic))
            } else {
                ContentUnavailableView(
                    "Select a Topic",
                    systemImage: "tag.fill",
                    description: Text("Choose a topic from the sidebar to view its courses")
                )
            }
        }
    }
}

struct TopicRowView: View {
    let topic: String
    let courseCount: Int
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(topic)
                    .font(.headline)
                    .lineLimit(2)
                
                Text("\(courseCount) course\(courseCount == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Visual indicator for course count
            Circle()
                .fill(topicColor)
                .frame(width: 8, height: 8)
        }
        .padding(.vertical, 2)
    }
    
    private var topicColor: Color {
        switch courseCount {
        case 1...3:
            return .green
        case 4...7:
            return .orange
        case 8...15:
            return .blue
        default:
            return .purple
        }
    }
}

struct TopicDetailView: View {
    let topic: String
    let courses: [Course]
    @State private var sortOrder: CourseSortOrder = .name
    
    enum CourseSortOrder: String, CaseIterable {
        case name = "Name"
        case level = "Level"
        case rating = "Rating"
        case datePublished = "Date Published"
        
        var systemImage: String {
            switch self {
            case .name: return "textformat"
            case .level: return "chart.bar"
            case .rating: return "star"
            case .datePublished: return "calendar"
            }
        }
    }
    
    private var sortedCourses: [Course] {
        courses.sorted { first, second in
            switch sortOrder {
            case .name:
                return first.name < second.name
            case .level:
                return (first.educationalLevel ?? "") < (second.educationalLevel ?? "")
            case .rating:
                let firstRating = Double(first.aggregateRating?.ratingValue ?? "0") ?? 0
                let secondRating = Double(second.aggregateRating?.ratingValue ?? "0") ?? 0
                return firstRating > secondRating
            case .datePublished:
                return (first.datePublished ?? "") > (second.datePublished ?? "")
            }
        }
    }
    
    private var levelDistribution: [String: Int] {
        var distribution: [String: Int] = [:]
        for course in courses {
            let level = course.educationalLevel ?? "Unknown"
            distribution[level, default: 0] += 1
        }
        return distribution
    }
    
    private var averageRating: Double {
        let ratings = courses.compactMap { course in
            Double(course.aggregateRating?.ratingValue ?? "")
        }
        guard !ratings.isEmpty else { return 0 }
        return ratings.reduce(0, +) / Double(ratings.count)
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Image(systemName: "tag.fill")
                            .foregroundColor(.purple)
                            .font(.title2)
                        
                        Text(topic)
                            .font(.largeTitle)
                            .fontWeight(.bold)
                    }
                    
                    Text("\(courses.count) course\(courses.count == 1 ? "" : "s") in this topic")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                // Statistics
                VStack(alignment: .leading, spacing: 12) {
                    Text("Statistics")
                        .font(.headline)
                    
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 12) {
                        StatCard(title: "Total Courses", value: "\(courses.count)", icon: "book.fill", color: .blue)
                        StatCard(title: "Avg. Rating", value: String(format: "%.1f", averageRating), icon: "star.fill", color: .yellow)
                    }
                    
                    // Level distribution
                    if !levelDistribution.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Level Distribution")
                                .font(.subheadline)
                                .fontWeight(.medium)
                            
                            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 8) {
                                ForEach(levelDistribution.sorted(by: { $0.key < $1.key }), id: \.key) { level, count in
                                    HStack {
                                        Text(level)
                                            .font(.caption)
                                        Spacer()
                                        Text("\(count)")
                                            .font(.caption)
                                            .fontWeight(.bold)
                                            .foregroundColor(levelColor(level))
                                    }
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(levelColor(level).opacity(0.1))
                                    .cornerRadius(6)
                                }
                            }
                        }
                    }
                }
                .padding()
                .background(Color(.controlBackgroundColor))
                .cornerRadius(12)
                
                Divider()
                
                // Course list
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Courses")
                            .font(.headline)
                        
                        Spacer()
                        
                        Picker("Sort", selection: $sortOrder) {
                            ForEach(CourseSortOrder.allCases, id: \.self) { order in
                                Label(order.rawValue, systemImage: order.systemImage)
                                    .tag(order)
                            }
                        }
                        .pickerStyle(.menu)
                    }
                    
                    ForEach(sortedCourses) { course in
                        TopicCourseRowView(course: course)
                    }
                }
            }
            .padding()
        }
        .navigationTitle(topic)
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

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
            }
            
            HStack {
                Text(value)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(color)
                Spacer()
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(8)
    }
}

struct TopicCourseRowView: View {
    let course: Course
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(course.name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(2)
                    
                    Text(course.description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
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
            }
            
            HStack {
                Button("Open Course") {
                    NSWorkspace.shared.open(course.url)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                
                Spacer()
                
                if let published = course.datePublished {
                    Text(published)
                        .font(.caption2)
                        .foregroundColor(.secondary)
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
