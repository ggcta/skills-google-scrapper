import SwiftUI
import CSBHelperCore

struct SearchView: View {
    @EnvironmentObject var dataService: DataService
    @Binding var searchText: String
    @State private var searchResults: SearchResults?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            if searchText.isEmpty {
                // Welcome screen
                VStack(spacing: 20) {
                    Image(systemName: "magnifyingglass.circle.fill")
                        .font(.system(size: 80))
                        .foregroundColor(.blue)
                    
                    Text("Welcome to CSB Helper")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("Search for courses, paths, labs, and topics from Google Cloud Skills Boost")
                        .font(.title3)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        StatRow(icon: "book.fill", title: "Courses", count: dataService.courses.count, color: .blue)
                        StatRow(icon: "map.fill", title: "Paths", count: dataService.paths.count, color: .green)
                        StatRow(icon: "flask.fill", title: "Labs", count: dataService.labs.count, color: .orange)
                        StatRow(icon: "tag.fill", title: "Topics", count: dataService.topics.allTopics.count, color: .purple)
                    }
                    .padding()
                    .background(Color(.controlBackgroundColor))
                    .cornerRadius(12)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                // Search results
                if let results = searchResults {
                    SearchResultsView(results: results, searchText: searchText)
                } else {
                    ProgressView("Searching...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .padding()
        .onChange(of: searchText) { _, newValue in
            Task {
                await performSearch(query: newValue)
            }
        }
    }
    
    @MainActor
    private func performSearch(query: String) async {
        guard !query.isEmpty else {
            searchResults = nil
            return
        }
        
        // Add a small delay to avoid too many searches while typing
        try? await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds
        
        // Check if search text is still the same (user might have continued typing)
        guard query == searchText else { return }
        
        searchResults = dataService.searchAll(query: query)
    }
}

struct StatRow: View {
    let icon: String
    let title: String
    let count: Int
    let color: Color
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(color)
                .frame(width: 20)
            
            Text(title)
                .fontWeight(.medium)
            
            Spacer()
            
            Text("\(count)")
                .fontWeight(.bold)
                .foregroundColor(color)
        }
    }
}

struct SearchResultsView: View {
    let results: SearchResults
    let searchText: String
    
    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 20) {
                // Header
                HStack {
                    Text("Search Results")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Spacer()
                    
                    Text("\(results.totalCount) results")
                        .foregroundColor(.secondary)
                }
                
                if results.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 50))
                            .foregroundColor(.secondary)
                        
                        Text("No results found for '\(searchText)'")
                            .font(.title3)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 50)
                } else {
                    // Courses
                    if !results.courses.isEmpty {
                        SearchSection(title: "Courses", icon: "book.fill", color: .blue) {
                            ForEach(results.courses) { course in
                                CourseRowView(course: course)
                            }
                        }
                    }
                    
                    // Paths
                    if !results.paths.isEmpty {
                        SearchSection(title: "Paths", icon: "map.fill", color: .green) {
                            ForEach(results.paths) { path in
                                PathRowView(path: path)
                            }
                        }
                    }
                    
                    // Labs
                    if !results.labs.isEmpty {
                        SearchSection(title: "Labs", icon: "flask.fill", color: .orange) {
                            ForEach(results.labs) { lab in
                                LabRowView(lab: lab)
                            }
                        }
                    }
                    
                    // Topics
                    if !results.topics.isEmpty {
                        SearchSection(title: "Topics", icon: "tag.fill", color: .purple) {
                            ForEach(results.topics, id: \.self) { topic in
                                TopicRowView(topic: topic)
                            }
                        }
                    }
                }
            }
            .padding()
        }
    }
}

struct SearchSection<Content: View>: View {
    let title: String
    let icon: String
    let color: Color
    @ViewBuilder let content: Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                content
            }
        }
    }
}
