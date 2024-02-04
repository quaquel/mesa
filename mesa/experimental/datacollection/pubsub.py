from enum import StrEnum, auto
from collections import defaultdict
import contextlib

class Events(StrEnum):
    STATE_CHANGE = auto()
    AGENT_ADDED = auto()
    AGENT_REMOVED = auto()
    TIME_INCREMENT = auto()


class EventProducer:

    def __init__(self, owner):
        self.subscribers = defaultdict(list)
        self.owner = owner

    def subscribe(self, event: str, event_handler: callable):
        self.subscribers[event].append(event_handler)

    def unsubscribe(self, event: str, event_handler: callable):
        # or try except pass, which is slightly faster
        with contextlib.suppress(ValueError):
            self.subscribers[event].remove(event_handler)

    def fire_event(self, event: str, *args, **kwargs):
        # copy is needed here because the handling of the event
        # might result in the receiver unsubscribing itself, causing a change
        # in the dict while iterating over it.
        for entry in self.subscribers[event].copy():
            entry(self.owner, *args, **kwargs)


class ObservableNumber:
    # observable is a descriptor that can be used on
    # objects to declare specific attributes as observable (i.e., they fire events)

    def __get__(self, instance, owner):
        return getattr(instance, self.private_name)

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = f"_{name}"

    def __set__(self, instance, value):
        setattr(instance, self.private_name, value)
        instance.event_producer.fire_event(Events.STATE_CHANGE, self.public_name)


class Observer:
    def __init__(self, object, event, event_handler):
        self.event_handler = event_handler
        object.subscribe(event, self.handler)
        self.data = None

    def handler(self, *args, **kwargs):
        self.data = self.event_handler(*args, **kwargs)


class AgentSetObserver:

    # FIXME:: you want to initialize this with the current state
    def __init__(self, agentset, event, event_handler):
        self.event_handler = event_handler
        for agent in agentset:
            agent.subscribe(event, self.handler)
        self.data = {}

    def handler(self, subject, *args, **kwargs):
        self.data[subject.unique_id] = self.event_handler(subject, *args, **kwargs)