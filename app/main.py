#!/usr/bin/env python3
import sys
import os
import argparse
from config.settings import WEBDRIVER_PROFILE_FOLDER_NAME, BASE_URL_PARTNERS

# Ensure app modules can be imported
# Add 'app' directory to sys.path so we can import 'models' directly
sys.path.append(os.path.join(os.getcwd(), 'app'))

from models.course import Course
from models.path import Path
from models.paths import Paths
from models.courses import Courses
from models.labs import Labs
from services.launch_browser import launch_browser

def cmd_course(args):
    """Handle course command"""
    course_id = args.id
    print(f"Processing course {course_id}...")
    
    # Logic adapted from scraper.py
    
    # Launch browser for authenticated access
    # We use headless=False to allow user to see/login if needed
    # Use persistent profile to share login state
    driver = launch_browser(headless=False, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)

    try:
        course = Course(id=course_id, driver=driver)
        course.extract_transcript()
    finally:
        driver.quit()

def cmd_path(args):
    """Handle path command"""
    path_id = args.id
    print(f"Processing path {path_id}...")
    
    path = Path(id=path_id)
    path.load_json()
    
    if not path.courses:
        print("Path data not found locally. Fetching...")
        path.fetch_data()
        path.save_json()
        path.save_markdown()
        
        # Update courses collection
        # This part mimics tasks_coordinator logic
        courses_collection = Courses()
        courses_collection.load_json()
        
        for course in path.courses.values():
            c_id = course['id']
            c_name = course['name']
            courses_collection.collection[c_id] = c_name
        courses_collection.save_json()

    driver = None
    if args.all or args.course:
        # Launch browser for authenticated access
        print("\n\033[35mDEBUG: Launching browser for path extraction...\033[0m")
        driver = launch_browser(headless=False, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)

    try:
        courses_to_extract = []
        
        if args.all:
            print(f"Extracting all courses in path {path.name}...")
            courses_to_extract = list(path.courses.values())
            
        elif args.course:
            course_ids = [cid.strip() for cid in args.course.split(',')]
            print(f"Extracting courses: {course_ids} in path {path.name}...")
            
            for cid in course_ids:
                # Find course data in path.courses (values are dicts with id, name)
                # We need to find the course dict that matches the id
                found = False
                for course_data in path.courses.values():
                    if str(course_data['id']) == cid:
                         courses_to_extract.append(course_data)
                         found = True
                         break
                
                if not found:
                    print(f"\033[33m[Warning] Course {cid} not found in path {path_id}.\033[0m")

        if courses_to_extract:
            courses_collection = Courses()
            courses_collection.load_json()
            
            for course_data in courses_to_extract:
                c_id = course_data['id']
                c_name = course_data['name']
                print(f"\n--- Processing Course: {c_name} ({c_id}) ---")
                
                # Pass driver to course instance
                course_instance = Course(id=c_id, name=c_name, driver=driver)
                course_instance.extract_transcript()
                
                courses_collection.collection[c_id] = c_name
                courses_collection.save_json()
        else:
            if not args.all and not args.course:
                path.courses_list()

    finally:
        if driver:
            print("Closing browser...")
            driver.quit()

def cmd_list(args):
    """Handle list command"""
    
    # Determine type
    if args.courses:
        target_class = Courses
        label = "courses"
    elif args.labs:
        target_class = Labs
        label = "labs"
    else:
        # Default to paths or if args.paths is set
        target_class = Path # Wait, Path is single, Paths is collection. 
        # Typo in imports? from models.paths import Paths
        # In main.py:
        # from models.path import Path
        # from models.paths import Paths
        # So it should be Paths
        target_class = Paths
        label = "paths"

    print(f"Listing all {label}...")
    
    # Instantiate
    collection = target_class()
    collection.load_json()
    
    # Fetch if empty (only for Paths currently as others don't have list fetch implemented)
    if not collection.collection:
        print(f"No {label} found locally.")
        if label == 'paths':
             print("Fetching...")
             collection.fetch_paths()
        else:
             print("Please fetch paths first or use 'python main.py path <id> --all' to populate courses/labs.")
             return

    # Determine sort
    sort_by = 'id' if args.id else 'name'
    
    collection.print_list(sort_by=sort_by)

