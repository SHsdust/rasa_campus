from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import AllSlotsReset, SlotSet, Restarted, FollowupAction, SessionStarted
from typing import Any, Text, Dict, List
from rasa_sdk.forms import FormValidationAction
from dateutil import relativedelta, parser
from dateutil.relativedelta import relativedelta
import logging
import datetime
# from actions.action_ask_leave import Leave

from random import choice, randrange, sample, randint
from numpy import arange
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, REAL, or_
from sqlalchemy.orm import Session, sessionmaker
import time

logger = logging.getLogger(__name__)

Base = declarative_base()

# time_extractor = 'DucklingEntityExtractor'
time_extractor = 'smart'

def create_database(database_engine, database_name: Text):
    """Try to connect to the database. Create it if it does not exist"""
    try:
        database_engine.connect()
    except sa.exc.OperationalError:
        default_db_url = f"sqlite:///{database_name}.db"
        default_engine = sa.create_engine(default_db_url)
        conn = default_engine.connect()
        conn.execute("commit")
        conn.execute(f"CREATE DATABASE {database_name}")
        conn.close()


class Room(Base):
    __tablename__ = "room"
    id = Column(Integer, primary_key=True)
    people = Column(String(255))
    room_name = Column(String(255))
    date = Column(String(255))
    start = Column(Integer)
    end = Column(Integer)
    reason = Column(String(255))
    start_timestamp = Column(Integer)
    end_timestamp = Column(Integer)


class ProfileDB:
    def __init__(self, db_engine):
        self.engine = db_engine
        self.create_tables()
        self.session = self.get_session()
        self.room_name = ['101', '102', '103', '104', '105', '201', '202', '203', '204', '205', '301', '302', '303',
                          '304', '305']
        # self.time = {'09:00': 1, '10:00': 2, '11:00': 3, '12:00': 4, '13:00': 5, '14:00': 6, '15:00': 7, '16:00': 8,
        #              '17:00': 9, '18:00': 10}
        # self.time_dic = {self.time[i]: i for i in self.time}

    def create_tables(self):
        Room.__table__.create(self.engine, checkfirst=True)

    def get_session(self) -> Session:
        return sessionmaker(bind=self.engine, autoflush=True)()

    def get_room_free(self, date, start, end):
        start_timestamp = date+' '+start
        start_timestamp = parser.isoparse(start_timestamp)
        start_timestamp = int(time.mktime(start_timestamp.timetuple()))
        end_timestamp = date+' '+end
        end_timestamp = parser.isopparse(end_timestamp)
        end_timestamp = int(time.mktime(end_timestamp.timetuple()))
        room = (
            self.session.query(Room)
                .filter(Room.date == date)
                .filter(Room.start_timestamp <= start_timestamp)
                .filter(Room.end_timestamp > start_timestamp)
                .all(),
            self.session.query(Room)
                .filter(Room.date == date)
                .filter(Room.start_timestamp >= start_timestamp)
                .filter(Room.start_timestamp < end_timestamp)
                .all()
        )
        room_name_id = [j.room_name for i in room for j in i]
        print('get_room_free', room_name_id)
        room_name = list(filter(lambda obj: obj not in room_name_id, self.room_name))
        print('room_name', room_name)
        # room_name = [str(i) for i in room_name]
        return room_name

    def add_room_order(self, people, room_name, date, start, end, reason):
        try:
            # start = self.time[start]
            # end = self.time[end]
            start_timestamp = date + ' ' + start
            start_timestamp = parser.isoparse(start_timestamp)
            start_timestamp = int(time.mktime(start_timestamp.timetuple()))
            end_timestamp = date + ' ' + end
            end_timestamp = parser.isoparse(end_timestamp)
            end_timestamp = int(time.mktime(end_timestamp.timetuple()))
            add_user = Room(people=people, room_name=room_name, date=date, start=start, end=end, reason=reason, start_timestamp=start_timestamp, end_timestamp=end_timestamp)
            self.session.add(add_user)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(e)
            return False

    def get_user_book_room(self, people):
        room = (
            self.session.query(Room)
                .filter(Room.people == people)
                .all()
        )
        res = [{'people': i.people, 'room_name': i.room_name, 'date': i.date, 'start': i.start, 'end': i.end, 'reason': i.reason} for i in room]
        return res

    def restart(self):
        users = self.session.query(Room).all()
        [self.session.delete(user) for user in users]

        users = self.session.query(Leave).all()
        [self.session.delete(user) for user in users]

        self.session.commit()


