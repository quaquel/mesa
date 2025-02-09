"""Mesa Data Collection Module.

DataCollector is meant to provide a simple, standard way to collect data
generated by a Mesa model. It collects four types of data: model-level data,
agent-level data, agent-type-level data, and tables.

A DataCollector is instantiated with three dictionaries of reporter names and
associated variable names or functions for each, one for model-level data,
one for agent-level data, and one for agent-type-level data; a fourth dictionary
provides table names and columns. Variable names are converted into functions
which retrieve attributes of that name.

When the collect() method is called, each model-level function is called, with
the model as the argument, and the results associated with the relevant
variable. Then the agent-level functions are called on each agent, and the
agent-type-level functions are called on each agent of the specified type.

Additionally, other objects can write directly to tables by passing in an
appropriate dictionary object for a table row.

The DataCollector then stores the data it collects in dictionaries:
    * model_vars maps each reporter to a list of its values
    * tables maps each table to a dictionary, with each column as a key with a
      list as its value.
    * _agent_records maps each model step to a list of each agent's id
      and its values.
    * _agenttype_records maps each model step to a dictionary of agent types,
      each containing a list of each agent's id and its values.

Finally, DataCollector can create a pandas DataFrame from each collection.
"""

import contextlib
import itertools
import types
import warnings
from copy import deepcopy
from functools import partial

with contextlib.suppress(ImportError):
    import pandas as pd


