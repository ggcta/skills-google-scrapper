import Foundation
import ArgumentParser
import CSBHelperCore

@main
struct CSBHelperCLI: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "csbhelper",
        abstract: "Google Cloud Skills Boost Helper - Swift Edition",
        discussion: """
        A Swift implementation of the CSB Helper tool for managing Google Cloud Skills Boost content.
        Load, browse, and search through courses, paths, and labs from your local JSON data.
        """,
        version: "1.0.0",
        subcommands: [
            ListCommand.self,
            SearchCommand.self,
            ShowCommand.self,
            TopicsCommand.self
        ],
        defaultSubcommand: ListCommand.self
    )
}

struct ListCommand: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "list",
        abstract: "List all entities of a specific type"
    )
    
    @Option(name: .shortAndLong, help: "Entity type to list (courses, paths, labs)")
    var type: String = "courses"
    
    @Option(name: .shortAndLong, help: "Path to data folder")
    var dataPath: String = "data"
    
    func run() async throws {
        let dataService = DataService(dataFolderPath: dataPath)
        await dataService.loadAllData()
        
        switch type.lowercased() {
        case "courses", "course":
            await listCourses(dataService.courses)
        case "paths", "path":
            await listPaths(dataService.paths)
        case "labs", "lab":
            await listLabs(dataService.labs)
        default:
            print("Unknown type: \(type). Use 'courses', 'paths', or 'labs'")
        }
    }
    
    @MainActor
    private func listCourses(_ collection: CourseCollection) {
        let courses = collection.allEntities
        print("📚 Found \(courses.count) courses:")
        print()
        
        for course in courses {
            print("ID: \(course.id)")
            print("Name: \(course.name)")
            print("Level: \(course.educationalLevel ?? "N/A")")
            print("Topics: \(course.topics.joined(separator: ", "))")
            print("URL: \(course.url)")
            print("---")
        }
    }
    
    @MainActor
    private func listPaths(_ collection: PathCollection) {
        let paths = collection.allEntities
        print("🛤️  Found \(paths.count) paths:")
        print()
        
        for path in paths {
            print("ID: \(path.id)")
            print("Name: \(path.name)")
            print("Courses: \(path.courses.count)")
            print("Published: \(path.datePublished ?? "N/A")")
            print("URL: \(path.url)")
            print("---")
        }
    }
    
    @MainActor
    private func listLabs(_ collection: LabCollection) {
        let labs = collection.allEntities
        print("🧪 Found \(labs.count) labs:")
        print()
        
        for lab in labs {
            print("ID: \(lab.id)")
            print("Name: \(lab.name)")
            print("Steps: \(lab.steps.count)")
            print("Published: \(lab.datePublished ?? "N/A")")
            print("URL: \(lab.url)")
            print("---")
        }
    }
}

struct SearchCommand: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "search",
        abstract: "Search across all entities"
    )
    
    @Argument(help: "Search query")
    var query: String
    
    @Option(name: .shortAndLong, help: "Path to data folder")
    var dataPath: String = "data"
    
    func run() async throws {
        let dataService = DataService(dataFolderPath: dataPath)
        await dataService.loadAllData()
        
        let results = await dataService.searchAll(query: query)
        
        print("🔍 Search results for '\(query)':")
        print("Found \(results.totalCount) total results")
        print()
        
        if !results.courses.isEmpty {
            print("📚 Courses (\(results.courses.count)):")
            for course in results.courses {
                print("  • \(course.name) (ID: \(course.id))")
            }
            print()
        }
        
        if !results.paths.isEmpty {
            print("🛤️  Paths (\(results.paths.count)):")
            for path in results.paths {
                print("  • \(path.name) (ID: \(path.id))")
            }
            print()
        }
        
        if !results.labs.isEmpty {
            print("🧪 Labs (\(results.labs.count)):")
            for lab in results.labs {
                print("  • \(lab.name) (ID: \(lab.id))")
            }
            print()
        }
        
        if !results.topics.isEmpty {
            print("🏷️  Topics (\(results.topics.count)):")
            for topic in results.topics {
                print("  • \(topic)")
            }
        }
        
        if results.isEmpty {
            print("No results found.")
        }
    }
}