def cmd_fetch(args):
    """Handle fetch command"""
    force = args.force

    fetch_paths = args.paths or args.all
    fetch_courses = args.courses or args.all
    fetch_labs = args.labs or args.all
    
    # Default to fetching paths if no specific type is selected
    if not (fetch_paths or fetch_courses or fetch_labs):
        print("No type specified. Defaulting to fetching paths...")
        fetch_paths = True

    if fetch_paths:
        print("\n--- Fetching Paths ---")
        paths = Paths()
        paths.load_json()
        if not paths.name:
            paths.name = "Paths Collection"
        
        # Ensure URL is up to date (fix double slash if present in old JSON)
        from config.settings import BASE_URL_PATHS
        paths.url = BASE_URL_PATHS
        
        if paths.fetch_paths(force=force):
             print("Paths list updated.")
        else:
             print("Paths list fetch skipped or failed.")
        
        # Always save markdown index
        paths.write_md()
        print(f"Paths markdown index saved to {paths._md_path}")

    if fetch_courses:
        print("\n--- Fetching Courses ---")
        courses = Courses()
        courses.load_json()
        if courses.fetch_courses(force=force):
            print("Courses list updated.")
        else:
            print("Courses list fetch skipped or failed.")

    if fetch_labs:
        print("\n--- Fetching Labs ---")
        labs = Labs()
        labs.load_json()
        if labs.fetch_labs(force=force):
            print("Labs list updated.")
        else:
            print("Labs list fetch skipped or failed.")

def cmd_browser(args):
    """Handle browser command"""
    print("\n\033[35mDEBUG: LAUNCHING THE BROWSER...\033[0m\n")
    
    profile = args.profile_folder if args.profile_folder else WEBDRIVER_PROFILE_FOLDER_NAME
    
    driver = launch_browser(profile_folder=profile, headless=False, browser="chrome")
    
    # Open the URL in the default web browser (PARTNERS page usually redirects to login if not logged in)
    driver.get(BASE_URL_PARTNERS)
    print("\n\033[35mDEBUG: BROWSER LAUNCHED.\033[0m")
    print("You can now log in. The script will keep running. Press Ctrl+C to exit and close browser.")
    
    try:
        # Keep the script running so the browser stays open
        # We can also just input() to wait
        input("Press Enter to close the browser and exit...")
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing browser...")
        driver.quit()

def cmd_md(args):
    """Handle md command"""
    toc_only = args.toc
    no_transcript = args.no_transcript
    
    # Check if at least one type is provided
    if not (args.course or args.path or args.lab):
        print("Please specify at least one item type: --course, --path, or --lab.")
        return

    # Process Courses
    if args.course:
        course_ids = [cid.strip() for cid in args.course.split(',') if cid.strip()]
        for cid in course_ids:
            print(f"Generating markdown for Course {cid}...")
            course = Course(id=cid)
            course.load_json()
            if not course.name: # basic check if loaded
                 print(f"Course {cid} data not found. Please fetch/extract first.")
                 continue
            course.save_markdown(toc_only=toc_only, no_transcript=no_transcript)
            print(f"Markdown saved to {course._md_path}")

    # Process Paths
    if args.path:
        path_ids = [pid.strip() for pid in args.path.split(',') if pid.strip()]
        for pid in path_ids:
            print(f"Generating markdown for Path {pid}...")
            path = Path(id=pid)
            path.load_json()
            if not path.name:
                 print(f"Path {pid} data not found. Please fetch first.")
                 continue
            path.save_markdown(toc_only=toc_only)
            print(f"Markdown saved to {path._md_path}")

    # Process Labs
    if args.lab:
        lab_ids = [lid.strip() for lid in args.lab.split(',') if lid.strip()]
        for lid in lab_ids:
            print(f"Generating markdown for Lab {lid}...")
            lab = Lab(id=lid)
            lab.load_json()
             # Lab might not be fully implemented yet, but we support the structure
            if not lab.name:
                 print(f"Lab {lid} data not found.")
                 continue
            lab.save_markdown(toc_only=toc_only)
            print(f"Markdown saved to {lab._md_path}")

