from typing import Any

import itertools

from ...agent import Agent, AgentSet
from ...model import Model
from .pubsub import EventProducer, Events

class UpdatedAgentSet(AgentSet):

    def get(self, attr_names: str | list[str]) -> list[Any]:
        if isinstance(attr_names, str):
            attr_names = [attr_names]
        a = [[getattr(agent, attr_name) for attr_name in attr_names] for agent in self._agents]
        return a


class ObservableModel(Model):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.event_producer = EventProducer(self)

    @property
    def time(self):
        return self._time

    def add_agent(self, agent:Agent) -> None:
        self.agents_[type(agent)][agent] = None
        self.event_producer.fire_event(Events.AGENT_ADDED, agent)

    def remove_agent(self, agent:Agent) -> None:
        self.agents_[type(agent)].pop(agent, default=None)
        self.event_producer.fire_event(Events.AGENT_REMOVED, agent)

    def get_agents_of_type(self, agenttype: type[Agent]) -> AgentSet:
        """Retrieves an AgentSet containing all agents of the specified type."""
        return UpdatedAgentSet(self.agents_[agenttype].keys(), self)

    @property
    def agents(self) -> AgentSet:
        if hasattr(self, "_agents"):
            return self._agents
        else:
            all_agents = itertools.chain.from_iterable(self.agents_.values())
            return UpdatedAgentSet(all_agents, self)

    def subscribe(self, event: str, event_handler: callable):
        self.event_producer.subscribe(event, event_handler)

    def unsubscribe(self, event: str, event_handler: callable):
        # or try except pass, which is slightly faster
        self.event_producer.unsubscribe(event, event_handler)


class ObservableAgent(Agent):
    def __init__(self, unique_id: int, model: ObservableModel) -> None:
        """
        Create a new agent.

        Args:
            unique_id (int): A unique identifier for this agent.
            model (Model): The model instance in which the agent exists.
        """
        self.unique_id = unique_id
        self.model = model
        self.pos = None
        self.event_producer = EventProducer(self)

        # register agent
        self.model.add_agent(self)

    def remove_agent(self, agent: Agent) -> None:
        self.model.remove_agent(agent)

    def subscribe(self, event: str, event_handler: callable):
        self.event_producer.subscribe(event, event_handler)

    def unsubscribe(self, event: str, event_handler: callable):
        # or try except pass, which is slightly faster
        self.event_producer.unsubscribe(event, event_handler)






