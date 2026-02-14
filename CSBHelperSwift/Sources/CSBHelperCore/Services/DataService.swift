import Foundation
import Observation

/// Service for loading and saving entity data from JSON files
@Observable
public class DataService {
    private let dataFolderURL: URL
    private let fileManager = FileManager.default
    
    // Collections
    public let courses = CourseCollection(name: "Courses")
    public let paths = PathCollection(name: "Paths")
    public let labs = LabCollection(name: "Labs")
    public let topics = TopicCollection()
    
    public init(dataFolderPath: String = "data") {
        // Default to the data folder in the current working directory
        let currentDirectory = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        self.dataFolderURL = currentDirectory.appendingPathComponent(dataFolderPath)
        
        // Create data folder if it doesn't exist
        try? fileManager.createDirectory(at: dataFolderURL, withIntermediateDirectories: true)
    }
    
    /// Load all data from JSON files
    public func loadAllData() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.loadCourses() }
            group.addTask { await self.loadPaths() }
            group.addTask { await self.loadLabs() }
        }
        
        // Extract topics after courses are loaded
        topics.extractTopics(from: courses)
    }
    
    /// Load courses from JSON files
    @MainActor
    private func loadCourses() async {
        let coursesData = await loadEntitiesFromFolder(entityType: Course.self, folderName: "courses")
        courses.clear()
        for course in coursesData {
            courses.addEntity(course)
        }
    }
    
    /// Load paths from JSON files
    @MainActor
    private func loadPaths() async {
        let pathsData = await loadEntitiesFromFolder(entityType: Path.self, folderName: "paths")
        paths.clear()
        for path in pathsData {
            paths.addEntity(path)
        }
    }
    
    /// Load labs from JSON files
    @MainActor
    private func loadLabs() async {
        let labsData = await loadEntitiesFromFolder(entityType: Lab.self, folderName: "labs")
        labs.clear()
        for lab in labsData {
            labs.addEntity(lab)
        }
    }
    
    /// Generic method to load entities from a folder
    private func loadEntitiesFromFolder<T: BaseEntity>(entityType: T.Type, folderName: String) async -> [T] {
        let folderURL = dataFolderURL.appendingPathComponent(folderName)
        
        guard fileManager.fileExists(atPath: folderURL.path) else {
            print("Folder does not exist: \(folderURL.path)")
            return []
        }
        
        do {
            let fileURLs = try fileManager.contentsOfDirectory(at: folderURL, includingPropertiesForKeys: nil)
                .filter { $0.pathExtension == "json" }
            
            var entities: [T] = []
            
            for fileURL in fileURLs {
                if let entity = await loadEntity(from: fileURL, as: entityType) {
                    entities.append(entity)
                }
            }
            
            return entities
        } catch {
            print("Error reading folder \(folderName): \(error)")
            return []
        }
    }
    
    /// Load a single entity from a JSON file
    private func loadEntity<T: BaseEntity>(from fileURL: URL, as entityType: T.Type) async -> T? {
        do {
            let data = try Data(contentsOf: fileURL)
            let entity = try JSONDecoder().decode(entityType, from: data)
            return entity
        } catch {
            print("Error loading entity from \(fileURL.lastPathComponent): \(error)")
            return nil
        }
    }
    
    /// Save an entity to a JSON file
    public func saveEntity<T: BaseEntity>(_ entity: T) async throws {
        let folderName: String
        switch entity.type {
        case .course:
            folderName = "courses"
        case .path:
            folderName = "paths"
        case .lab:
            folderName = "labs"
        }
        
        let folderURL = dataFolderURL.appendingPathComponent(folderName)
        try fileManager.createDirectory(at: folderURL, withIntermediateDirectories: true)
        
        let fileURL = folderURL.appendingPathComponent("\(entity.id).json")
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        
        let data = try encoder.encode(entity)
        try data.write(to: fileURL)
    }
    
    /// Search across all entity types
    public func searchAll(query: String) -> SearchResults {
        SearchResults(
            courses: courses.search(query: query),
            paths: paths.search(query: query),
            labs: labs.search(query: query),
            topics: topics.searchTopics(query: query)
        )
    }
    
    /// Refresh topics from current courses
    @MainActor
    public func refreshTopics() {
        topics.extractTopics(from: courses)
    }
}

/// Search results container
public struct SearchResults {
    public let courses: [Course]
    public let paths: [Path]
    public let labs: [Lab]
    public let topics: [String]
    
    public var isEmpty: Bool {
        courses.isEmpty && paths.isEmpty && labs.isEmpty && topics.isEmpty
    }
    
    public var totalCount: Int {
        courses.count + paths.count + labs.count + topics.count
    }
}
