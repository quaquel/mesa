from typing import Any, Callable, List
import itertools

import pandas as pd

from mesa.agent import AgentSet


class BaseCollector:
    def __init__(self, name:str, obj: Any, attributes: str|List[str]=None, callable: Callable=None, column_names: List[str]=None):
        """

        Args
        name : name of the collector
        obj : object
        attributes :
        callable : callable
        column_names : list of column names, optional, defaults to attributes

        """
        super().__init__()

        if isinstance(attributes, str):
            attributes = [attributes,]

        self.name = name
        self.obj = obj
        self.attributes = attributes
        self.callable = callable
        self.column_names = column_names
        self.data_over_time = {}

    def collect(self, time):
        if self.attributes is None:
            data = self._collect_callable()
        else:
            data = self._collect_data()
        self.data_over_time[time] = data

    def _collect_data(self):
        data = {attribute:getattr(self.obj, attribute) for attribute in self.attributes}
        if self.callable is not None:
            data = self.callable(data)
        return data

    def _collect_callable(self):
        return self.callable(self.obj)


    def to_dataframe(self):
        # couple of workflows
        # problem is the distinction btween the data we collect, and what we want to return
        # so column name is either attributes
        # or name, or even something else if callable does funky stuff
        # so we need meaningful defaults and a way to override them

        if self.column_names is not None:
            columns = self.column_names
        elif self.callable is not None:
            columns = [self.name]
        else:
            columns = self.attributes

        return pd.DataFrame.from_dict(self.data_over_time , orient="index", columns=columns)


class AgentSetCollector(BaseCollector):
    def __init__(self, name, obj, attributes=None, callable=None, column_names=None):
        super().__init__(name, obj, attributes, callable, column_names)
        self.attributes.append("unique_id")

    def collect(self, time):
        if self.attributes is None:
            data = self._collect_callable()
        else:
            data = self._collect_data(time)
        self.data_over_time[time] = data

    def _collect_data(self, time):
        data = [dict(zip(self.attributes, entry), time=time) for entry in self.obj.get(self.attributes)]
        if self.callable is not None:
            data = self.callable(data)
        return data

    def _collect_callable(self):
        return self.callable(self.obj)

    def to_dataframe(self):
        # couple of workflows
        # problem is the distinction btween the data we collect, and what we want to return
        # so column name is either attributes
        # or name, or even something else if callable does funky stuff
        # so we need meaningful defaults and a way to override them

        # all_records = itertools.chain.from_iterable(self._agent_records.values())
        # rep_names = list(self.agent_reporters)
        #
        # df = pd.DataFrame.from_records(
        #     data=all_records,
        #     columns=["Step", "AgentID", *rep_names],
        #     index=["Step", "AgentID"],
        # )
        # FIXME::
        if self.callable is not None:
            return super().to_dataframe()

        all_records = itertools.chain.from_iterable(self.data_over_time.values())

        df = pd.DataFrame.from_records(
            data=all_records,
            columns=["time", *self.attributes],
            index=["time", "unique_id"],
        )
        # FIXME::
        return df


class ObserverCollector:
    def __init__(self, name, obj, event, state=None, callable=None):
        super().__init__()
        self.name = name
        self.obj = obj
        self.state = state
        self.callable = callable
        self.event = event

        self.obj.subscribe(self, event)
        self.data = []
        self.data_over_time = {}

    def handle_event(self, subject, state):
        if state == self.state:
            self.data = getattr(subject, state)

    def collect(self, time):
        self.data_over_time[time] = self.data

    def to_dataframe(self):
        return pd.DataFrame(data=self.data_over_time)


class DataCollector:
    def __init__(self, model, collectors=None):
        super().__init__()
        self.model = model
        self.collectors = {}

        if collectors is not None:
            for collector in collectors:
                self.add_collector(collector)

    def add_collector(self, collector):
        self.collectors[collector.name] = collector
        setattr(self, collector.name, collector)

    def remove_collector(self, collector):
        self.collectors.pop(collector.name)
        delattr(self, collector.name)

    def collect_all(self):
        time = self.model.time
        for collector in self.collectors.values():
            collector.collect(time)



def collect_from(name, object, attributes, callable=None):
    if isinstance(object, AgentSet):
        return AgentSetCollector(name, object, attributes, callable)
    else:
        return BaseCollector(name, object, attributes, callable)
