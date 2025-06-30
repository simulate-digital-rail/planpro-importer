from datetime import datetime
from pathlib import Path

from yaramo.model import DbrefGeoNode, Edge, Node, Route, Signal, Topology, Track

from .model110 import parse
from .nodereader import NodeReader
from .signalreader import SignalReader
from ..utils import Utils
from ..routereader import RouteReader


class PlanProReader110(object):

    def __init__(self, plan_pro_file_name, geo_converter=None):
        if not plan_pro_file_name.endswith(".ppxml"):
            plan_pro_file_name = plan_pro_file_name + ".ppxml"
        self.plan_pro_file_name = plan_pro_file_name
        self.geo_converter = geo_converter
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
        container = Utils.get_container(self.root_object)

        for _container in container:
            node_reader = NodeReader(self.topology, _container)
            node_reader.read_nodes()
            self.read_edges_from_container(_container)
            node_reader.add_point_names()
            node_reader.get_drive_amounts()
        for _container in container:
            reader = SignalReader(self.topology, _container)
            reader.read_signals_from_container()
        for _container in container:
            RouteReader.read_routes_from_container(_container, self.topology)

        return self.topology

    def read_edges_from_container(self, container):
        for top_kante in container.TOP_Kante:
            top_kante_uuid = top_kante.Identitaet.Wert
            length = float(top_kante.TOP_Kante_Allg.TOP_Laenge.Wert)
            node_a = self.topology.nodes[top_kante.ID_TOP_Knoten_A.Wert]
            node_b = self.topology.nodes[top_kante.ID_TOP_Knoten_B.Wert]
            edge = Edge(node_a, node_b, length=length, uuid=top_kante_uuid)

            # Anschluss
            Utils.set_connection(top_kante.TOP_Kante_Allg.TOP_Anschluss_A.Wert, node_a, edge)
            Utils.set_connection(top_kante.TOP_Kante_Allg.TOP_Anschluss_B.Wert, node_b, edge)

            length_remaining = length

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

            second_previous_node_uuid = node_a.geo_node.uuid
            previous_node_uuid = _get_other_uuid(node_a.geo_node.uuid, first_edge)
            geo_nodes_in_order = []
            geo_nodes_in_order.extend(Utils.get_intermediate_geo_nodes_of_geo_edge(container, first_edge, second_previous_node_uuid, self.geo_converter))

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
                x, y = Utils.get_coordinates_of_geo_node(
                    container, previous_node_uuid
                )
                geo_node = DbrefGeoNode(x, y, uuid=previous_node_uuid)
                geo_nodes_in_order.append(geo_node)

                next_edge = _get_next_edge(
                    previous_node_uuid, second_previous_node_uuid
                )
                if next_edge is None:
                    completed = False
                    break

                geo_nodes_in_order.extend(Utils.get_intermediate_geo_nodes_of_geo_edge(container, next_edge, previous_node_uuid, self.geo_converter))

                second_previous_node_uuid = previous_node_uuid
                length_remaining = length_remaining - float(
                    next_edge.GEO_Kante_Allg.GEO_Laenge.Wert
                )
                previous_node_uuid = _get_other_uuid(
                    second_previous_node_uuid, next_edge
                )

            if completed:
                edge.intermediate_geo_nodes = geo_nodes_in_order
                self.topology.add_edge(edge)
            else:
                print(
                    f"Warning: TOP_EDGE {top_kante_uuid} could not be completed, "
                    f"since the chain of geo edges is broken after {previous_node_uuid}. "
                    "This may cause errors later, since the topology is broken."
                )
                node_a.remove_edge(edge)
                node_b.remove_edge(edge)

        for track in container.Gleis_Art:
            uuid = track.Identitaet.Wert
            track_type = track.Gleisart.Wert
            track_obj = Track(track_type, uuid=uuid)
            for section in track.Bereich_Objekt_Teilbereich:
                section_start = section.Begrenzung_A.Wert
                section_end = section.Begrenzung_B.Wert
                section_edge = self.topology.edges[section.ID_TOP_Kante.Wert]
                track_obj.add_edge_section(section_edge, section_start, section_end)
            self.topology.add_track(track_obj)
