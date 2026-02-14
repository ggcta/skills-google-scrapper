import XCTest
@testable import CSBHelperCore

final class ModelTests: XCTestCase {
    
    func testCourseModel() throws {
        // Test Course creation and properties
        let course = Course(
            id: "60",
            name: "Google Cloud Fundamentals: Core Infrastructure",
            description: "Introduction to Google Cloud concepts",
            datePublished: "2025-01-23",
            educationalLevel: "Beginner",
            about: ["Cloud Computing", "Infrastructure"],
            teaches: ["Identify Google Cloud products", "Create basic infrastructure"]
        )
        
        XCTAssertEqual(course.id, "60")
        XCTAssertEqual(course.name, "Google Cloud Fundamentals: Core Infrastructure")
        XCTAssertEqual(course.type, .course)
        XCTAssertEqual(course.topics, ["Cloud Computing", "Infrastructure"])
        XCTAssertEqual(course.objectives, ["Identify Google Cloud products", "Create basic infrastructure"])
        XCTAssertTrue(course.url.absoluteString.contains("course_templates/60"))
    }
    
    func testPathModel() throws {
        // Test Path creation and properties
        let pathCourse = PathCourse(
            id: "60",
            type: "Course",
            name: "Test Course",
            description: "Test Description",
            url: URL(string: "https://example.com/60")!
        )
        
        let path = Path(
            id: "36",
            name: "Cloud Developer Learning Path",
            description: "A comprehensive learning path",
            datePublished: "2024-11-25",
            hasPart: [pathCourse]
        )
        
        XCTAssertEqual(path.id, "36")
        XCTAssertEqual(path.name, "Cloud Developer Learning Path")
        XCTAssertEqual(path.type, .path)
        XCTAssertEqual(path.courses.count, 1)
        XCTAssertEqual(path.courses.first?.id, "60")
        XCTAssertTrue(path.url.absoluteString.contains("paths/36"))
    }
    
    func testLabModel() throws {
        // Test Lab creation and properties
        let lab = Lab(
            id: "1119",
            name: "Getting Started with Cloud Marketplace",
            description: "Learn to use Cloud Marketplace",
            datePublished: "2025-04-03",
            steps: [
                "1": "Overview",
                "2": "Objectives", 
                "3": "Task 1: Sign in to Console",
                "4": "Task 2: Deploy LAMP stack"
            ]
        )
        
        XCTAssertEqual(lab.id, "1119")
        XCTAssertEqual(lab.name, "Getting Started with Cloud Marketplace")
        XCTAssertEqual(lab.type, .lab)
        XCTAssertEqual(lab.steps.count, 4)
        XCTAssertTrue(lab.url.absoluteString.contains("catalog_lab/1119"))
        
        // Test ordered steps
        let orderedSteps = lab.orderedSteps
        XCTAssertEqual(orderedSteps.count, 4)
        XCTAssertEqual(orderedSteps.first?.key, "1")
        XCTAssertEqual(orderedSteps.first?.value, "Overview")
    }
    
    func testEntityComparable() throws {
        let course1 = Course(id: "1", name: "A Course", description: "Description")
        let course2 = Course(id: "2", name: "B Course", description: "Description")
        let course3 = Course(id: "3", name: "A Course", description: "Description")
        
        // Test sorting by name, then by id
        XCTAssertTrue(course1 < course2) // "A Course" < "B Course"
        XCTAssertTrue(course1 < course3) // Same name, "1" < "3"
        XCTAssertTrue(course3 < course2) // "A Course" < "B Course"
    }
    
    func testEntityHashable() throws {
        let course1 = Course(id: "60", name: "Test Course", description: "Description")
        let course2 = Course(id: "60", name: "Test Course", description: "Description")
        let course3 = Course(id: "61", name: "Test Course", description: "Description")
        
        // Same id and type should be equal
        XCTAssertEqual(course1, course2)
        XCTAssertNotEqual(course1, course3)
        
        // Should be hashable
        let courseSet: Set<Course> = [course1, course2, course3]
        XCTAssertEqual(courseSet.count, 2) // course1 and course2 are the same
    }
    
    func testEntityCollection() throws {
        let collection = EntityCollection<Course>(name: "Test Courses")
        
        let course1 = Course(id: "1", name: "Course A", description: "Description A")
        let course2 = Course(id: "2", name: "Course B", description: "Description B")
        
        collection.addEntity(course1)
        collection.addEntity(course2)
        
        XCTAssertEqual(collection.count, 2)
        XCTAssertEqual(collection.entity(withId: "1")?.name, "Course A")
        XCTAssertNil(collection.entity(withId: "999"))
        
        // Test search
        let searchResults = collection.search(query: "Course A")
        XCTAssertEqual(searchResults.count, 1)
        XCTAssertEqual(searchResults.first?.id, "1")
        
        // Test sorted entities
        let sortedEntities = collection.allEntities
        XCTAssertEqual(sortedEntities.first?.name, "Course A") // Should be sorted by name
    }
    
    func testTopicCollection() throws {
        let courseCollection = CourseCollection(name: "Courses")
        let topicCollection = TopicCollection()
        
        let course1 = Course(id: "1", name: "Course 1", description: "Description", about: ["Cloud", "Computing"])
        let course2 = Course(id: "2", name: "Course 2", description: "Description", about: ["Cloud", "Storage"])
        
        courseCollection.addEntity(course1)
        courseCollection.addEntity(course2)
        
        topicCollection.extractTopics(from: courseCollection)
        
        XCTAssertTrue(topicCollection.allTopics.contains("Cloud"))
        XCTAssertTrue(topicCollection.allTopics.contains("Computing"))
        XCTAssertTrue(topicCollection.allTopics.contains("Storage"))
        
        let cloudCourses = topicCollection.courses(for: "Cloud")
        XCTAssertEqual(cloudCourses.count, 2)
        
        let computingCourses = topicCollection.courses(for: "Computing")
        XCTAssertEqual(computingCourses.count, 1)
        XCTAssertEqual(computingCourses.first?.id, "1")
    }
}
