from typing import Dict
from config.settings import BASE_URL
from utils.utils import util_replace_quote_marks, util_replace_special_chars  # Correct import

class MDHelper:

    @staticmethod
    def md_helper_path(data: Dict) -> str:
        markdown = []

        # Add front matter
        front_matter_lines = ["---"]
        for key, value in data.items():
            if key == "description" or key == "courses" or key == 'steps':
                continue

            if key == "topics" and data['topics']:
                front_matter_lines.append(f"{key}:")
                for topic in value:
                    front_matter_lines.append(f"- {topic}")
                continue

            if key == "name":
                front_matter_lines.append(f"{key}: '{value}'")
                continue

            front_matter_lines.append(f"{key}: {value}")
        front_matter_lines.append("---")
        markdown.append("\n".join(front_matter_lines))

        # The # main heading
        markdown.append(f"# [{data['name']}]({data['url']})")

        # Add description
        if "description" in data:
            markdown.append(f"{data['description']}")

        # Add courses belong to a Path
        if data["type"] == 'Path' and "courses" in data:
            markdown.append("## Courses & Progress")
            course_list = []
            for course_id, course in data["courses"].items():
                course_md_name = f"{util_replace_special_chars(course['name'])}.md"
                course_list.append(f"- [ ] [{course['name']} ({course_id})](../courses/{course_md_name})")
            markdown.append("\n".join(course_list))
        
        if data['type'] == 'Lab' and 'steps' in data:
            for step_number, step_text in data['steps'].items():
                markdown.append(f"## Step {step_number}: {step_text}")

        return "\n\n".join(markdown) + "\n"

    @staticmethod
    def md_helper_lab(data: Dict) -> str:
        markdown = []

        # Add front matter
        front_matter_lines = ["---"]
        for key, value in data.items():
            if key == "description" or key == 'steps':
                continue

            if key == "name":
                front_matter_lines.append(f"{key}: '{value}'")
                continue

            front_matter_lines.append(f"{key}: {value}")
        front_matter_lines.append("---")
        markdown.append("\n".join(front_matter_lines))

        # The # main heading
        markdown.append(f"# [{data['name']}]({data['url']})")

        # Add description
        if "description" in data:
            markdown.append(f"{data['description']}")
        
        # Add steps belong to a Lab, each step is a sub-heading at level 2
        if data['type'] == 'Lab' and 'steps' in data:
            for step_number, step_text in data['steps'].items():
                markdown.append(f"## Step {step_number}: {step_text}")

        return "\n\n".join(markdown) + "\n"

    @staticmethod
    def md_helper_course(data: Dict) -> str:
        markdown = []

        # Add front matter
        front_matter_lines = ["---"]
        for key, value in data.items():
            if key == "description" or key == "objectives" or key == "modules":
                continue

            if key == "topics" and data['topics']:
                front_matter_lines.append(f"{key}:")
                for topic in value:
                    front_matter_lines.append(f"- {topic}")
                continue

            if key == "name":
                front_matter_lines.append(f"{key}: '{value}'")
                continue

            front_matter_lines.append(f"{key}: {value}")
        front_matter_lines.append("---")
        markdown.append("\n".join(front_matter_lines))
        # End of front matter

        # The # Heading
        markdown.append(f"# [{data['name']}]({data['url']})")

        # Add description
        if "description" in data and data.get('description') is not None:
            markdown.append("**Description:**")
            markdown.append(f"{data['description']}")

        # Add objectives, \n between each item
        if "objectives" in data and len(data.get("objectives")) > 0:
            markdown.append("**Objectives:**")
            objective_list = []
            for objective in data['objectives']:
                objective_list.append(f"- {objective}")
            markdown.append("\n".join(objective_list))
            # markdown.append(data['objectives'])
        # End of objectives

        # If modules in a course
        if "modules" in data:
            modules = data['modules']
            for module in modules:
                # Each module is a level 2 heading
                markdown.append(f"## {module['title']}")

                if module['description']:
                    markdown.append(f"{module['description'].strip('<p>').strip('</p>')}")

                for step in module['steps']:
                    for activity in step['activities']:
                        activity_title = activity['title']
                        activity_type = activity['type']
                        activity_href = activity['href']
                        # Each activity is a level 3 heading
                        markdown.append(f"### {activity_type.title()} - [{activity_title}]({BASE_URL}{activity_href})")

                        # If it's a video, let put a YouTube video for it here.
                        if activity_type == 'video':
                            markdown.append(f"- [YouTube: {activity_title}](https://www.youtube.com/watch?v={activity['videoId']})")
                            markdown.append(activity['transcript'])

                        # If it's a video, let put a checkbox here for a completion status
                        elif activity_type == 'lab':
                            markdown.append(activity.get('description'))
                            lab_md_name = f"{util_replace_special_chars(activity_title)}.md"
                            if activity['isComplete'] is False:
                                markdown.append(f"- [ ] [{activity_title}](../labs/{lab_md_name})")
                            else:
                                markdown.append(f"- [x] [{activity_title}](../labs/{lab_md_name})")

                        # If it's a quiz, presents all the quiz and answer here
                        elif activity_type == 'quiz':
                            if activity.get('quizItems'):
                                quizItems = activity['quizItems']
                                quiz_number = 1
                                for question in quizItems:
                                    quiz_list = []
                                    quiz_stem = question.get("stem").replace("<p>", "").replace("</p>", "")
                                    quiz_stem = quiz_stem.replace('\n\n', '')
                                    # Each quiz is a level 4 heading
                                    markdown.append(f"#### Quiz {quiz_number}.")
                                    # Put into a callout format for Obsidian or Typora
                                    quiz_list.append(f"> [!important]")
                                    quiz_list.append(f"> **{util_replace_quote_marks(quiz_stem)}**")
                                    quiz_list.append(">")

                                    if question.get("options"):
                                        for option in question.get("options"):
                                            quiz_list.append(f"> - [ ] {util_replace_quote_marks(option.get('title'))}")
                                    else:
                                        continue

                                    markdown.append("\n".join(quiz_list))
                                    quiz_number += 1

                        # If it's a link, let put a link here
                        elif activity_type == 'link':
                            markdown.append(f"- [{activity_title}]({activity['link']})")

        # End of modules

        # Ensure an empty line between each section, and an extra empty line at the end of the file
        return "\n\n".join(markdown) + "\n"