class DataCollector:
    """Class for collecting data generated by a Mesa model.

    A DataCollector is instantiated with dictionaries of names of model-,
    agent-, and agent-type-level variables to collect, associated with
    attribute names or functions which actually collect them. When the
    collect(...) method is called, it collects these attributes and executes
    these functions one by one and stores the results.
    """

    def __init__(
        self,
        model_reporters=None,
        agent_reporters=None,
        agenttype_reporters=None,
        tables=None,
    ):
        """Instantiate a DataCollector with lists of model, agent, and agent-type reporters.

        Both model_reporters, agent_reporters, and agenttype_reporters accept a
        dictionary mapping a variable name to either an attribute name, a function,
        a method of a class/instance, or a function with parameters placed in a list.

        Model reporters can take four types of arguments:
        1. Lambda function:
           {"agent_count": lambda m: len(m.agents)}
        2. Method of a class/instance:
           {"agent_count": self.get_agent_count} # self here is a class instance
           {"agent_count": Model.get_agent_count} # Model here is a class
        3. Class attributes of a model:
           {"model_attribute": "model_attribute"}
        4. Functions with parameters that have been placed in a list:
           {"Model_Function": [function, [param_1, param_2]]}

        Agent reporters can similarly take:
        1. Attribute name (string) referring to agent's attribute:
           {"energy": "energy"}
        2. Lambda function:
           {"energy": lambda a: a.energy}
        3. Method of an agent class/instance:
           {"agent_action": self.do_action} # self here is an agent class instance
           {"agent_action": Agent.do_action} # Agent here is a class
        4. Functions with parameters placed in a list:
           {"Agent_Function": [function, [param_1, param_2]]}

        Agenttype reporters take a dictionary mapping agent types to dictionaries
        of reporter names and attributes/funcs/methods, similar to agent_reporters:
           {Wolf: {"energy": lambda a: a.energy}}

        The tables arg accepts a dictionary mapping names of tables to lists of
        columns. For example, if we want to allow agents to write their age
        when they are destroyed (to keep track of lifespans), it might look
        like:
           {"Lifespan": ["unique_id", "age"]}

        Args:
            model_reporters: Dictionary of reporter names and attributes/funcs/methods.
            agent_reporters: Dictionary of reporter names and attributes/funcs/methods.
            agenttype_reporters: Dictionary of agent types to dictionaries of
                                 reporter names and attributes/funcs/methods.
            tables: Dictionary of table names to lists of column names.

        Notes:
            - If you want to pickle your model you must not use lambda functions.
            - If your model includes a large number of agents, it is recommended to
              use attribute names for the agent reporter, as it will be faster.
        """
        self.model_reporters = {}
        self.agent_reporters = {}
        self.agenttype_reporters = {}

        self.model_vars = {}
        self._agent_records = {}
        self._agenttype_records = {}
        self.tables = {}

        # add the signal of the validation of model reporter
        self._validated = False

        if model_reporters is not None:
            for name, reporter in model_reporters.items():
                self._new_model_reporter(name, reporter)

        if agent_reporters is not None:
            for name, reporter in agent_reporters.items():
                self._new_agent_reporter(name, reporter)

        if agenttype_reporters is not None:
            for agent_type, reporters in agenttype_reporters.items():
                for name, reporter in reporters.items():
                    self._new_agenttype_reporter(agent_type, name, reporter)

        if tables is not None:
            for name, columns in tables.items():
                self._new_table(name, columns)

    def _validate_model_reporter(self, name, reporter, model):
        """Validate model reporter and handle validation results appropriately.

        Args:
            name: Name of the reporter
            reporter: Reporter definition (lambda/method/attribute/function list)
            model: Model instance

        Raises:
            ValueError: If reporter is None or has invalid format
            AttributeError: If model attribute doesn't exist
            TypeError: If reporter type is not supported
            RuntimeError: If reporter execution fails
        """
        self._validated = True  # put the change of signal firstly avoid losing efficacy

        # Type 1: Lambda function
        if isinstance(reporter, types.LambdaType):
            try:
                reporter(model)
            except Exception as e:
                raise RuntimeError(
                    f"Lambda reporter '{name}' failed validation: {e!s}\n"
                    f"Example: lambda m: len(m.agents)"
                ) from e

        # Type 2: Method of class/instance
        if not callable(reporter) and not isinstance(reporter, types.LambdaType):
            pass

        # Type 3: Model attribute (string)
        if isinstance(reporter, str):
            try:
                if not hasattr(model, reporter):
                    raise AttributeError(
                        f"Model reporter '{name}' references non-existent attribute '{reporter}'\n"
                    )
                getattr(model, reporter)  # 验证属性是否可访问
            except AttributeError as e:
                raise AttributeError(
                    f"Model reporter '{name}' attribute validation failed: {e!s}\n"
                ) from e

        # Type 4: Function with parameters in list
        if isinstance(reporter, list) and (not reporter or not callable(reporter[0])):
            raise ValueError(
                f"Invalid function list format for reporter '{name}'\n"
                f"Expected: [function, [param1, param2]], got: {reporter}"
            )

    def _new_model_reporter(self, name, reporter):
        """Add a new model-level reporter to collect.

        Args:
            name: Name of the model-level variable to collect.
            reporter: Can be one of four types:
                1. Attribute name (str): "attribute_name"
                2. Lambda function: lambda m: len(m.agents)
                3. Method: model.get_count or Model.get_count
                4. List of [function, [parameters]]
        """
        self.model_reporters[name] = reporter
        self.model_vars[name] = []

    def _new_agent_reporter(self, name, reporter):
        """Add a new agent-level reporter to collect.

        Args:
            name: Name of the agent-level variable to collect.
            reporter: Attribute string, function object, method of a class/instance, or
                      function with parameters placed in a list that returns the
                      variable when given an agent instance.
        """
        # Check if the reporter is an attribute string
        if isinstance(reporter, str):
            attribute_name = reporter

            def attr_reporter(agent):
                return getattr(agent, attribute_name, None)

            reporter = attr_reporter

        # Check if the reporter is a function with arguments placed in a list
        elif isinstance(reporter, list):
            func, params = reporter[0], reporter[1]

            def func_with_params(agent):
                return func(agent, *params)

            reporter = func_with_params

        # For other types (like lambda functions, method of a class/instance),
        # it's already suitable to be used as a reporter directly.

        self.agent_reporters[name] = reporter

    def _new_agenttype_reporter(self, agent_type, name, reporter):
        """Add a new agent-type-level reporter to collect.

        Args:
            agent_type: The type of agent to collect data for.
            name: Name of the agent-type-level variable to collect.
            reporter: Attribute string, function object, method of a class/instance, or
                      function with parameters placed in a list that returns the
                      variable when given an agent instance.
        """
        if agent_type not in self.agenttype_reporters:
            self.agenttype_reporters[agent_type] = {}

        # Use the same logic as _new_agent_reporter
        if isinstance(reporter, str):
            attribute_name = reporter

            def attr_reporter(agent):
                return getattr(agent, attribute_name, None)

            reporter = attr_reporter

        elif isinstance(reporter, list):
            func, params = reporter[0], reporter[1]

            def func_with_params(agent):
                return func(agent, *params)

            reporter = func_with_params

        self.agenttype_reporters[agent_type][name] = reporter

    def _new_table(self, table_name, table_columns):
        """Add a new table that objects can write to.

        Args:
            table_name: Name of the new table.
            table_columns: List of columns to add to the table.
        """
        new_table = {column: [] for column in table_columns}
        self.tables[table_name] = new_table

    def _record_agents(self, model):
        """Record agents data in a mapping of functions and agents."""
        rep_funcs = self.agent_reporters.values()

        def get_reports(agent):
            _prefix = (agent.model.steps, agent.unique_id)
            reports = tuple(rep(agent) for rep in rep_funcs)
            return _prefix + reports

        agent_records = map(get_reports, model.agents)
        return agent_records

    def _record_agenttype(self, model, agent_type):
        """Record agent-type data in a mapping of functions and agents."""
        rep_funcs = self.agenttype_reporters[agent_type].values()

        def get_reports(agent):
            _prefix = (agent.model.steps, agent.unique_id)
            reports = tuple(rep(agent) for rep in rep_funcs)
            return _prefix + reports

        agent_types = model.agent_types
        if agent_type in agent_types:
            agents = model.agents_by_type[agent_type]
        else:
            from mesa import Agent

            if issubclass(agent_type, Agent):
                agents = [
                    agent for agent in model.agents if isinstance(agent, agent_type)
                ]
            else:
                # Raise error if agent_type is not in model.agent_types
                raise ValueError(
                    f"Agent type {agent_type} is not recognized as an Agent type in the model or Agent subclass. Use an Agent (sub)class, like {agent_types}."
                )

        agenttype_records = map(get_reports, agents)
        return agenttype_records

    def collect(self, model):
        """Collect all the data for the given model object."""
        if self.model_reporters:
            if not self._validated:
                for name, reporter in self.model_reporters.items():
                    self._validate_model_reporter(name, reporter, model)

            for var, reporter in self.model_reporters.items():
                # Check if lambda or partial function
                if isinstance(reporter, types.LambdaType | partial):
                    # Use deepcopy to store a copy of the data,
                    # preventing references from being updated across steps.
                    self.model_vars[var].append(deepcopy(reporter(model)))
                # Check if model attribute
                elif isinstance(reporter, str):
                    self.model_vars[var].append(
                        deepcopy(getattr(model, reporter, None))
                    )
                # Check if function with arguments
                elif isinstance(reporter, list):
                    self.model_vars[var].append(deepcopy(reporter[0](*reporter[1])))
                # Assume it's a callable otherwise (e.g., method)
                else:
                    self.model_vars[var].append(deepcopy(reporter()))

        if self.agent_reporters:
            agent_records = self._record_agents(model)
            self._agent_records[model.steps] = list(agent_records)

        if self.agenttype_reporters:
            self._agenttype_records[model.steps] = {}
            for agent_type in self.agenttype_reporters:
                agenttype_records = self._record_agenttype(model, agent_type)
                self._agenttype_records[model.steps][agent_type] = list(
                    agenttype_records
                )

    def add_table_row(self, table_name, row, ignore_missing=False):
        """Add a row dictionary to a specific table.

        Args:
            table_name: Name of the table to append a row to.
            row: A dictionary of the form {column_name: value...}
            ignore_missing: If True, fill any missing columns with Nones;
                            if False, throw an error if any columns are missing
        """
        if table_name not in self.tables:
            raise Exception("Table does not exist.")

        for column in self.tables[table_name]:
            if column in row:
                self.tables[table_name][column].append(row[column])
            elif ignore_missing:
                self.tables[table_name][column].append(None)
            else:
                raise Exception("Could not insert row with missing column")

    def get_model_vars_dataframe(self):
        """Create a pandas DataFrame from the model variables.

        The DataFrame has one column for each model variable, and the index is
        (implicitly) the model tick.
        """
        # Check if self.model_reporters dictionary is empty, if so raise warning
        if not self.model_reporters:
            raise UserWarning(
                "No model reporters have been defined in the DataCollector, returning empty DataFrame."
            )

        return pd.DataFrame(self.model_vars)

    def get_agent_vars_dataframe(self):
        """Create a pandas DataFrame from the agent variables.

        The DataFrame has one column for each variable, with two additional
        columns for tick and agent_id.
        """
        # Check if self.agent_reporters dictionary is empty, if so raise warning
        if not self.agent_reporters:
            raise UserWarning(
                "No agent reporters have been defined in the DataCollector, returning empty DataFrame."
            )

        all_records = itertools.chain.from_iterable(self._agent_records.values())
        rep_names = list(self.agent_reporters)

        df = pd.DataFrame.from_records(
            data=all_records,
            columns=["Step", "AgentID", *rep_names],
            index=["Step", "AgentID"],
        )
        return df

    def get_agenttype_vars_dataframe(self, agent_type):
        """Create a pandas DataFrame from the agent-type variables for a specific agent type.

        The DataFrame has one column for each variable, with two additional
        columns for tick and agent_id.

        Args:
            agent_type: The type of agent to get the data for.
        """
        # Check if self.agenttype_reporters dictionary is empty for this agent type, if so return empty DataFrame
        if agent_type not in self.agenttype_reporters:
            warnings.warn(
                f"No agent-type reporters have been defined for {agent_type} in the DataCollector, returning empty DataFrame.",
                UserWarning,
                stacklevel=2,
            )
            return pd.DataFrame()

        all_records = itertools.chain.from_iterable(
            records[agent_type]
            for records in self._agenttype_records.values()
            if agent_type in records
        )
        rep_names = list(self.agenttype_reporters[agent_type])

        df = pd.DataFrame.from_records(
            data=all_records,
            columns=["Step", "AgentID", *rep_names],
            index=["Step", "AgentID"],
        )
        return df

    def get_table_dataframe(self, table_name):
        """Create a pandas DataFrame from a particular table.

        Args:
            table_name: The name of the table to convert.
        """
        if table_name not in self.tables:
            raise Exception("No such table.")
        return pd.DataFrame(self.tables[table_name])
