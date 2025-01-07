from planpro_importer import PlanProVersion, import_planpro


def read_19():
    # Test 1.9
    topology = import_planpro("filename.ppxml", PlanProVersion.PlanPro19)
    print(f"{len(topology.edges)}")
    print(f"{len(topology.nodes)}")
    print(f"{len(topology.signals)}")
    print(f"{len(topology.routes)}")


def read_110():
    # Test 1.10
    topology = import_planpro("filename.ppxml", PlanProVersion.PlanPro110)
    print(f"{len(topology.edges)}")
    print(f"{len(topology.nodes)}")
    print(f"{len(topology.signals)}")
    print(f"{len(topology.routes)}")


if __name__ == "__main__":
    read_19()
    read_110()

