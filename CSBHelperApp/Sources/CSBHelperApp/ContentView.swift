import SwiftUI
import CSBHelperCore

struct ContentView: View {
    @EnvironmentObject var dataService: DataService
    @State private var selectedTab: Tab = .search
    @State private var searchText = ""
    
    enum Tab: String, CaseIterable {
        case search = "Search"
        case courses = "Courses"
        case paths = "Paths"
        case labs = "Labs"
        case topics = "Topics"
        
        var systemImage: String {
            switch self {
            case .search: return "magnifyingglass"
            case .courses: return "book.fill"
            case .paths: return "map.fill"
            case .labs: return "flask.fill"
            case .topics: return "tag.fill"
            }
        }
    }
    
    var body: some View {
        NavigationSplitView {
            // Sidebar
            List(Tab.allCases, id: \.self, selection: $selectedTab) { tab in
                Label(tab.rawValue, systemImage: tab.systemImage)
                    .tag(tab)
            }
            .navigationTitle("CSB Helper")
            .frame(minWidth: 200)
        } detail: {
            // Main content
            Group {
                switch selectedTab {
                case .search:
                    SearchView(searchText: $searchText)
                case .courses:
                    CoursesView()
                case .paths:
                    PathsView()
                case .labs:
                    LabsView()
                case .topics:
                    TopicsView()
                }
            }
            .frame(minWidth: 600, minHeight: 400)
        }
        .searchable(text: $searchText, placement: .toolbar)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Refresh") {
                    Task {
                        await dataService.loadAllData()
                    }
                }
            }
        }
    }
}