ENGINE = sa.create_engine("sqlite:///profile.db")
create_database(ENGINE, 'profile')
profile_db = ProfileDB(ENGINE)


class ActionRestart(Action):
    def name(self) -> Text:
        return "action_restart"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ):
        logger.info('action_restart')
        profile_db.restart()
        return [Restarted()]

class ActionSessionStart(Action):
    def name(self) -> Text:
        return "action_session_start"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ):
        logger.info('action_session_start')
        # profile_db.restart()
        return [SessionStarted()]


class ActionQueryUserBookRoom(Action):
    def name(self) -> Text:
        return "action_query_user_book_room"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ):
        rooms = profile_db.get_user_book_room(tracker.sender_id)
        print('action_query_user_book_room', rooms)
        if rooms:
            dispatcher.utter_message('您有以下会议室预定信息：')
        else:
            dispatcher.utter_message('您当前没有预定会议室。')
        for room in rooms:
            message = (
                f"会议室号:{room['room_name']}，开始时间:{room['start']}，结束时间:{room['end']}，会议标题:{room['reason']}"
            )
            dispatcher.utter_message(message)
        return []


class ValidateQueryBookRoomForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_query_book_room_form"

    def validate_room_start_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_start_time, {}'.format(value))
        if value:
            try:
                value = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                return {"room_start_time": value}
            except Exception:
                return {"room_start_time": None}
        else:
            # return {"room_start_time": None}
            return {}

    def extract_room_start_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        # entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == 'DucklingEntityExtractor']
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]

        logger.info('extract_room_start_time, {}'.format(entities))
        logger.info('extract_room_start_time, {}'.format(tracker.slots.get('room_start_time')))

        if entities and tracker.slots.get('requested_slot') != 'room_end_time':
            logger.info('extract_room_start_time, {}'.format(entities[0]['value']))
            return {'room_start_time': entities[0]['value']}

        # return {"room_start_time": tracker.slots.get('room_start_time')}
        return {}

    def validate_room_end_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_end_time, {}'.format(value))
        if value:
            try:
                end_time = parser.isoparse(tracker.slots.get('room_end_time')).strftime("%Y-%m-%d %H:%M")
                end_time = parser.isoparse(end_time)
                start_time = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                start_time = parser.isoparse(start_time)
                if end_time < start_time:
                    end_time = end_time + datetime.timedelta(hours=12)
                value = end_time.strftime("%Y-%m-%d %H:%M")
                return {"room_end_time": value}
            except:
                return {"room_end_time": None}
        else:
            # return {"room_end_time": None}
            return {}

    def extract_room_end_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        # entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == 'DucklingEntityExtractor']
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_end_time, {}'.format(entities))
        logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_end_time')))
        if entities:
            logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_start_time')))
            if len(entities) == 1 and tracker.slots.get('requested_slot') == 'room_end_time':
                logger.info('extract_room_end_time, {}'.format(entities[0]['value']))
                return {'room_end_time': entities[0]['value']}
            if len(entities) == 2:
                logger.info('extract_room_end_time, {}'.format(entities[1]['value']))
                return {'room_end_time': entities[1]['value']}

        # return {"room_end_time": tracker.slots.get('room_end_time')}


class ActionQueryBookRoom(Action):
    def name(self) -> Text:
        return "action_query_book_room"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        room_start_time = tracker.get_slot("room_start_time")
        room_end_time = tracker.get_slot("room_end_time")
        if room_start_time and room_end_time:
            room_name = profile_db.get_room_free(room_start_time.split(' ')[0], room_start_time.split(' ')[1],
                                                 room_end_time.split(' ')[1])
            message = (
                f"目前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}。"
            )
            dispatcher.utter_message(message)
            return []
        else:

            return []


