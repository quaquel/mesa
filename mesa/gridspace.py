import itertools
import random
import warnings
from collections import defaultdict
from collections.abc import Iterable
from functools import cache
from random import Random
from typing import Any, Callable

from mesa import Agent, Model


from line_profiler_pycharm import profile

Coordinates = tuple[int, int]

class CellAgent:
    """
    Base class for a model agent in Mesa.

    Attributes:
        unique_id (int): A unique identifier for this agent.
        model (Model): A reference to the model instance.
        self.pos: Position | None = None
    """

    def __init__(self, unique_id: int, model: Model) -> None:
        """
        Create a new agent.

        Args:
            unique_id (int): A unique identifier for this agent.
            model (Model): The model instance in which the agent exists.
        """
        self.unique_id = unique_id
        self.model = model
        self.cell: Cell | None = None

        # register agent
        try:
            self.model.agents_[type(self)][self] = None
        except AttributeError:
            # model super has not been called
            self.model.agents_ = defaultdict(dict)
            self.model.agentset_experimental_warning_given = False

            warnings.warn(
                "The Mesa Model class was not initialized. In the future, you need to explicitly initialize the Model by calling super().__init__() on initialization.",
                FutureWarning,
                stacklevel=2,
            )

    @property
    def pos(self):
        return self.cell.coords

    def remove(self) -> None:
        """Remove and delete the agent from the model."""
        self.model.agents_[type(self)].pop(self, None)

    def step(self) -> None:
        """A single step of the agent."""

    def advance(self) -> None:
        pass

    @property
    def random(self) -> Random:
        return self.model.random


# def create_neighborhood_getter(moore=True, include_center=False, radius=1):
#     # TODO:: or raise an error if radius < 1
#     @cache
#     def of(cell: Cell):
#         if radius == 0:
#             return {cell: cell.content}
#
#         neighborhood = {}
#         for neighbor in cell.connections:
#             if (
#                     moore
#                     or neighbor.coords[0] == cell.coords[0]
#                     or neighbor.coords[1] == cell.coords[1]
#             ):
#                 neighborhood[neighbor] = neighbor.content
#
#         if radius > 1:
#             for neighbor in list(neighborhood.keys()):
#                 neighborhood.update(
#                     create_neighborhood_getter(moore, include_center, radius - 1)(
#                         neighbor
#                     )
#                 )
#
#         if not include_center:
#             neighborhood.pop(cell, None)
#
#         return CellCollection(neighborhood)
#
#     return of


class Cell:
    __slots__ = ["coords", "connections", "content", "direct_neighborhood", "space"]

    def __init__(self, i: int, j: int, space) -> None:
        self.coords = (i, j)
        self.connections: list[Cell] = [] # TODO: change to CellCollection?
        self.content = {} # TODO:: change to AgentSet or weakrefs? (neither is very performant, )
        self.direct_neighborhood = CellCollection({})
        self.space: DiscreteSpace = space

    def connect(self, other) -> None:
        """Connects this cell to another cell."""
        self.connections.append(other)
        self.direct_neighborhood.cells[other] = other.content

    def disconnect(self, other) -> None:
        """Disconnects this cell from another cell."""
        self.connections.remove(other)
        self.direct_neighborhood.cells.pop(other, None)

    def add_agent(self, agent: Agent) -> None:
        """Adds an agent to the cell."""
        if len(self.content) == 0:
            self.space._empties.pop(self.coords, None)
        self.content[agent] = None
        agent.cell = self

    def remove_agent(self, agent: Agent) -> None:
        """Removes an agent from the cell."""
        self.content.pop(agent, None)
        agent.cell = None
        if len(self.content) == 0:
            self.space._empties[self.coords] = None

    @cache
    def get_neighborhood(self, moore=True, include_center=False, radius=1):
        return CellCollection(self._get_neighborhood(moore=moore, include_center=include_center, radius=radius))

    def _get_neighborhood(self, moore=True, include_center=False, radius=1):
        if radius == 0:
            return {self: self.content}

        neighborhood = {}
        for neighbor in self.connections:
            if (
                    moore
                    or neighbor.coords[0] == self.coords[0]
                    or neighbor.coords[1] == self.coords[1]
            ):
                neighborhood[neighbor] = neighbor.content

        radius = radius - 1
        if radius > 1:
            for neighbor in list(neighborhood.keys()):
                neighborhood.update(neighbor._get_neighborhood(moore, include_center, radius))

        if not include_center:
            neighborhood.pop(self, None)

        return neighborhood

    def __repr__(self):
        return f"Cell({self.coords})"


