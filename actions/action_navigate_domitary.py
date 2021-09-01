from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher

import requests

from actions.utils.request import get

# This is a simple example for a custom action which utters "Hello World!"


class ActionNavigateDomitary(Action):

    def name(self) -> Text:
        return "action_navigate_domitary"

    async def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text")

        domitary = tracker.get_slot("domitary")

        dispatcher.utter_message(f"垃圾宿舍")
        return []



if __name__ == "__main__":
    pass
