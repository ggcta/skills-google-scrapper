# CSB Helper - Swift Edition

A modern Swift implementation of the Google Cloud Skills Boost Helper, providing both command-line and macOS GUI interfaces for managing your CSB learning content.

## Features

### Core Models
- **Identifiable, Codable, Hashable, Comparable** Swift models
- **Course**: Full course data with modules, ratings, and learning objectives
- **Path**: Learning paths with course collections
- **Lab**: Hands-on labs with step-by-step instructions
- **Topics**: Auto-extracted topic categorization

### Command Line Interface
- **List**: Browse courses, paths, and labs
- **Search**: Full-text search across all content
- **Show**: Detailed view of specific entities
- **Topics**: Topic-based course discovery

### macOS GUI Application
- **Native SwiftUI interface** optimized for macOS 13+
- **Split-view navigation** with sidebar and detail views
- **Real-time search** with instant results
- **Rich detail views** with ratings, topics, and metadata
- **Settings panel** for configuration management

## Architecture

### Swift Package Structure
```
CSBHelperSwift/
├── Sources/
│   ├── CSBHelperCore/          # Shared library
│   │   ├── Models/             # Data models
│   │   ├── Services/           # Business logic
│   │   └── Utils/              # Utility functions
│   └── CSBHelperCLI/           # Command-line app
└── Tests/                      # Unit tests
```

### macOS App Structure
```
CSBHelperApp/
└── Sources/
    └── CSBHelperApp/
        ├── Views/              # SwiftUI views
        │   ├── SearchView.swift
        │   ├── CoursesView.swift
        │   ├── PathsView.swift
        │   ├── LabsView.swift
        │   ├── TopicsView.swift
        │   └── SettingsView.swift
        └── main.swift          # App entry point
```

## Installation & Usage

### Prerequisites
- macOS 14.0+ (for GUI app with @Observable support)
- Swift 5.9+
- Xcode 15+ (for development)

### Command Line Interface

1. **Build the CLI:**
   ```bash
   cd CSBHelperSwift
   swift build -c release
   ```

2. **Run commands:**
   ```bash
   # List all courses
   .build/release/CSBHelperCLI list --type courses
   
   # Search for content
   .build/release/CSBHelperCLI search "Google Cloud"
   
   # Show course details
   .build/release/CSBHelperCLI show --type course --id 60
   
   # List topics
   .build/release/CSBHelperCLI topics
   ```

### macOS GUI Application

1. **Build and run:**
   ```bash
   cd CSBHelperApp
   swift run
   ```

2. **Or open in Xcode:**
   - Open `CSBHelperApp/Package.swift` in Xcode
   - Build and run the target

## Data Models

### BaseEntity Protocol
All entities conform to:
- `Identifiable`: Unique ID for SwiftUI lists
- `Codable`: JSON serialization/deserialization
- `Hashable`: Set operations and dictionary keys
- `Comparable`: Automatic sorting capabilities

### Course Model
```swift
struct Course: BaseEntity {
    var id: String
    var name: String
    var description: String
    var datePublished: String?
    let educationalLevel: String?
    let topics: [String]           // from 'about' field
    let objectives: [String]       // from 'teaches' field
    let modules: [CourseModule]
    let aggregateRating: AggregateRating?
    // ... additional properties
}
```

### Path Model
```swift
struct Path: BaseEntity {
    var id: String
    var name: String
    var description: String
    var datePublished: String?
    let hasPart: [PathCourse]      // courses in path
    let availableLanguage: [String]
    // ... additional properties
}
```

### Lab Model
```swift
struct Lab: BaseEntity {
    var id: String
    var name: String
    var description: String
    var datePublished: String?
    let steps: [String: String]    // step number -> description
    // ... additional properties
}
```

## Services

### DataService
- **@Observable** for SwiftUI state management
- **Async data loading** from JSON files
- **Search functionality** across all entity types
- **Topic extraction** from course metadata
- **Thread-safe operations**

### Collections
- **EntityCollection<T>**: Generic collection wrapper
- **TopicCollection**: Specialized topic management
- **Search capabilities** with filtering and sorting

## GUI Features

### Search View
- **Welcome screen** with statistics
- **Real-time search** with debounced input
- **Categorized results** by entity type
- **Empty state handling**

### Entity Views
- **Master-detail navigation** with split views
- **Sorting and filtering** options
- **Rich detail views** with metadata
- **External link integration** (open in browser)

### Settings
- **Data folder configuration**
- **Auto-refresh settings**
- **Statistics display**
- **Cache management**

## CLI Commands

### List Command
```bash
csbhelper list --type [courses|paths|labs] --data-path ./data
```

### Search Command
```bash
csbhelper search "kubernetes" --data-path ./data
```

### Show Command
```bash
csbhelper show --type course --id 60 --data-path ./data
```

### Topics Command
```bash
csbhelper topics --topic "Cloud Computing" --data-path ./data
```

## Data Compatibility

The Swift implementation is fully compatible with the original Python version's JSON data format:
- Reads existing `data/` folder structure
- Supports all original JSON schemas
- Maintains backward compatibility
- Can run alongside Python version

## Development

### Adding New Features
1. **Models**: Extend `BaseEntity` protocol
2. **Services**: Add to `DataService` class
3. **Views**: Create SwiftUI views in `Views/` folder
4. **CLI**: Add commands to `main.swift`

### Testing
```bash
swift test
```

### Building for Distribution
```bash
# CLI
swift build -c release --arch arm64 --arch x86_64

# macOS App (requires Xcode)
xcodebuild -scheme CSBHelperApp -configuration Release
```

## Migration from Python

The Swift version provides:
- **Better performance** with native compilation
- **Modern UI** with SwiftUI
- **Type safety** with Swift's type system
- **Memory efficiency** with ARC
- **Native macOS integration**

While maintaining:
- **Same data format** (JSON files)
- **Same functionality** (search, browse, organize)
- **Same workflow** (compatible with existing data)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow Swift coding conventions
4. Add tests for new functionality
5. Submit a pull request

## License

Same as the original Python version - open source and free to use.
