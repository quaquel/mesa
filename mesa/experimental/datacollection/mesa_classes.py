from typing import Any, Iterable, Callable, List

import itertools

from ...agent import Agent, AgentSet
from ...model import Model
from .pubsub import MessageProducer, MessageType
from .collectors import Measure, MeasureDescriptor



class ConditionalAgentSet(AgentSet):
    """This is a dynamic agent set where membership depends on a specified condition

    For this agent set, memberships depends on a user specified condition, and it can change over the course of the
    simulation. Agent membership is evaluated everytime the agent sends a STATE_CHANGE message.

    If the user passes an initial set of agents, only these agents are considered to be potentially part of the
    agent set

    If the suer does not pass an initial set of agents, it defaults to model.agents


    """

    def __init__(self, agents: Iterable[Agent] | None, model: Model, observable_state:str, condition: Callable[[Any], bool]) -> None:
        """
        FIXME:: ONLY SIMPLE CONDITIONS ARE CURRENTLY SUPPORTED


        Args:
            agents (Iterable[Agent]): An iterable of agents. These form the basis of the agents in the set
            model (Model): A model instance
            condition (Callable[[Agent], bool]): a function that takes an agent and returns boolean. If true, the agent
            is considered part of the agent set, otherwise the is currently not part of the agent set.


        """

        super().__init__({}, model)
        self._condition: Callable[[Any], bool] = condition
        self.observable_state: str = observable_state
        self._message_type: str = f"{observable_state.upper()}_CHANGE"

        if agents is None:
            agents = model.agents
            model.subscribe(model.AGENT_ADDED)

        for agent in agents:
            self.add_permanently(agent)

    def add_permanently(self, agent: Agent) -> None:
        agent.subscribe(getattr(agent, self._message_type), self.state_change_handler)
        self._apply_condition(agent, getattr(agent, self.observable_state))

    def remove_permanently(self, agent):
        self.remove(agent)
        agent.unsubscribe(getattr(agent, self._message_type), self.state_change_handler)

    def _apply_condition(self, agent, value) -> None:
        if self._condition(value):
            self.add(agent)
        else:
            self.discard(agent)

    def state_change_handler(self, message):
       self._apply_condition(message.sender, message.value)

    def agent_added_handler(self, message):
        agent = message.agent
        agent.subscribe(getattr(agent, self._message_type), self.state_change_handler)
        self._apply_condition(agent, getattr(agent, self.name))


class ObservableModel(Model):
    AGENT_ADDED = MessageType("agent")
    AGENT_REMOVED = MessageType("agent")

    def __setattr__(self, name, value):
        if isinstance(value, Measure) and not name.startswith("_"):
            klass = type(self)
            descr = MeasureDescriptor()
            descr.__set_name__(klass, name)
            setattr(klass, name, descr)
            descr.__set__(self, value)
        else:
            super().__setattr__(name, value)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.event_producer = MessageProducer(self)

    @property
    def time(self):
        return self._time

    def add_agent(self, agent: Agent) -> None:
        self.agents_[type(agent)][agent] = None
        self.event_producer.send_message(self.AGENT_ADDED, agent=agent)

    def remove_agent(self, agent: Agent) -> None:
        self.agents_[type(agent)].pop(agent, default=None)
        self.event_producer.send_message(self.AGENT_REMOVED, agent=agent)

    def get_agents_of_type(self, agenttype: type[Agent]) -> AgentSet:
        """Retrieves an AgentSet containing all agents of the specified type."""
        return AgentSet(self.agents_[agenttype].keys(), self)

    @property
    def agents(self) -> AgentSet:
        if hasattr(self, "_agents"):
            return self._agents
        else:
            all_agents = itertools.chain.from_iterable(self.agents_.values())
            return AgentSet(all_agents, self)

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
        super().__init__(unique_id, model)
        self.unique_id = unique_id
        self.model = model
        self.pos = None
        self.event_producer = MessageProducer(self)

        # register agent
        self.model.add_agent(self)

    def remove_agent(self, agent: Agent) -> None:
        self.model.remove_agent(agent)

    def subscribe(self, event: str, event_handler: callable):
        self.event_producer.subscribe(event, event_handler)

    def unsubscribe(self, event: str, event_handler: callable):
        # or try except pass, which is slightly faster
        self.event_producer.unsubscribe(event, event_handler)