class ActionAskBookRoom(Action):
    def name(self) -> Text:
        return "action_book_room"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        room_start_time = tracker.get_slot("room_start_time")
        room_end_time = tracker.get_slot("room_end_time")
        room_id = tracker.get_slot("room_id")
        room_text = tracker.get_slot("room_text")
        room_confirm = tracker.get_slot("room_confirm")
        if room_confirm == 'no':
            dispatcher.utter_message(
                text="好的，已为您取消申请"
            )
            return [SlotSet("room_start_time", None),
                    SlotSet("room_end_time", None),
                    SlotSet("room_id", None),
                    SlotSet("room_text", None),
                    SlotSet("room_confirm", None)]
        elif room_confirm == 'yes':
            # api
            result = profile_db.add_room_order(tracker.sender_id, room_id, room_start_time.split(' ')[0],
                                               room_start_time.split(' ')[1], room_end_time.split(' ')[1], room_text)

            if result:
                message = (
                    f"已成功帮你提交申请，\n    会议开始时间: {room_start_time}\n    会议结束时间: {room_end_time}\n    会议房间号: {room_id}\n    会议标题: {room_text}"
                )
            else:
                message = (
                    f"提交请假申请失败。"
                )
            dispatcher.utter_message(message)
            return [SlotSet("room_start_time", None),
                    SlotSet("room_end_time", None),
                    SlotSet("room_id", None),
                    SlotSet("room_text", None),
                    SlotSet("room_confirm", None)]
        return []


class ValidateBookRoomForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_book_room_form"

    def validate_room_start_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_start_time, {}'.format(value))
        if value:
            try:
                value = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                return {"room_start_time": value}
            except:
                return {"room_start_time": None}
        else:
            # return {"room_start_time": None}
            return {}

    def extract_room_start_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        # entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == 'DucklingEntityExtractor']
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_start_time, {}'.format(entities))
        logger.info('extract_room_start_time, {}'.format(tracker.slots.get('room_start_time')))
        if entities and tracker.slots.get('requested_slot') != 'room_end_time':
            logger.info('extract_room_start_time, {}'.format(entities[0]['value']))
            return {'room_start_time': entities[0]['value']}

        # return {"room_start_time": tracker.slots.get('room_start_time')}

    def validate_room_end_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_end_time, {}'.format(value))
        if value:
            try:
                end_time = parser.isoparse(tracker.slots.get('room_end_time')).strftime("%Y-%m-%d %H:%M")
                end_time = parser.isoparse(end_time)
                start_time = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                start_time = parser.isoparse(start_time)
                if end_time < start_time:
                    end_time = end_time + datetime.timedelta(hours=12)
                value = end_time.strftime("%Y-%m-%d %H:%M")
                return {"room_end_time": value}
            except:
                return {"room_end_time": None}
        else:
            # return {"room_end_time": None}
            return {}

    def extract_room_end_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        # entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == 'DucklingEntityExtractor']
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_end_time, {}'.format(entities))
        logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_end_time')))
        if entities:
            logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_start_time')))
            if len(entities) == 1 and tracker.slots.get('requested_slot') == 'room_end_time':
                logger.info('extract_room_end_time, {}'.format(entities[0]['value']))
                return {'room_end_time': entities[0]['value']}
            if len(entities) == 2:
                logger.info('extract_room_end_time, {}'.format(entities[1]['value']))
                return {'room_end_time': entities[1]['value']}

        # return {"room_end_time": tracker.slots.get('room_end_time')}

    def validate_room_id(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_id, {}'.format(value))
        if tracker.slots.get('requested_slot') != 'room_text':
            all_entities = tracker.latest_message.get("entities", [])
            entities = [e for e in all_entities if e.get("entity") == 'room_id']
            if entities:
                room_start_time = tracker.get_slot("room_start_time")
                room_end_time = tracker.get_slot("room_end_time")
                if room_start_time and room_end_time:
                    room_name = profile_db.get_room_free(room_start_time.split(' ')[0], room_start_time.split(' ')[1],
                                                         room_end_time.split(' ')[1])
                    if entities[0]['value'] not in profile_db.room_name:
                        dispatcher.utter_message('没有这个会议室。')
                        message = (
                            f"目前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}。"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                    elif entities[0]['value'] not in room_name:
                        dispatcher.utter_message('当前会议室已被预定。')
                        message = (
                            f"目前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}。"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                else:
                    if entities[0]['value'] not in profile_db.room_name:
                        dispatcher.utter_message('没有这个会议室。')
                        message = (
                            f"目前会议室有{'、'.join(profile_db.room_name)}。"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                return {"room_id": entities[0]['value']}
            else:
                return {"room_id": None}
        else:
            slots = [i for i in tracker.events if i.get('event') == 'slot' and i.get('name') == 'room_id']
            if len(slots) == 1:
                return {"room_id": slots[0]['value']}
            else:
                return {"room_id": slots[-2]['value']}

    def validate_room_text(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_text, {}'.format(value))
        return {"room_text": value}

    def validate_room_confirm(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_confirm, {}'.format(value))
        if value in ["yes", "no"]:
            return {"room_confirm": value}
        return {"room_confirm": None}
