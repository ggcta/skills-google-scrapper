import Foundation

/// Represents a course module with steps and activities
public struct CourseModule: Codable, Hashable, Identifiable {
    public let id: String
    public let title: String
    public let description: String
    public let steps: [CourseStep]
    public let expanded: Bool
    
    enum CodingKeys: String, CodingKey {
        case id, title, description, steps, expanded
    }
}

/// Represents a step within a course module
public struct CourseStep: Codable, Hashable, Identifiable {
    public let id: String
    public let prompt: String?
    public let isOptional: Bool
    public let activities: [String] // Simplified - could be more complex
    public let isComplete: Bool
    public let isTestedOut: Bool
    public let allActivitiesRequired: Bool
    
    enum CodingKeys: String, CodingKey {
        case id, prompt, isOptional, activities, isComplete, isTestedOut, allActivitiesRequired
    }
}

/// Represents aggregate rating information
public struct AggregateRating: Codable, Hashable {
    public let ratingValue: String
    public let reviewCount: String
    
    enum CodingKeys: String, CodingKey {
        case ratingValue, reviewCount
    }
}

/// Represents additional course information
public struct AdditionalInfo: Codable, Hashable {
    public let prerequisites: [String]
    public let duration: String
    
    enum CodingKeys: String, CodingKey {
        case prerequisites, duration
    }
}

/// Represents a course entity from Google Cloud Skills Boost
public struct Course: BaseEntity {
    public var id: String
    public var name: String
    public var description: String
    public var datePublished: String?
    public let educationalLevel: String?
    public let image: [String]
    public let about: [String] // Topics
    public let teaches: [String] // Objectives
    public let inLanguage: String?
    public let availableLanguage: [String]
    public let modules: [CourseModule]
    public let aggregateRating: AggregateRating?
    public let additionalInfo: AdditionalInfo?
    
    public var type: EntityType { .course }
    
    // Computed properties for easier access
    public var topics: [String] { about }
    public var objectives: [String] { teaches }
    
    enum CodingKeys: String, CodingKey {
        case id = "@id"
        case name, description, datePublished, educationalLevel, image
        case about, teaches, inLanguage, availableLanguage, modules
        case aggregateRating, additionalInfo
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Extract ID from URL
        let idURL = try container.decode(String.self, forKey: .id)
        self.id = String(idURL.split(separator: "/").last ?? "")
        
        self.name = try container.decode(String.self, forKey: .name)
        self.description = try container.decode(String.self, forKey: .description)
        self.datePublished = try container.decodeIfPresent(String.self, forKey: .datePublished)
        self.educationalLevel = try container.decodeIfPresent(String.self, forKey: .educationalLevel)
        self.image = try container.decodeIfPresent([String].self, forKey: .image) ?? []
        self.about = try container.decodeIfPresent([String].self, forKey: .about) ?? []
        self.teaches = try container.decodeIfPresent([String].self, forKey: .teaches) ?? []
        self.inLanguage = try container.decodeIfPresent(String.self, forKey: .inLanguage)
        self.availableLanguage = try container.decodeIfPresent([String].self, forKey: .availableLanguage) ?? []
        self.modules = try container.decodeIfPresent([CourseModule].self, forKey: .modules) ?? []
        self.aggregateRating = try container.decodeIfPresent(AggregateRating.self, forKey: .aggregateRating)
        self.additionalInfo = try container.decodeIfPresent(AdditionalInfo.self, forKey: .additionalInfo)
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(url.absoluteString, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(description, forKey: .description)
        try container.encodeIfPresent(datePublished, forKey: .datePublished)
        try container.encodeIfPresent(educationalLevel, forKey: .educationalLevel)
        try container.encode(image, forKey: .image)
        try container.encode(about, forKey: .about)
        try container.encode(teaches, forKey: .teaches)
        try container.encodeIfPresent(inLanguage, forKey: .inLanguage)
        try container.encode(availableLanguage, forKey: .availableLanguage)
        try container.encode(modules, forKey: .modules)
        try container.encodeIfPresent(aggregateRating, forKey: .aggregateRating)
        try container.encodeIfPresent(additionalInfo, forKey: .additionalInfo)
    }
    
    // Manual initializer for creating courses programmatically
    public init(id: String, name: String, description: String, datePublished: String? = nil,
         educationalLevel: String? = nil, image: [String] = [], about: [String] = [],
         teaches: [String] = [], inLanguage: String? = nil, availableLanguage: [String] = [],
         modules: [CourseModule] = [], aggregateRating: AggregateRating? = nil,
         additionalInfo: AdditionalInfo? = nil) {
        self.id = id
        self.name = name
        self.description = description
        self.datePublished = datePublished
        self.educationalLevel = educationalLevel
        self.image = image
        self.about = about
        self.teaches = teaches
        self.inLanguage = inLanguage
        self.availableLanguage = availableLanguage
        self.modules = modules
        self.aggregateRating = aggregateRating
        self.additionalInfo = additionalInfo
    }
}
