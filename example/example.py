from planpro_importer import PlanProVersion, import_planpro

print(__name__)

if __name__ == "__main__":
    # Test 1.9
    topology = import_planpro("joehstadt.ppxml", PlanProVersion.PlanPro19)
    print(f"{len(topology.signals)}")

    # Test 1.10
    topology = import_planpro("forchheim.ppxml", PlanProVersion.PlanPro110)
    print(f"{len(topology.signals)}")