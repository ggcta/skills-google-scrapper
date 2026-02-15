#!/usr/bin/env python3
import sys
import os
import argparse

# Ensure app modules can be imported
# Add 'app' directory to sys.path so we can import 'models' directly
sys.path.append(os.path.join(os.getcwd(), 'app'))

from models.course import Course
from models.path import Path
from models.paths import Paths
from models.courses import Courses

def cmd_course(args):
    """Handle course command"""
    course_id = args.id
    print(f"Processing course {course_id}...")
    
    # Logic adapted from scraper.py
    # We might need to load the course collection first to get the name if not provided,
    # but Course(id=course_id) fetch_data/extract_transcript usually handles it.
    
    course = Course(id=course_id)
    # If the course is in collection, we might want to use that name, but extract_transcript loads json anyway
    course.extract_transcript()

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

    if args.all:
        print(f"Extracting all courses in path {path.name}...")
        courses_collection = Courses()
        courses_collection.load_json()
        
        for course_data in path.courses.values():
            c_id = course_data['id']
            c_name = course_data['name']
            print(f"\n--- Processing Course: {c_name} ({c_id}) ---")
            course_instance = Course(id=c_id, name=c_name)
            course_instance.extract_transcript()
            courses_collection.collection[c_id] = c_name
            courses_collection.save_json()
    else:
        path.courses_list()

def cmd_list(args):
    """Handle list command"""
    print("Listing all paths...")
    paths = Paths()
    # verify if paths.json exists, if not fetch
    paths.load_json()
    if not paths.collection:
        print("No paths found locally. Fetching...")
        paths.fetch_paths()
    
    paths.print_list()

def cmd_fetch(args):
    """Handle fetch command"""
    print("Fetching all courses and paths data...")
    # This seems to correspond to gathering all paths and optionally courses?
    # In interactive mode option 6 is "Fetch data associated with local files" 
    # But user description says "f/fetch courses/paths list"
    
    paths = Paths()
    if paths.fetch_paths():
        print("Paths list updated.")
        paths.print_list()
    else:
        print("Failed to fetch paths.")

def cmd_reload(args):
    """Handle reload command"""
    print("Reloading courses/paths list...")
    # Logic matching Option 9: DEBUG: RELOADING DATA
    paths = Paths()
    if paths.fetch_paths():
         print("Paths List refreshed. Proceeding with courses of each path...")
         paths.save_json()
         paths.write_md()
    else:
         print("Paths List NOT refreshed. Proceeding with courses of each path (using cached)...")

    # Get all courses from all the paths
    courses_collection = Courses()
    courses_collection.load_json()
    
    # We need to iterate over a copy or loaded collection
    # If fetch_paths failed, we use existing collection
    for path_id, path_name in paths.collection.items():
        print(f"+|-• \033[35m[{path_id:>5} - {path_name:<72}]\033[0m")
        path_data = Path(id=path_id, name=path_name)
        path_data.fetch_data()
        
        # Save the path data
        path_data.save_json()
        path_data.save_markdown()
        
        # Add courses from this path to the courses collection
        for course in path_data.courses.values():
            course_id = course['id']
            course_name = course['name']
            courses_collection.collection[course_id] = course_name
            
    courses_collection.save_json()
    print("\n\033[35mCOURSES LIST RELOADED.\033[0m\n")

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
    parser_p.set_defaults(func=cmd_path)

    # List command
    parser_l = subparsers.add_parser('list', aliases=['l'], help='List all paths')
    parser_l.set_defaults(func=cmd_list)

    # Fetch command
    parser_f = subparsers.add_parser('fetch', aliases=['f'], help='Fetch courses/paths list')
    parser_f.set_defaults(func=cmd_fetch)

    # Reload command
    parser_r = subparsers.add_parser('reload', aliases=['r'], help='Reload courses/paths list')
    parser_r.set_defaults(func=cmd_reload)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute the selected command
    args.func(args)

if __name__ == "__main__":
    main()
