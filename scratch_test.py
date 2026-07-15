import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from chatbot.intent import is_off_topic, has_project_context

msg = "what is the capital of india"
print(f"has_project_context: {has_project_context(msg)}")
print(f"is_off_topic: {is_off_topic(msg)}")