def cmd_search(args):
    """Handle search command"""
    from services.database import Database
    
    query = args.query
    search_type = args.type
    field = args.field
    
    db = Database()
    
    # Determine tables to search
    tables = []
    
    # Handle 'topic' and 'module' search types
    if search_type and search_type.lower() in ['topic', 'topics', 't']:
        tables = ['courses']
        field = 'topics'
        print(f"Searching for topic '{query}' in {tables}...")
    elif search_type and search_type.lower() in ['module', 'modules', 'm']:
        tables = ['courses'] 
        field = 'modules'
        print(f"Searching for module '{query}' in {tables}...")
    elif search_type:
        # User specified type: course/path/lab
        # Map to table names: courses/paths/labs
        if search_type.lower() in ['course', 'courses', 'c']:
            tables.append('courses')
        elif search_type.lower() in ['path', 'paths', 'p']:
            tables.append('paths')
        elif search_type.lower() in ['lab', 'labs', 'l']:
            tables.append('labs')
    else:
        # Search all
        tables = ['paths', 'courses', 'labs']
    
    if not field and not tables:
         print(f"Unknown search type: {search_type}")
         return

    if not field:
        print(f"Searching for '{query}' in {tables}...")
    
    total_results = 0
    for table in tables:
        results = db.search(table, query, field)
        if results:
            print(f"\n--- {table} ({len(results)}) ---")
            for res in results:
                # Highlight ID and Name
                res_id = res.get('id', 'N/A')
                res_name = res.get('name', 'N/A')
                print(f"+|-• \033[35m[{res_id:>5} - {res_name:<72}]\033[0m")
            total_results += len(results)
            
    if total_results == 0:
        print("No results found.")

def main():
    parser = argparse.ArgumentParser(description="CloudSkillsBoost Scraper CLI")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Course command
    parser_c = subparsers.add_parser('course', aliases=['c'], help='Extract transcript for a course')
    parser_c.add_argument('id', help='Course ID')
    parser_c.set_defaults(func=cmd_course)

    # Path command
    parser_p = subparsers.add_parser('path', aliases=['p'], help='Process a learning path')
    parser_p.add_argument('id', help='Path ID')
    parser_p.add_argument('--all', '-a', action='store_true', help='Extract all courses in the path')
    parser_p.add_argument('--course', '-c', help='Extract specific course IDs (comma-separated)', default=None)
    parser_p.set_defaults(func=cmd_path)

    # List command
    parser_l = subparsers.add_parser('list', aliases=['l'], help='List all paths, courses, or labs')
    
    # Mutually exclusive group for type
    group_type = parser_l.add_mutually_exclusive_group()
    group_type.add_argument('--paths', '-p', action='store_true', help='List all paths (default)')
    group_type.add_argument('--courses', '-c', action='store_true', help='List all courses')
    group_type.add_argument('--labs', '-l', action='store_true', help='List all labs')
    
    # Mutually exclusive group for sorting
    group_sort = parser_l.add_mutually_exclusive_group()
    group_sort.add_argument('--name', '-n', action='store_true', help='Sort by name (default)')
    group_sort.add_argument('--id', '-i', action='store_true', help='Sort by ID')
    
    parser_l.set_defaults(func=cmd_list)

    # Fetch command
    parser_f = subparsers.add_parser('fetch', aliases=['f'], help='Fetch courses/paths/labs list from remote')
    parser_f.add_argument('--paths', '-p', action='store_true', help='Fetch paths list')
    parser_f.add_argument('--courses', '-c', action='store_true', help='Fetch courses list')
    parser_f.add_argument('--labs', '-l', action='store_true', help='Fetch labs list')
    parser_f.add_argument('--all', '-a', action='store_true', help='Fetch all lists')
    parser_f.add_argument('--force', '-f', action='store_true', help='Force fetch even if local data exists')
    parser_f.set_defaults(func=cmd_fetch)

    # Browser command
    parser_b = subparsers.add_parser('browser', aliases=['b', 'w'], help='Launch browser for manual login')
    parser_b.add_argument('--profile-folder', help='Specific webdriver profile folder', default=None)
    parser_b.set_defaults(func=cmd_browser)

    # MD command
    parser_m = subparsers.add_parser('md', help='Generate markdown output')
    parser_m.add_argument('--course', '-c', help='List of course IDs (comma-separated)', default=None)
    parser_m.add_argument('--lab', '-l', help='List of lab IDs (comma-separated)', default=None)
    parser_m.add_argument('--path', '-p', help='List of path IDs (comma-separated)', default=None)
    parser_m.add_argument('--toc', '-t', action='store_true', help='Table of content only (structure only)')
    parser_m.add_argument('--no-transcript', action='store_true', help='Skip video transcripts (courses only)')
    parser_m.set_defaults(func=cmd_md)

    # Search command
    parser_s = subparsers.add_parser('search', aliases=['s'], help='Search in database')
    parser_s.add_argument('query', help='Search query')
    parser_s.add_argument('--type', '-t', help='Limit search to type (course, path, lab)', default=None)
    parser_s.add_argument('--field', '-f', help='Limit search to specific field', default=None)
    parser_s.set_defaults(func=cmd_search)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute the selected command
    args.func(args)

if __name__ == "__main__":
    main()
