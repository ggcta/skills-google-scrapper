import Foundation

/// Base protocol for all CSB entities
public protocol BaseEntity: Identifiable, Codable, Hashable, Comparable {
    var id: String { get set }
    var name: String { get set }
    var description: String { get set }
    var datePublished: String? { get set }
    var url: URL { get }
    var type: EntityType { get }
}

/// Entity types supported by the application
public enum EntityType: String, CaseIterable, Codable {
    case course = "Course"
    case path = "Path"
    case lab = "Lab"
    
    public var baseURL: String {
        switch self {
        case .course:
            return "https://www.cloudskillsboost.google/course_templates"
        case .path:
            return "https://www.cloudskillsboost.google/paths"
        case .lab:
            return "https://www.cloudskillsboost.google/catalog_lab"
        }
    }
}

/// Default implementations for BaseEntity
public extension BaseEntity {
    var url: URL {
        URL(string: "\(type.baseURL)/\(id)")!
    }
    
    // Hashable conformance
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
        hasher.combine(type)
    }
    
    // Comparable conformance - sort by name, then by id
    public static func < (lhs: Self, rhs: Self) -> Bool {
        if lhs.name != rhs.name {
            return lhs.name < rhs.name
        }
        return lhs.id < rhs.id
    }
    
    // Equatable conformance (required for Hashable)
    public static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.id == rhs.id && lhs.type == rhs.type
    }
}
