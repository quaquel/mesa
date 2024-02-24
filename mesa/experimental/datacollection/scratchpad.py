class Measure:

    def __init__(self, model, identifier, *args, **kwargs):
        self.model = model
        self.identifier = identifier

    def get_value(self):
        return getattr(self.model, self.identifier)


class MeasureDescriptor:
    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = "_" + name

    def __get__(self, obj, owner):
        return getattr(obj, self.private_name).get_value()

    def __set__(self, obj, value):
        setattr(obj, self.private_name, value)


class Model:

    def __setattr__(self, name, value):
        if isinstance(value, Measure) and not name.startswith("_"):
            klass = type(self)
            descr = MeasureDescriptor()
            descr.__set_name__(klass, name)
            setattr(klass, name, descr)
            descr.__set__(self, value)
        else:
            super().__setattr__(name, value)

    def __init__(self, identifier, *args, **kwargs):
        self.gini = Measure(self, "identifier")
        self.identifier = identifier


if __name__ == "__main__":
    model1 = Model(1)
    model2 = Model(2)
    print(model1.gini)
    print(model2.gini)
