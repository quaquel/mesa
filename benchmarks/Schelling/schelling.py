

from mesa import Model
from mesa.gridspace import CellAgent, Grid
from mesa.time import RandomActivation


class SchellingAgent(CellAgent):
    """
    Schelling segregation agent
    """

    def __init__(self, unique_id, model, agent_type, cell, radius):
        """
        Create a new Schelling agent.

        Args:
           unique_id: Unique identifier for the agent.
           x, y: Agent initial location.
           agent_type: Indicator for the agent's type (minority=1, majority=0)
        """
        super().__init__(unique_id, model)
        self.cell = cell
        self.type = agent_type
        self.radius = radius
        # self.get_neighborhood = create_neighborhood_getter(radius)

    # @profile
    def step(self):
        similar = 0
        for neighbor in self.cell.get_neighborhood(radius=self.radius)._agents:
            if neighbor.type == self.type:
                similar += 1

        # If unhappy, move:
        if similar < self.model.homophily:
            # self.model.grid.move_to_empty(self)
            self.model.grid.move_to_empty(self)
        else:
            self.model.happy += 1


class Schelling(Model):
    """
    Model class for the Schelling segregation model.
    """

    def __init__(self, seed, height, width, homophily, radius, density, minority_pc=0.5):
        """ """
        super().__init__(seed)
        self.width = width
        self.height = height
        self.density = density
        self.minority_pc = minority_pc
        self.homophily = homophily
        self.radius = radius

        self.schedule = RandomActivation(self)
        self.grid = Grid(width, height, torus=True)

        self.happy = 0

        for cell in self.grid:
            if self.random.random() < self.density:
                agent_type = 1 if self.random.random() < self.minority_pc else 0
                agent = SchellingAgent(self.next_id(), self, agent_type, cell, radius)
                self.grid.move_agent(agent, cell)
                self.schedule.add(agent)

        self.running = True

    def step(self):
        """
        Run one step of the model. If All agents are happy, halt the model.
        """
        self.happy = 0  # Reset counter of happy agents
        self.schedule.step()


if __name__ == "__main__":
    import time

    # model = Schelling(15, 40, 40, 3, 1, 0.625)
    model = Schelling(15, 100, 100, 8, 2, 0.8)

    start_time = time.perf_counter()
    for _ in range(100):
        model.step()
    print("Time:", time.perf_counter() - start_time)
