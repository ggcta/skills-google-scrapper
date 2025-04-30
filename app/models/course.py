import re
from pathlib import Path as PathlibPath
from models.base_entity import BaseEntity
from models.labs import Labs
from models.lab import Lab
from selenium.common import NoSuchElementException
import json
import html
import requests
from bs4 import BeautifulSoup
from config.settings import BASE_URL, QL_IFRAME
from utils.utils import util_replace_quote_marks, util_replace_special_chars, util_strip_html_tags


# Constants for the extraction of the course data
COURSE_LD_JSON = "script[type='application/ld+json']"
COURSE_META_DESCRIPTION = "meta[name='description']"
COURSE_OUTLINE = "ql-course-outline"
QL_YOUTUBE_VIDEO = "ql-youtube-video"
LAB_REVIEW_LAB_ID = "#lab_review_lab_id"
LAB_CONTENT_OUTLINE = "ul.lab-content__outline"
QL_QUIZ = "ql-quiz"
XPATH_START_BUTTON = "//a[@class='start-button button button--positive']"
XPATH_QUIZ = "//ql-quiz"
QUIZ_VERSION = "quizVersion"
QUIZ_ITEMS = "quizItems"
LINK_URL_A_TAG = "ql-card.document-link a"


class Course(BaseEntity):
    """
    Class representing a course entity.\n
    Inherits from BaseEntity.\n
    This class is responsible for extracting course data from the Cloud Skills Boost platform.
    """
    def __init__(self,
                 id: str,
                 name: str = None,
                 description: str = None,
                 datePublished: str = None,
                 objectives: list = None,
                 topics: list = None,
                 modules: list = None):
        super().__init__(id,
                         name,
                         description)
        self.datePublished = datePublished or ""
        self.objectives = objectives or []
        self.topics = topics or []
        self.modules = modules or []

    def extract_transcript(self) -> None:
        """
        Main method to extract the transcript of a course.
        """
        print("\nTranscript Extracting is starting...\n")

        # Load the course data from JSON
        self.load_json()

        # Fetch and parse the course page
        course_html = self.fetch_course_page()
        if not course_html:
            return

        # Extract course metadata
        if not self.extract_course_metadata(course_html):
            self.save_markdown()
            return

        # Extract course outline
        if not self.extract_course_outline(course_html):
            return

        # Process course modules
        self.process_modules()

        # Save the course data
        self.save_json()
        self.save_markdown()

        print(f"(extract_transcript) \033[34m•-• COMPLETED: {self.id} - {self.name.upper()}\033[0m\n")

    def fetch_course_page(self):
        """
        Fetch the course page and return the parsed HTML.
        """
        try:
            response = requests.get(self.url, timeout=20)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as error:
            print(f"(extract_transcript) Error: Unable to load the course page. {error}")
            return None

    def extract_course_metadata(self, course_html):
        """
        Extract course metadata such as description, objectives, and topics.
        """
        try:
            course_ld_json_element = course_html.select_one(COURSE_LD_JSON)
            meta_element = course_html.select_one(COURSE_META_DESCRIPTION)

            if not course_ld_json_element or not meta_element:
                raise NoSuchElementException("(extract_course_metadata) meta_element not found.")

            course_ld_json_text = course_ld_json_element.string
            course_description = html.unescape(meta_element['content'])
            course_description = util_strip_html_tags(course_description)
            course_description = re.sub(r'\s{2,}', '\n\n', course_description)
            course_description = util_replace_quote_marks(course_description)

            course_objectives_json = json.loads(course_ld_json_text)
            datePublished = course_objectives_json.get('datePublished')

            # If the course has the same datePublished, return False and not continue.
            if datePublished == self.datePublished:
                print(f"(extract_course_metadata) Course {self.id} already extracted. datePublished: {datePublished}\n")
                return False

            self.id = course_objectives_json.get('@id').split('/')[-1]
            self.name = course_objectives_json.get('name').strip()
            self.description = course_description
            self.datePublished = course_objectives_json.get('datePublished')
            self.topics = course_objectives_json.get('about')
            self.objectives = course_objectives_json.get('teaches')

            return True
        except Exception as error:
            print(f"(extract_course_metadata) Error: {error}")
            return False

    def extract_course_outline(self, course_html):
        """
        Extract the course outline and modules.
        """
        try:
            course_outline_element = course_html.select_one(COURSE_OUTLINE)
            if not course_outline_element:
                raise NoSuchElementException("(extract_course_outline) ql-course-outline is not found.")

            self.modules = json.loads(course_outline_element["modules"])
            return True
        except Exception as error:
            print(f"(extract_course_outline) Error: {error}")
            return False

    def process_modules(self):
        """
        Process each module in the course.
        """
        for module in self.modules:
            module_title = module["title"].strip()
            print(f"(process_modules) \033[34m• MODULE: {module_title}\033[0m")

            if module.get("description"):
                module['description'] = self.clean_text(module.get("description", ""))

            for step in module['steps']:
                self.process_step(step)

    def process_step(self, step):
        """
        Process each step in a module.
        """
        for activity in step['activities']:
            activity_type = activity['type']
            activity_id = activity['id']
            activity_title = activity['title'].strip()
            activity_full_url = f"{BASE_URL}{activity['href']}"

            if activity_type == "video":
                self.process_video(activity, activity_full_url)
            elif activity_type == "lab":
                self.process_lab(activity, activity_full_url)
            elif activity_type == "quiz":
                self.process_quiz(activity, activity_full_url)
            elif activity_type == "link":
                self.process_link(activity, activity_full_url)

    def process_video(self, activity, url):
        """
        Process a video activity.
        """
        print(f"(process_video) •-> Vid: {activity['id']:>6} - {activity['title']}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            video_html = BeautifulSoup(response.text, "html.parser")

            video_element = video_html.select_one(QL_YOUTUBE_VIDEO)
            transcript_data = video_element["transcript"]
            video_id = video_element["videoid"]

            activity['videoId'] = video_id
            if transcript_data:
                transcript_json = json.loads(transcript_data)
                activity['transcript'] = " ".join([item['text'] for item in transcript_json])
            else:
                activity['transcript'] = '(No video transcript.)'

            print(f"(process_video) •-• [+]")
        except Exception as error:
            print(f"(process_video) Error: {error}")

    def process_lab(self, activity, url):
        """
        Process a lab activity.
        """
        print(f"(process_lab) •-> Lab: {activity['id']:>6} - {activity['title']}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            lab_page_html = BeautifulSoup(response.text, "html.parser")

            lab_review_lab_id_element = lab_page_html.select_one(LAB_REVIEW_LAB_ID)
            lab_content_outline_element = lab_page_html.select_one(LAB_CONTENT_OUTLINE)

            lab_id = lab_review_lab_id_element["value"].strip()

            # Create a Lab instance for the lab_id
            lab = Lab(
                id=lab_id
            )
            # Load the lab data from JSON even it's empty
            lab.load_json()

            # If the lab.name does exist, that means the lab has been extracted already.
            if lab.name:
                print(f"(process_lab) •-• [+] Existed: {lab.id} - {lab.name}")
                return False

            # If the lab.name doesn't exist, the lab is new, continue.
            lab_steps = {}
            if lab_content_outline_element:
                for a_tag in lab_content_outline_element.find_all('a'):
                    step = a_tag['href'].strip('#step')
                    text = a_tag.text
                    lab_steps[step] = text

            # Set the lab's attributes.
            lab.name = activity['title'].strip()
            lab.description = activity.get('description', '')
            lab.steps = lab_steps

            # Save the lab to files.
            lab.save_json()
            lab.save_markdown()

            # Add the lab to the Labs Collection
            labs_collection = Labs(name='Labs Collection')
            labs_collection.load_json()
            labs_collection.collection[lab_id] = lab.name
            labs_collection.save_json()

            print(f"(process_lab) •-• [+]")
        except Exception as error:
            print(f"(process_lab) Error: {error}")

    def process_quiz(self, activity, url):
        """
        Process a quiz activity.
        """
        # TODO: Extract Quiz that need to press the 'Start quiz' button, ie. course/201
        print(f"(process_quiz) •-> Qui: {activity['id']:>6} - {activity['title']}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            quiz_page_html = BeautifulSoup(response.text, "html.parser")

            quiz_element = quiz_page_html.select_one(QL_QUIZ)
            if quiz_element:
                quiz_question_data = quiz_element[QUIZ_VERSION.lower()]
                quiz_question_json = json.loads(quiz_question_data)
                activity[QUIZ_ITEMS] = quiz_question_json.get(QUIZ_ITEMS)

            print(f"(process_quiz) •-• [+]")
        except Exception as error:
            print(f"(process_quiz) Error: {error}")

    def process_link(self, activity, url):
        """
        Process a link activity.
        """
        print(f"(process_link) •-> Lnk: {activity['id']:>6} - {activity['title']}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            link_page_html = BeautifulSoup(response.text, "html.parser")

            link_url_a_tag = link_page_html.select_one(LINK_URL_A_TAG)
            if link_url_a_tag:
                activity['link'] = link_url_a_tag['href']
            else:
                iframe_tag = link_page_html.select_one(QL_IFRAME)
                activity['link'] = iframe_tag['src'] if iframe_tag else None

            print(f"(process_link) •-• [+]")
        except Exception as error:
            print(f"(process_link) Error: {error}")

    def generate_prompt(self):
        """
        Generate the prompts for videos from their transcripts.\n
        The prompt data will be saved to a JSON file.
        """
        # Proceed only if the course's json file does exist.
        if not self._json_path.exists():
            print("Sorry, the course json not found. Please fetch the course first.")
            return

        # Load the course data from the JSON file
        self.load_json()

        # The data structure will be simplified from the original course's json.
        course = {
            "id": self.id,
            "title": f'{self.name}'
            }

        modules = {}
        for module in self.modules:
            module_title = module["title"].strip()
            steps = {}
            for step in module['steps']:
                step_id = step['id']
                activities = {}
                for activity in step['activities']:
                    activity_title = activity['title']
                    activity_id = activity['id']
                    if activity['type'] == 'video':
                        this_video = {}
                        this_video['title'] = activity_title

                        # Prompt for the video in a simple format
                        # topic: {course.title}, {module.title}; title: {activity.title}; transcript: {activity.transcript}
                        video_prompt = []
                        video_prompt.append(f"topic: {self.name}, {module_title}")
                        video_prompt.append(f"title: {activity['title'].strip()}")
                        video_prompt.append(f"transcript: {activity.get('transcript', '(No transcript available)')}")
                        this_video['prompt'] = '; '.join(video_prompt)

                        activities[activity_id] = this_video
                steps[step_id] = activities
            modules[module_title] = steps

        course['modules'] = modules

        # JSON file name for the prompt data, a bit different from the course's json file
        json_name = f'{self.id}-prompt.json'
        json_path = PathlibPath(self._json_path.parent / json_name)

        # Save the prompt data to a JSON file, overwrite if exists
        with open(json_path, 'w', encoding='utf-8', newline='\n') as jsonfile:
            json.dump(course, jsonfile, ensure_ascii=False, indent=2)

    def generate_markdown(self):
        """
        Generate the Markdown data for the course.
        """
        markdown = []
        markdown.append(self.generate_front_matter())

        markdown.append(f"# [{self.name}]({self.url})")

        if hasattr(self, 'description') and self.description:
            markdown.append("**Description:**")
            markdown.append(f"{self.description}")

        if hasattr(self, 'objectives') and self.objectives:
            markdown.append("**Objectives:**")
            objective_list = []
            for objective in self.objectives:
                objective_list.append(f"- {objective}")
            markdown.append("\n".join(objective_list))

        if hasattr(self, 'modules') and self.modules:
            for module in self.modules:
                module_title = module["title"].strip()
                markdown.append(f"## {module_title}")
                if module.get("description"):
                    module['description'] = self.clean_text(module.get("description", ""))
                    markdown.append(f"{module['description']}")

                for step in module.get("steps", []):
                    for activity in step.get("activities", []):
                        activity_title = activity['title'].strip()
                        activity_type = activity['type']
                        activity_href = activity['href']

                        markdown.append(f"### {activity_type.title()} - [{activity_title}]({BASE_URL}{activity_href if activity_href else ''})")

                        if activity_type == 'video':
                            markdown.append(f"- [YouTube: {activity_title}](https://www.youtube.com/watch?v={activity['videoId']})")
                            markdown.append(f"{activity.get('transcript', '(No transcript available)')}")

                        elif activity_type == 'lab':
                            markdown.append(activity.get('description'))
                            lab_md_name = f"{util_replace_special_chars(activity_title)}.md"
                            if activity['isComplete'] is False:
                                markdown.append(f"- [ ] [{activity_title}](../labs/{lab_md_name})")
                            else:
                                markdown.append(f"- [x] [{activity_title}](../labs/{lab_md_name})")

                        elif activity_type == 'quiz':
                            if activity.get('quizItems'):
                                quizItems = activity.get('quizItems')
                                quiz_number = 1
                                for quizItem in quizItems:
                                    quiz_list = []
                                    quiz_stem = self.clean_text(quizItem.get('stem'))
                                    quiz_stem = quiz_stem.replace('\n\n', '')
                                    markdown.append(f"#### Quiz {quiz_number}.")

                                    quiz_list.append(f"> [!important]")
                                    quiz_list.append(f"> **{self.clean_text(quiz_stem)}**")
                                    quiz_list.append(">")

                                    if quizItem.get('options'):
                                        for option in quizItem.get('options', []):
                                            quiz_list.append(f"> - [ ] {self.clean_text(option.get('title'))}")
                                    markdown.append("\n".join(quiz_list))
                                    quiz_number += 1

                        elif activity_type == 'link':
                            markdown.append(f"- [{activity_title}]({activity['link']})")

        return "\n\n".join(markdown) + "\n"

# END OF COURSE CLASS
# END OF FILE
