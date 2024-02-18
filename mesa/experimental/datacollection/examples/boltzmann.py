

from mesa.space import MultiGrid
from mesa.time import RandomActivation

from mesa.experimental.datacollection.mesa_classes import ObservableModel, ObservableAgent
from mesa.experimental.datacollection.pubsub import MessageType, ObservableState
from mesa.experimental.datacollection.collectors import collect, DataCollector, Measure, MeasureDescriptor
from mesa.experimental.datacollection.pubsub import AgentSetObserver

def compute_gini(agents):
    agent_wealths = [agent.wealth for agent in agents]
    x = sorted(agent_wealths)
    N = model.num_agents
    B = sum(xi * (N - i) for i, xi in enumerate(x)) / (N * sum(x))
    return 1 + (1 / N) - 2 * B



class BoltzmannWealthModel(ObservableModel):
    """A simple model of an economy where agents exchange currency at random.

    All the agents begin with one unit of currency, and each time step can give
    a unit of currency to another agent. Note how, over time, this produces a
    highly skewed distribution of wealth.
    """

    # gini = MeasureDescriptor()

    def __init__(self, N=100, width=10, height=10):
        super().__init__()
        self.num_agents = N
        self.grid = MultiGrid(width, height, True)
        self.schedule = RandomActivation(self)

        # Create agents
        for i in range(self.num_agents):
            a = MoneyAgent(i, self)
            self.schedule.add(a)
            # Add the agent to a random grid cell
            x = self.random.randrange(self.grid.width)
            y = self.random.randrange(self.grid.height)
            self.grid.place_agent(a, (x, y))

        self.running = True

        self.gini = Measure(self, self.agents, compute_gini)

    def step(self):
        self.schedule.step()


class MoneyAgent(ObservableAgent):
    """An agent with fixed initial wealth."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.wealth = 1

    def move(self):
        possible_steps = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=False
        )
        new_position = self.random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)

    def give_money(self):
        cellmates = self.model.grid.get_cell_list_contents([self.pos])
        cellmates.pop(
            cellmates.index(self)
        )  # Ensure agent is not giving money to itself
        if len(cellmates) > 0:
            other = self.random.choice(cellmates)
            other.wealth += 1
            self.wealth -= 1

    def step(self):
        self.move()
        if self.wealth > 0:
            self.give_money()


def handler(subject, state):
    if state == "wealth":
        return getattr(subject, state)


def some_func(obj):
    return obj.get_value()

if __name__ == '__main__':
    model = BoltzmannWealthModel()

    datacollector = DataCollector(model, [collect("wealth", model.agents),
                                          collect("gini", model)])


    for _ in range(10):
        model.step()
        datacollector.collect_all()

    print(datacollector.wealth.to_dataframe().head())
    print(datacollector.gini.to_dataframe().head())