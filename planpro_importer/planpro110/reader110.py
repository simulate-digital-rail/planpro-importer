from .signalreader import SignalReader
from pathlib import Path
from datetime import datetime

from yaramo.model import DbrefGeoNode, Edge, Node, Route, Signal, Topology

from .model110 import parse
from .nodereader import NodeReader


class PlanProReader110(object):

    def __init__(self, plan_pro_file_name):
        if not plan_pro_file_name.endswith(".ppxml"):
            plan_pro_file_name = plan_pro_file_name + ".ppxml"
        self.plan_pro_file_name = plan_pro_file_name
        self.root_object = parse(self.plan_pro_file_name, silence=True)

        self.topology = Topology(name=Path(self.plan_pro_file_name).stem)
        self.topology.created_at = self._get_created_at()
        self.topology.created_with = self._get_created_with()

    def _get_created_at(self) -> datetime:
        """Gets the date object, when the PlanPro was created

        :return: The date object
        """
        return self.root_object.PlanPro_Schnittstelle_Allg.Erzeugung_Zeitstempel.Wert

    def _get_created_with(self) -> str:
        """Gets a string containing the name of the tool and the version of the tool.

        :return: The tool string (name and version)
        """
        common_interface = self.root_object.PlanPro_Schnittstelle_Allg
        tool = common_interface.Werkzeug_Name.Wert
        version = common_interface.Werkzeug_Version.Wert
        return f"{tool} (Version: {version})"

    def read_topology_from_plan_pro_file(self):
        container = self._get_container()

        for _container in container:
            node_reader = NodeReader(self.topology, _container)
            node_reader.read_nodes()
            self.read_edges_from_container(_container)
            node_reader.add_point_names()
        for _container in container:
            self.read_signals_from_container(_container)
        for _container in container:
            self.read_routes_from_container(_container)

        return self.topology

    def _get_container(self):
        container = []

        if self.root_object.LST_Planung is not None:
            container.extend(
                fd.LST_Zustand_Ziel.Container
                for fd in self.root_object.LST_Planung.Fachdaten.Ausgabe_Fachdaten
            )
        if self.root_object.LST_Zustand is not None:
            container.append(self.root_object.LST_Zustand.Container)

        if not container:
            raise ImportError("No PlanPro-data found")

        return container

    def read_edges_from_container(self, container):
        for top_kante in container.TOP_Kante:
            top_kante_uuid = top_kante.Identitaet.Wert
            node_a = self.topology.nodes[top_kante.ID_TOP_Knoten_A.Wert]
            node_b = self.topology.nodes[top_kante.ID_TOP_Knoten_B.Wert]

            # Anschluss
            def _set_connection(_anschluss, _cur_node, _other_node):
                if _anschluss == "Links":
                    _cur_node.set_connection_left(_other_node)
                elif _anschluss == "Rechts":
                    _cur_node.set_connection_right(_other_node)
                else:
                    _cur_node.set_connection_head(_other_node)

            _set_connection(
                top_kante.TOP_Kante_Allg.TOP_Anschluss_A.Wert, node_a, node_b
            )
            _set_connection(
                top_kante.TOP_Kante_Allg.TOP_Anschluss_B.Wert, node_b, node_a
            )

            length = float(top_kante.TOP_Kante_Allg.TOP_Laenge.Wert)
            length_remaining = length

            # Intermediate geo nodes
            geo_edges = self.get_all_geo_edges_by_top_edge_uuid(
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

            second_previous_node_uuid = node_a.geo_node.uuid
            previous_node_uuid = _get_other_uuid(node_a.geo_node.uuid, first_edge)
            geo_nodes_in_order = []

            def _get_next_edge(_previous_node_uuid, _second_previous_node_uuid):
                for _geo_edge in geo_edges:
                    if _previous_node_uuid in [
                        _geo_edge.ID_GEO_Knoten_A.Wert,
                        _geo_edge.ID_GEO_Knoten_B.Wert,
                    ]:
                        if _second_previous_node_uuid not in [
                            _geo_edge.ID_GEO_Knoten_A.Wert,
                            _geo_edge.ID_GEO_Knoten_B.Wert,
                        ]:
                            return _geo_edge
                return None

            completed = True
            while previous_node_uuid != node_b.geo_node.uuid:
                x, y = NodeReader.get_coordinates_of_geo_node(container, previous_node_uuid)
                geo_node = DbrefGeoNode(x, y, uuid=previous_node_uuid)
                geo_nodes_in_order.append(geo_node)

                next_edge = _get_next_edge(previous_node_uuid, second_previous_node_uuid)
                if next_edge is None:
                    completed = False
                    break
                second_previous_node_uuid = previous_node_uuid
                length_remaining = length_remaining - float(
                    next_edge.GEO_Kante_Allg.GEO_Laenge.Wert
                )
                previous_node_uuid = _get_other_uuid(second_previous_node_uuid, next_edge)

            if completed:
                edge = Edge(node_a, node_b, length=length, uuid=top_kante_uuid)
                edge.intermediate_geo_nodes = geo_nodes_in_order
                self.topology.add_edge(edge)
            else:
                print(
                    f"Warning: TOP_EDGE {top_kante_uuid} could not be completed, "
                    f"since the chain of geo edges is broken after {previous_node_uuid}. "
                    "This may cause errors later, since the topology is broken."
                )

    def read_signals_from_container(self, container):
        reader = SignalReader(self.topology, container)
        return reader.read_signals_from_container()

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
            edges = []
            for teilbereich in fstr_fahrweg.Bereich_Objekt_Teilbereich:
                edge_uuid = teilbereich.ID_TOP_Kante.Wert
                if edge_uuid in self.topology.edges:
                    edges.append(self.topology.edges[edge_uuid])

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

    def get_all_geo_edges_by_top_edge_uuid(self, container, top_edge_uuid):
        geo_edges = container.GEO_Kante
        result = []
        for geo_edge in geo_edges:
            if geo_edge.ID_GEO_Art.Wert == top_edge_uuid:
                result.append(geo_edge)
        return result
