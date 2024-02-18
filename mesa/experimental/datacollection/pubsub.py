from enum import StrEnum, auto
from collections import defaultdict
import contextlib

from typing import List, Set, Callable, Type


class MessageType:
    # FIXME should there be only one instance for each name?
    # Should we dynamically create a class for each message type?
    # at least we should have some way to validate a message

    message_types = defaultdict(list)

    def __init__(self, message_fields: str | Set[str] | None = None) -> None:
        if isinstance(message_fields, str):
            message_fields = set((message_fields, ))
        self.message_fields: Set[str] = message_fields
        self.name: str | None = None
        self.defining_class: Type | None = None

    def __set_name__(self, defining_class: Type, name: str) -> None:
        self.defining_class = defining_class
        self.name = name

        type(self).message_types[name].append(defining_class)


class Message:
    def __init__(self, message_type: MessageType, sender, **kwargs):
        if not self.validate_content(message_type, kwargs):
            raise ValueError(f"message fields not correct for message type {message_type.name}"
                             f"expected {message_type.message_fields} but got {set(kwargs.keys())}")

        self.message_type = message_type
        self.sender = sender
        for k, v in kwargs.items():
            setattr(self, k, v)

    @staticmethod
    def validate_content(message_type, content):
        return set(content.keys()) == message_type.message_fields


class MessageProducer:

    def __init__(self, owner):
        self.subscribers = defaultdict(list)
        self.owner = owner

    def subscribe(self, event_name: str, event_handler: Callable):
        self.subscribers[event_name].append(event_handler)

    def unsubscribe(self, event_name: str, event_handler: Callable):
        # or try except pass, which is slightly faster
        with contextlib.suppress(ValueError):
            self.subscribers[event_name].remove(event_handler)

    def send_message(self, message_type: MessageType, **kwargs):
        """send message of message type and with content in keyword arguments to all subscribers"""

        # copy is needed here because the handling of the event
        # might result in the receiver unsubscribing itself, causing a change
        # in the dict while iterating over it.
        message = Message(message_type, self.owner, **kwargs)

        for entry in self.subscribers[message_type.name].copy():
            entry(message)


class ObservableState:
    # observable is a descriptor that can be used on
    # objects to declare specific attributes as observable (i.e., they fire events)

    def __get__(self, instance, owner):
        return getattr(instance, self.private_name)

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = f"_{name}"

    def __set__(self, instance, value):
        setattr(instance, self.private_name, value)
        instance.event_producer.send_message(instance.STATE_CHANGE, state=self.public_name)


# class Observer:
#     def __init__(self, obj, event, message_handler):
#         self.message_handler = message_handler
#         obj.subscribe(event, self.handler)
#         self.data = None
#
#     def handler(self, *args, **kwargs):
#         self.data = self.message_handler(*args, **kwargs)


# class AgentSetObserver:
#
#     # FIXME:: you want to initialize this with the current state
#     def __init__(self, agentset, event, event_handler):
#         self.event_handler = event_handler
#         for agent in agentset:
#             agent.subscribe(event, self.handler)
#         self.data = {}
#
#     def handler(self, subject, *args, **kwargs):
#         self.data[subject.unique_id] = self.event_handler(subject, *args, **kwargs)
