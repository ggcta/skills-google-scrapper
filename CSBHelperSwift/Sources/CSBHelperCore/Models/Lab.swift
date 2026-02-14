import Foundation

/// Represents a lab entity from Google Cloud Skills Boost
public struct Lab: BaseEntity {
    public var id: String
    public var name: String
    public var description: String
    public var datePublished: String?
    public let image: [String]
    public let inLanguage: String?
    public let steps: [String: String]
    
    public var type: EntityType { .lab }
    
    enum CodingKeys: String, CodingKey {
        case id = "@id"
        case name, description, datePublished, image, inLanguage, steps
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
        self.steps = try container.decodeIfPresent([String: String].self, forKey: .steps) ?? [:]
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(url.absoluteString, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(description, forKey: .description)
        try container.encodeIfPresent(datePublished, forKey: .datePublished)
        try container.encode(image, forKey: .image)
        try container.encodeIfPresent(inLanguage, forKey: .inLanguage)
        try container.encode(steps, forKey: .steps)
    }
    
    // Manual initializer for creating labs programmatically
    public init(id: String, name: String, description: String, datePublished: String? = nil,
         image: [String] = [], inLanguage: String? = nil, steps: [String: String] = [:]) {
        self.id = id
        self.name = name
        self.description = description
        self.datePublished = datePublished
        self.image = image
        self.inLanguage = inLanguage
        self.steps = steps
    }
    
    /// Get ordered steps as an array of tuples
    public var orderedSteps: [(key: String, value: String)] {
        steps.sorted { first, second in
            // Try to sort numerically if possible, otherwise alphabetically
            if let firstNum = Int(first.key), let secondNum = Int(second.key) {
                return firstNum < secondNum
            }
            return first.key < second.key
        }
    }
}
