from .planpro19 import PlanProReader19
from .planpro110 import PlanProReader110
from .planproversion import PlanProVersion
from yaramo.model import Topology


def import_planpro(planpro_file: str, planpro_version: PlanProVersion = PlanProReader19) -> Topology:
    reader = None
    if planpro_version == PlanProVersion.PlanPro19:
        reader = PlanProReader19(planpro_file)
    if planpro_version == PlanProVersion.PlanPro110:
        reader = PlanProReader110(planpro_file)
    return reader.read_topology_from_plan_pro_file()
