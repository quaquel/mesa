import pandas as pd

from mesa.agent import AgentSet

class BaseCollector():
    def __init__(self, name, object, attributes=None, callable=None):
        super().__init__()

        if isinstance(attributes, str):
            attributes = [attributes,]

        self.name = name
        self.object = object
        self.attributes = attributes
        self.callable = callable
        self.data_over_time = []

    def collect(self):
        data = {attribute:getattr(object, attribute) for attribute in self.attributes}
        if self.callable is not None:
            data = self.callable(data)
        self.data_over_time.append(data)

    def to_dataframe(self):
        return pd.DataFrame(data=self.data_over_time)


class AgentSetCollector(BaseCollector):
    def __init__(self, name, object, attributes=None, callable=None):
        super().__init__(name, object, attributes, callable)
        self.attributes.append('unique_id')

    def collect(self):
        # data = {attribute:self.object.get(attribute) for attribute in self.attributes}
        data = [dict(zip(self.attributes, entry)) for entry in self.object.get(self.attributes)]
        if self.callable is not None:
            data = self.callable(data)
        self.data_over_time.append(data)


class ObserverCollector:
    def __init__(self, name, object, event, state=None, callable=None):
        super().__init__()
        self.name = name
        self.object = object
        self.state = state
        self.callable = callable
        self.event = event

        self.object.subscribe(self, event)
        self.data = []
        self.data_over_time = []

    def handle_event(self, subject, state):
        if state == self.state:
            self.data = getattr(subject, state)

    def collect(self):
        self.data_over_time.append(self.data)

    def to_dataframe(self):
        return pd.DataFrame(data=self.data_over_time)


class DataCollector:
    def __init__(self, collectors=None):
        super().__init__()
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
        for collector in self.collectors.values():
            collector.collect()



def collect_from(name, object, attributes, callable=None):
    if isinstance(object, AgentSet):
        return AgentSetCollector(name, object, attributes, callable)
    else:
        return BaseCollector(name, object, attributes, callable)