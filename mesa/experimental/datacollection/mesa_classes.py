from typing import Any, Iterable, Callable, List

import itertools

from ...agent import Agent, AgentSet
from ...model import Model
from .pubsub import MessageProducer, MessageType
from .collectors import Measure, MeasureDescriptor


class UpdatedAgentSet(AgentSet):

    def get(self, attr_names: str | List[str]) -> list[Any]:
        """
        Retrieve the specified attribute(s) from each agent in the AgentSet.

        Args:
            attr_names (str | List[str]): The name(s) of the attribute(s) to retrieve from each agent.

        Returns:
            list[Any]: A list of attribute values for each agent in the set.
        """

        if isinstance(attr_names, str):
            return [getattr(agent, attr_names) for agent in self._agents]
        else:
            return [[getattr(agent, attr_name) for attr_name in attr_names] for agent in self._agents]


class ConditionalAgentSet(UpdatedAgentSet):
    """This is a dynamic agent set where membership depends on a specified condition

    For this agent set, memberships depends on a user specified condition, and it can change over the course of the
    simulation. Agent membership is evaluated everytime the agent sends a STATE_CHANGE message.

    If the user passes an initial set of agents, only these agents are considered to be potentially part of the
    agent set

    If the suer does not pass an initial set of agents, it defaults to model.agents


    """

    def __init__(self, agents: Iterable[Agent] | None, model: Model, condition: Callable[[Agent], bool]) -> None:
        """

        Args:
            agents (Iterable[Agent]): An iterable of agents. These form the basis of the agents in the set
            model (Model): A model instance
            condition (Callable[[Agent], bool]): a function that takes an agent and returns boolean. If true, the agent
            is considered part of the agent set, otherwise the is currently not part of the agent set.


        """

        super().__init__({}, model)
        self._condition = condition

        if agents is None:
            agents = model.agents
            model.subscribe(model.AGENT_ADDED.name)

        for agent in agents:
            self.add_permanently(agent)

    def add_permanently(self, agent: Agent) -> None:
        agent.subscribe(agent.STATE_CHANGE.name, self.state_change_handler)
        self._apply_condition(agent)
    def remove_permanently(self, agent):
        self.remove(agent)
        agent.unsubscribe(agent.STATE_CHANGE.name, self.state_change_handler)

    def _apply_condition(self, agent: Agent):
        if self._condition(agent):
            self.add(agent)
        else:
            self.discard(agent)

    def state_change_handler(self, message):
        self._apply_condition(message.sender)

    def agent_added_handler(self, message):
        agent = message.agent
        agent.subscribe(agent.STATE_CHANGE)
        self._apply_condition(agent)


class ObservableModel(Model):
    AGENT_ADDED = MessageType("agent")
    AGENT_REMOVED = MessageType("agent")
    STATE_CHANGED = MessageType("state")

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
    STATE_CHANGE = MessageType("state")

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