struct ShowCommand: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "show",
        abstract: "Show detailed information about a specific entity"
    )
    
    @Argument(help: "Entity ID")
    var id: String
    
    @Option(name: .shortAndLong, help: "Entity type (course, path, lab)")
    var type: String
    
    @Option(name: .shortAndLong, help: "Path to data folder")
    var dataPath: String = "data"
    
    func run() async throws {
        let dataService = DataService(dataFolderPath: dataPath)
        await dataService.loadAllData()
        
        switch type.lowercased() {
        case "course":
            if let course = await dataService.courses.entity(withId: id) {
                await showCourse(course)
            } else {
                print("Course with ID '\(id)' not found.")
            }
        case "path":
            if let path = await dataService.paths.entity(withId: id) {
                await showPath(path)
            } else {
                print("Path with ID '\(id)' not found.")
            }
        case "lab":
            if let lab = await dataService.labs.entity(withId: id) {
                await showLab(lab)
            } else {
                print("Lab with ID '\(id)' not found.")
            }
        default:
            print("Unknown type: \(type). Use 'course', 'path', or 'lab'")
        }
    }
    
    @MainActor
    private func showCourse(_ course: Course) {
        print("📚 Course Details")
        print("================")
        print("ID: \(course.id)")
        print("Name: \(course.name)")
        print("Description: \(course.description)")
        print("Level: \(course.educationalLevel ?? "N/A")")
        print("Published: \(course.datePublished ?? "N/A")")
        print("Language: \(course.inLanguage ?? "N/A")")
        print("URL: \(course.url)")
        print()
        
        if !course.topics.isEmpty {
            print("Topics:")
            for topic in course.topics {
                print("  • \(topic)")
            }
            print()
        }
        
        if !course.objectives.isEmpty {
            print("Learning Objectives:")
            for objective in course.objectives {
                print("  • \(objective)")
            }
            print()
        }
        
        if let rating = course.aggregateRating {
            print("Rating: \(rating.ratingValue) (\(rating.reviewCount) reviews)")
            print()
        }
        
        if !course.modules.isEmpty {
            print("Modules (\(course.modules.count)):")
            for module in course.modules {
                print("  • \(module.title) (\(module.steps.count) steps)")
            }
        }
    }
    
    @MainActor
    private func showPath(_ path: Path) {
        print("🛤️  Path Details")
        print("===============")
        print("ID: \(path.id)")
        print("Name: \(path.name)")
        print("Description: \(path.description)")
        print("Published: \(path.datePublished ?? "N/A")")
        print("Language: \(path.inLanguage ?? "N/A")")
        print("URL: \(path.url)")
        print()
        
        if !path.courses.isEmpty {
            print("Courses (\(path.courses.count)):")
            for course in path.courses {
                print("  • \(course.name) (ID: \(course.id))")
            }
        }
    }
    
    @MainActor
    private func showLab(_ lab: Lab) {
        print("🧪 Lab Details")
        print("==============")
        print("ID: \(lab.id)")
        print("Name: \(lab.name)")
        print("Description: \(lab.description)")
        print("Published: \(lab.datePublished ?? "N/A")")
        print("Language: \(lab.inLanguage ?? "N/A")")
        print("URL: \(lab.url)")
        print()
        
        if !lab.steps.isEmpty {
            print("Steps (\(lab.steps.count)):")
            for (key, value) in lab.orderedSteps {
                print("  \(key). \(value)")
            }
        }
    }
}

struct TopicsCommand: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "topics",
        abstract: "List all topics and their associated courses"
    )
    
    @Option(name: .shortAndLong, help: "Path to data folder")
    var dataPath: String = "data"
    
    @Option(name: .shortAndLong, help: "Show courses for specific topic")
    var topic: String?
    
    func run() async throws {
        let dataService = DataService(dataFolderPath: dataPath)
        await dataService.loadAllData()
        
        if let specificTopic = topic {
            await showTopicCourses(specificTopic, dataService.topics)
        } else {
            await listAllTopics(dataService.topics)
        }
    }
    
    @MainActor
    private func listAllTopics(_ topicCollection: TopicCollection) {
        let topics = topicCollection.allTopics
        print("🏷️  Found \(topics.count) topics:")
        print()
        
        for topic in topics {
            let courseCount = topicCollection.courses(for: topic).count
            print("• \(topic) (\(courseCount) courses)")
        }
    }
    
    @MainActor
    private func showTopicCourses(_ topic: String, _ topicCollection: TopicCollection) {
        let courses = topicCollection.courses(for: topic)
        
        if courses.isEmpty {
            print("No courses found for topic '\(topic)'")
            return
        }
        
        print("🏷️  Courses for topic '\(topic)' (\(courses.count)):")
        print()
        
        for course in courses {
            print("• \(course.name) (ID: \(course.id))")
            print("  Level: \(course.educationalLevel ?? "N/A")")
            if let rating = course.aggregateRating {
                print("  Rating: \(rating.ratingValue) (\(rating.reviewCount) reviews)")
            }
            print()
        }
    }
}