class CellCollection:

    def __init__(self, cells: dict[Cell, Iterable[Agent]]) -> None:
        self.cells = cells

    def __iter__(self):
        return iter(self.cells)

    def __getitem__(self, key:Cell) -> Iterable[Agent]:
        return self.cells[key]

    def __setitem__(self, key:Cell, value:Iterable[Agent]):
        self.cells[key] = value

    def __delitem__(self, key:Cell):
        del self.cells[key]

    def __len__(self):
        return len(self.cells)

    def __repr__(self):
        return f"CellCollection({self.cells})"

    @property
    def agents(self) -> Iterable[Agent]:
        # should this not return an agentset
        # changing this makes the code potentially slow
        return itertools.chain.from_iterable(self.cells.values())

    def select_random(self) -> Cell:
        return random.choice(list(self.cells.keys()))

    def update(self, other):
        self.cells.update(other.cells)

    #     # TODO:: what about shuffle, select, sort, add, and remove
    #     # TODO:: How close do we want to mimic the behavior of AgentSet


class DiscreteSpace:
    cells: dict[Coordinates, Cell]

    def _connect_single_cell(self, cell):  # <= different for every concrete Space
        ...

    def __iter__(self):
        return iter(self.cells.values())

    def get_neighborhood(self, coords: Coordinates, neighborhood_getter: Callable):
        # TODO:: what is the point of this method. You have the ccoordinates. and the
        # TODO:: getter, why run it through the grid
        return neighborhood_getter(self.cells[coords])

    def move_agent(self, agent: Agent, new_cell: Cell) -> None:
        """Move an agent from its current position to a new position."""

        agent.cell.remove_agent(agent)
        new_cell.add_agent(agent)


    @property
    def empties(self) -> CellCollection:

        return CellCollection(
            {
                self.cells[coords]: self.cells[coords].content
                for coords in self._empties
            }
        )

    # @profile
    def move_to_empty(self, agent) -> Cell:
        """Moves agent to a random empty cell, vacating agent's old cell."""

        num_empty_cells = len(self._empties)
        if num_empty_cells == 0:
            raise Exception("ERROR: No empty cells")

        # This method is based on Agents.jl's random_empty() implementation. See
        # https://github.com/JuliaDynamics/Agents.jl/pull/541. For the discussion, see
        # https://github.com/projectmesa/mesa/issues/1052 and
        # https://github.com/projectmesa/mesa/pull/1565. The cutoff value provided
        # is the break-even comparison with the time taken in the else branching point.
        if num_empty_cells > self.cutoff_empties:
            while True:
                new_pos = (
                    agent.random.randrange(self.width),
                    agent.random.randrange(self.height),
                )
                if new_pos in self._empties:
                    break
        else:
            new_pos = agent.random.choice(list(self._empties.keys()))

        self.move_agent(agent, self.cells[new_pos])

    def is_cell_empty(self, pos) -> bool:
        """Returns a bool of the contents of a cell."""
        return len(self.cells[pos].content) == 0


class Grid(DiscreteSpace):
    def __init__(self, width: int, height: int, torus: bool = False) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self.torus = torus
        self.cells = {(i, j): Cell(i, j, self) for j in range(width) for i in range(height)}

        self._empties = {(i, j): None for j in range(width) for i in range(height)}
        self.cutoff_empties = 7.953 * len(self.cells) ** 0.384

        for cell in self.cells.values():
            self._connect_single_cell(cell)

    def _connect_single_cell(self, cell):
        i, j = cell.coords
        directions = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ]
        for di, dj in directions:
            ni, nj = (i + di, j + dj)
            if self.torus:
                ni, nj = ni % self.height, nj % self.width
            if 0 <= ni < self.height and 0 <= nj < self.width:
                cell.connect(self.cells[ni, nj])

    def get_neighborhood(self, coords, neighborhood_getter: Any) -> CellCollection:
        return neighborhood_getter(self.cells[coords])
