# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions



from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher

import cpca
import requests

from actions.utils.request import get

# This is a simple example for a custom action which utters "Hello World!"
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

KEY = "527143302d5d4b43b683599c90b1d9ff"
CITY_LOOKUP_URL = "https://geoapi.qweather.com/v2/city/lookup"
WEATHER_URL = "https://devapi.qweather.com/v7/weather/now"


class ActionQueryWeather(Action):
    def name(self) -> Text:
        return "action_query_weather"

    async def run(self, dispather: CollectingDispatcher,
                  tracker: Tracker,
                  domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text")
        province, city = cpca.transform([user_message]).loc[0, ["省", "市"]]
        city = province if city in ["市辖区", None] else city

        text = await self.get_weather(await self.get_location_id(city))
        dispather.utter_message(text=text)

        return []


    @staticmethod
    async def get_location_id(city):

        params = {
            "location": city,
            "key": KEY
        }

        res = await get(CITY_LOOKUP_URL, params=params)

        return res["location"][0]["id"]

    @staticmethod
    async def get_weather(location_id):

        params = {
            "location": location_id,
            "key": KEY
        }

        res = (await get(WEATHER_URL, params=params))["now"]

        return f"{res['text']} 风向: {res['windDir']}\n温度: {res['temp']}摄氏度\n体感温度：{res['feelsLike']}摄氏度"


if __name__ == "__main__":
    location = "深圳"
    params_for_id = {
        "location": location,
        "key": KEY
    }
    location_id = requests.get(CITY_LOOKUP_URL, params=params_for_id).json()["location"][0]["id"]
    print("location: ", location)
    print("location_id: ", location_id)

    params_for_wea = {
        "location": location_id,
        "key": KEY
    }
    weather = requests.get(WEATHER_URL, params=params_for_wea).json()
    print("weather: ", weather)
