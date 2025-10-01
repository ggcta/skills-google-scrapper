# CSB Helper - Application Information

## Overview
**CSB Helper** (Cloud Skills Boost Helper) is a comprehensive web scraping and content management application designed to extract, organize, and present educational content from Google Cloud Skills Boost platform. The application serves as both a scraper for automated content extraction and a web-based interface for browsing and managing the extracted content.

## Core Purpose
The application addresses the need to:
- Extract course content, transcripts, and quiz data from Google Cloud Skills Boost
- Convert web-based learning materials into structured Markdown files
- Build a Personal Knowledge Base (compatible with tools like Obsidian)
- Provide a searchable web interface for browsing extracted content
- Automate the "Mark Complete Video" functionality

## Architecture

### Technology Stack
- **Backend**: Python Flask web framework
- **Web Scraping**: Selenium WebDriver + BeautifulSoup4
- **Data Storage**: JSON files for structured data
- **Output Format**: Markdown files for knowledge management
- **Frontend**: HTML templates with Materialize CSS framework
- **Containerization**: Docker support with Alpine Linux base

### Key Components

#### 1. Web Application (`app/app.py`)
- Flask-based web server running on port 8080
- RESTful routes for courses, paths, labs, and topics
- Real-time search functionality
- Thread-safe topic extraction with periodic refresh
- Breadcrumb navigation system

#### 2. Scraper Engine (`app/scraper.py`)
- Command-line interface for content extraction
- Selenium-based browser automation
- Supports both individual and batch processing
- Interactive task coordinator for user selections

#### 3. Data Models (`app/models/`)
- **BaseEntity**: Abstract base class for all content types
- **Course**: Individual course data and transcript extraction
- **Path**: Learning path with multiple courses
- **Lab**: Hands-on laboratory exercises
- **Collections**: Aggregated data management (Courses, Paths, Labs, Topics)

#### 4. Configuration (`app/config/settings.py`)
- Centralized configuration management
- URL patterns for different content types
- File path management for data and output
- WebDriver settings and CSS selectors

### Data Flow
1. **Extraction Phase**: Scraper navigates CSB website using Selenium
2. **Processing Phase**: Content parsed with BeautifulSoup and structured into JSON
3. **Storage Phase**: Data saved to `data/` folder as JSON files
4. **Output Phase**: Markdown files generated in `csbmdvault/` folder
5. **Presentation Phase**: Web interface loads JSON data for browsing

## Key Features

### Content Extraction
- **Courses**: Full course content including modules, videos, and quizzes
- **Transcripts**: Automated video transcript extraction
- **Paths**: Learning path structure with course relationships
- **Labs**: Hands-on exercise content and instructions
- **Topics**: Automatic topic categorization from course metadata

### Web Interface
- **Search**: Real-time search across all content types
- **Navigation**: Hierarchical browsing by paths, courses, labs, topics
- **Responsive Design**: Mobile-friendly interface using Materialize
- **Dynamic Content**: Auto-refreshing topic extraction every 5 minutes

### Data Management
- **JSON Storage**: Structured data persistence
- **Markdown Export**: Knowledge base compatible output
- **File Organization**: Systematic folder structure
- **Data Validation**: Schema-based content validation

## File Structure
```
csbhelper/
├── app/                    # Main application code
│   ├── config/            # Configuration settings
│   ├── models/            # Data models and entities
│   ├── services/          # Business logic services
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── utils/             # Utility functions
├── data/                  # JSON data storage
├── csbmdvault/           # Markdown output files
├── database/             # Schema definitions and examples
├── docs/                 # Documentation
├── .webdriver_profiles/  # Browser profiles for automation
└── requirements.txt      # Python dependencies
```

## Usage Modes

### 1. Scraper Mode (Command Line)
```bash
python scraper.py
```
- Interactive menu for content selection
- Batch processing capabilities
- Hidden menu options (99: fetch all paths, 5: generate prompts)

### 2. Web Interface Mode
```bash
python app.py
```
- Browse extracted content via web interface
- Search functionality across all content types
- Real-time content updates

### 3. Docker Deployment
```bash
docker build -t csbhelper .
docker run -dp '8080:8080' csbhelper
```

## Current Status & Limitations

### Implemented Features
- ✅ Full content extraction pipeline
- ✅ Web-based browsing interface
- ✅ Search functionality
- ✅ Markdown export for knowledge management
- ✅ Docker containerization
- ✅ Topic categorization

### Known TODOs
- Command-line interface improvements
- LLM integration for content summarization
- Partner portal support (partner.cloudskillsboost.google)
- GCS bucket synchronization
- Async processing for performance
- Quiz answer marking functionality

## Dependencies
- **requests**: HTTP client for API calls
- **beautifulsoup4**: HTML parsing
- **selenium**: Browser automation
- **html2text**: HTML to Markdown conversion
- **flask**: Web framework
- **gunicorn**: Production WSGI server

## Target Use Cases
1. **Personal Learning**: Extract courses for offline study
2. **Knowledge Management**: Build searchable learning repositories
3. **Content Analysis**: Analyze course structures and topics
4. **Automation**: Bulk processing of learning materials
5. **Research**: Academic analysis of cloud training content

This application represents a comprehensive solution for managing and organizing Google Cloud Skills Boost educational content, bridging the gap between online learning platforms and personal knowledge management systems.
