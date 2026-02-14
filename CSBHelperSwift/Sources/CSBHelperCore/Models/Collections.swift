import Foundation
import Observation

/// Generic collection wrapper for managing entities
@Observable
public class EntityCollection<T: BaseEntity> {
    private(set) var entities: [String: T] = [:]
    private(set) var name: String
    
    public init(name: String) {
        self.name = name
    }
    
    /// Get all entities as an array
    public var allEntities: [T] {
        Array(entities.values).sorted()
    }
    
    /// Get entity by ID
    public func entity(withId id: String) -> T? {
        entities[id]
    }
    
    /// Add or update entity
    public func addEntity(_ entity: T) {
        entities[entity.id] = entity
    }
    
    /// Remove entity by ID
    public func removeEntity(withId id: String) {
        entities.removeValue(forKey: id)
    }
    
    /// Clear all entities
    public func clear() {
        entities.removeAll()
    }
    
    /// Search entities by name or description
    public func search(query: String) -> [T] {
        guard !query.isEmpty else { return allEntities }
        
        let lowercaseQuery = query.lowercased()
        return allEntities.filter { entity in
            entity.name.lowercased().contains(lowercaseQuery) ||
            entity.description.lowercased().contains(lowercaseQuery) ||
            entity.id.lowercased().contains(lowercaseQuery)
        }
    }
    
    /// Get count of entities
    public var count: Int {
        entities.count
    }
}

/// Specialized collection for courses
public typealias CourseCollection = EntityCollection<Course>

/// Specialized collection for paths
public typealias PathCollection = EntityCollection<Path>

/// Specialized collection for labs
public typealias LabCollection = EntityCollection<Lab>

/// Topics collection that extracts topics from courses
@Observable
public class TopicCollection {
    private(set) var topics: [String: [Course]] = [:]
    
    /// Extract topics from courses
    public func extractTopics(from courses: CourseCollection) {
        var newTopics: [String: [Course]] = [:]
        
        for course in courses.allEntities {
            for topic in course.topics {
                if newTopics[topic] == nil {
                    newTopics[topic] = []
                }
                newTopics[topic]?.append(course)
            }
        }
        
        // Sort courses within each topic
        for topic in newTopics.keys {
            newTopics[topic]?.sort()
        }
        
        self.topics = newTopics
    }
    
    /// Get all topic names sorted
    public var allTopics: [String] {
        Array(topics.keys).sorted()
    }
    
    /// Get courses for a specific topic
    public func courses(for topic: String) -> [Course] {
        topics[topic] ?? []
    }
    
    /// Search topics
    public func searchTopics(query: String) -> [String] {
        guard !query.isEmpty else { return allTopics }
        
        let lowercaseQuery = query.lowercased()
        return allTopics.filter { $0.lowercased().contains(lowercaseQuery) }
    }
}
