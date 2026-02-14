import Foundation

/// Represents a course reference within a path
public struct PathCourse: Codable, Hashable, Identifiable {
    public let id: String
    public let type: String
    public let name: String
    public let description: String
    public let url: URL
    
    enum CodingKeys: String, CodingKey {
        case type = "@type"
        case name, description, url
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Extract ID from URL
        let urlString = try container.decode(String.self, forKey: .url)
        self.url = URL(string: urlString)!
        self.id = String(urlString.split(separator: "/").last ?? "")
        
        self.type = try container.decode(String.self, forKey: .type)
        self.name = try container.decode(String.self, forKey: .name)
        self.description = try container.decode(String.self, forKey: .description)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(type, forKey: .type)
        try container.encode(name, forKey: .name)
        try container.encode(description, forKey: .description)
        try container.encode(url, forKey: .url)
    }
    
    public init(id: String, type: String, name: String, description: String, url: URL) {
        self.id = id
        self.type = type
        self.name = name
        self.description = description
        self.url = url
    }
}

/// Represents a learning path entity from Google Cloud Skills Boost
public struct Path: BaseEntity {
    public var id: String
    public var name: String
    public var description: String
    public var datePublished: String?
    public let image: [String]
    public let inLanguage: String?
    public let availableLanguage: [String]
    public let hasPart: [PathCourse]
    
    public var type: EntityType { .path }
    
    // Computed property for easier access to courses
    public var courses: [PathCourse] { hasPart }
    
    enum CodingKeys: String, CodingKey {
        case id = "@id"
        case name, description, datePublished, image
        case inLanguage, availableLanguage, hasPart
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Extract ID from URL
        let idURL = try container.decode(String.self, forKey: .id)
        self.id = String(idURL.split(separator: "/").last ?? "")
        
        self.name = try container.decode(String.self, forKey: .name)
        self.description = try container.decode(String.self, forKey: .description)
        self.datePublished = try container.decodeIfPresent(String.self, forKey: .datePublished)
        self.image = try container.decodeIfPresent([String].self, forKey: .image) ?? []
        self.inLanguage = try container.decodeIfPresent(String.self, forKey: .inLanguage)
        self.availableLanguage = try container.decodeIfPresent([String].self, forKey: .availableLanguage) ?? []
        self.hasPart = try container.decodeIfPresent([PathCourse].self, forKey: .hasPart) ?? []
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(url.absoluteString, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(description, forKey: .description)
        try container.encodeIfPresent(datePublished, forKey: .datePublished)
        try container.encode(image, forKey: .image)
        try container.encodeIfPresent(inLanguage, forKey: .inLanguage)
        try container.encode(availableLanguage, forKey: .availableLanguage)
        try container.encode(hasPart, forKey: .hasPart)
    }
    
    // Manual initializer for creating paths programmatically
    public init(id: String, name: String, description: String, datePublished: String? = nil,
         image: [String] = [], inLanguage: String? = nil, availableLanguage: [String] = [],
         hasPart: [PathCourse] = []) {
        self.id = id
        self.name = name
        self.description = description
        self.datePublished = datePublished
        self.image = image
        self.inLanguage = inLanguage
        self.availableLanguage = availableLanguage
        self.hasPart = hasPart
    }
}
