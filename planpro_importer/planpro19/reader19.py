from yaramo.model import DbrefGeoNode, Edge, Node, Route, Signal, Topology
from ..utils import Utils
from .model19 import parse
from ..routereader import RouteReader


class PlanProReader19(object):

    def __init__(self, plan_pro_file_name, geo_converter = None):
        if not plan_pro_file_name.endswith(".ppxml"):
            plan_pro_file_name = plan_pro_file_name + ".ppxml"
        self.plan_pro_file_name = plan_pro_file_name
        self.geo_converter = geo_converter
        self.topology = Topology(name=self.plan_pro_file_name.split("/")[-1][:-6])

    def read_topology_from_plan_pro_file(self):
        root_object = parse(self.plan_pro_file_name, silence=True)
        container = Utils.get_container(root_object)

        for c in container:
            self.read_topology_from_container(c)
        for c in container:
            self.read_signals_from_container(c)
        for c in container:
            RouteReader.read_routes_from_container(c, self.topology)

        return self.topology

    def read_topology_from_container(self, container):
        for top_knoten in container.TOP_Knoten:
            top_knoten_uuid = top_knoten.Identitaet.Wert
            node_obj = Node(uuid=top_knoten_uuid)

            # Coordinates
            geo_node_uuid = top_knoten.ID_GEO_Knoten.Wert
            x, y = Utils.get_coordinates_of_geo_node(container, geo_node_uuid)
            if x is None or y is None:
                continue
            node_obj.geo_node = DbrefGeoNode(x, y, uuid=geo_node_uuid)

            self.topology.add_node(node_obj)

        for top_kante in container.TOP_Kante:
            top_kante_uuid = top_kante.Identitaet.Wert
            length = top_kante.TOP_Kante_Allg.TOP_Laenge.Wert
            node_a = self.topology.nodes[top_kante.ID_TOP_Knoten_A.Wert]
            node_b = self.topology.nodes[top_kante.ID_TOP_Knoten_B.Wert]
            edge = Edge(node_a, node_b, length=length, uuid=top_kante_uuid)

            # Anschluss
            Utils.set_connection(top_kante.TOP_Kante_Allg.TOP_Anschluss_A.Wert, node_a, edge)
            Utils.set_connection(top_kante.TOP_Kante_Allg.TOP_Anschluss_B.Wert, node_b, edge)

            # Intermediate geo nodes
            geo_edges = Utils.get_all_geo_edges_by_top_edge_uuid(
                container, top_kante_uuid
            )

            first_edge = None
            for geo_edge in geo_edges:
                if node_a.geo_node.uuid in [
                    geo_edge.ID_GEO_Knoten_A.Wert,
                    geo_edge.ID_GEO_Knoten_B.Wert,
                ]:
                    first_edge = geo_edge
                    break

            def _get_other_uuid(_uuid, _edge):
                if _edge.ID_GEO_Knoten_A.Wert == _uuid:
                    return _edge.ID_GEO_Knoten_B.Wert
                return _edge.ID_GEO_Knoten_A.Wert

            second_last_node_uuid = node_a.geo_node.uuid
            last_node_uuid = _get_other_uuid(node_a.geo_node.uuid, first_edge)
            geo_nodes_in_order = []
            geo_nodes_in_order.extend(Utils.get_intermediate_geo_nodes_of_geo_edge(container, first_edge, second_last_node_uuid, self.geo_converter))

            def _get_next_edge(_last_node_uuid, _second_last_node):
                for _geo_edge in geo_edges:
                    if _last_node_uuid in [
                        _geo_edge.ID_GEO_Knoten_A.Wert,
                        _geo_edge.ID_GEO_Knoten_B.Wert,
                    ]:
                        if _second_last_node not in [
                            _geo_edge.ID_GEO_Knoten_A.Wert,
                            _geo_edge.ID_GEO_Knoten_B.Wert,
                        ]:
                            return _geo_edge
                return None

            while last_node_uuid != node_b.geo_node.uuid:
                x, y = Utils.get_coordinates_of_geo_node(container, last_node_uuid)
                geo_node = DbrefGeoNode(x, y, uuid=last_node_uuid)
                geo_nodes_in_order.append(geo_node)

                next_edge = _get_next_edge(last_node_uuid, second_last_node_uuid)
                geo_nodes_in_order.extend(Utils.get_intermediate_geo_nodes_of_geo_edge(container, next_edge, last_node_uuid, self.geo_converter))

                second_last_node_uuid = last_node_uuid
                last_node_uuid = _get_other_uuid(second_last_node_uuid, next_edge)

            edge.intermediate_geo_nodes = geo_nodes_in_order
            self.topology.add_edge(edge)

    def read_signals_from_container(self, container):
        for signal in container.Signal:
            signal_uuid = signal.Identitaet.Wert

            if (
                signal.Signal_Real is not None
                and signal.Signal_Real.Signal_Real_Aktiv is not None
            ):
                if (
                    len(signal.Punkt_Objekt_TOP_Kante) == 1
                ):  # If greater, no real signal with lights
                    if (
                        signal.Bezeichnung is not None
                        and signal.Bezeichnung.Bezeichnung_Aussenanlage is not None
                    ):
                        function = (
                            signal.Signal_Real.Signal_Real_Aktiv.Signal_Funktion.Wert
                        )
                        if (
                            function == "Einfahr_Signal"
                            or function == "Ausfahr_Signal"
                            or function == "Block_Signal"
                        ):
                            top_kante_id = signal.Punkt_Objekt_TOP_Kante[
                                0
                            ].ID_TOP_Kante.Wert
                            signal_obj = Signal(
                                uuid=signal_uuid,
                                function=function,
                                kind=signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signal_Art.Wert,
                                name=signal.Bezeichnung.Bezeichnung_Aussenanlage.Wert,
                                edge=self.topology.edges[top_kante_id],
                                direction=signal.Punkt_Objekt_TOP_Kante[
                                    0
                                ].Wirkrichtung.Wert,
                                side_distance=signal.Punkt_Objekt_TOP_Kante[
                                    0
                                ].Seitlicher_Abstand.Wert,
                                distance_edge=signal.Punkt_Objekt_TOP_Kante[
                                    0
                                ].Abstand.Wert,
                            )
                            self.topology.add_signal(signal_obj)
                            signal_obj.edge.signals.append(signal_obj)

    def read_routes_from_container(self, container):
        for fstr_fahrweg in container.Fstr_Fahrweg:
            fahrweg_uuid = str(fstr_fahrweg.Identitaet.Wert)

            # Maximum speed
            maximum_speed = None
            if fstr_fahrweg.Fstr_V_Hg is not None:
                maximum_speed = fstr_fahrweg.Fstr_V_Hg.Wert

            # Start and End signal
            start_signal = None
            end_signal = None
            start_signal_uuid = fstr_fahrweg.ID_Start.Wert
            end_signal_uuid = fstr_fahrweg.ID_Ziel.Wert
            if start_signal_uuid in self.topology.signals:
                start_signal = self.topology.signals[start_signal_uuid]
            if end_signal_uuid in self.topology.signals:
                end_signal = self.topology.signals[end_signal_uuid]
            if start_signal is None or end_signal is None:
                continue  # Start or end signal not found

            # Edges
            edges = set()
            for teilbereich in fstr_fahrweg.Bereich_Objekt_Teilbereich:
                edge_uuid = teilbereich.ID_TOP_Kante.Wert
                if edge_uuid in self.topology.edges:
                    edges.add(self.topology.edges[edge_uuid])

            # Build route
            route = Route(
                start_signal=start_signal,
                maximum_speed=maximum_speed,
                uuid=fahrweg_uuid,
                name=f"{start_signal.name}-{end_signal.name}",
            )
            route.end_signal = end_signal
            route.edges = edges
            self.topology.add_route(route)
