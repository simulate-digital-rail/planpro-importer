import logging

from yaramo.model import DbrefGeoNode, Node, Topology

from .model110 import CContainer
from ..utils import Utils


class NodeReader:

    def __init__(self, topology: Topology, container: CContainer):
        """The node reader reads all nodes from a container and adds them
        to the topology.

        :param topology: The topology
        :param container: The container
        """
        self.topology: Topology = topology
        self.container: CContainer = container

    def read_nodes(self):
        """Read the nodes from the container."""

        for top_knoten in self.container.TOP_Knoten:
            node_obj = Node(uuid=top_knoten.Identitaet.Wert)

            # Coordinates
            geo_node_uuid = top_knoten.ID_GEO_Knoten.Wert
            x, y, source, coordinate_system = Utils.get_coordinates_of_geo_node(self.container, geo_node_uuid)
            if x is None or y is None:
                continue
            node_obj.geo_node = DbrefGeoNode(x, y, data_source=source, dbref_crs=coordinate_system, uuid=geo_node_uuid)

            self.topology.add_node(node_obj)

    def add_point_names(self):
        """Add the names of the points to the points. If there is no name defined,
        it will use the last five characters of the UUID."""

        for point_element in self.container.W_Kr_Gsp_Element:
            element_uuid = point_element.Identitaet.Wert
            point_name = point_element.Bezeichnung.Bezeichnung_Aussenanlage.Wert
            component = self.get_component_by_element_uuid(element_uuid)
            point = self.get_point_of_component(component)
            if point is not None:
                point.name = point_name

        # Set default names for the rest
        for node in self.topology.nodes.values():
            if node.name is None:
                node.name = node.uuid[-5:]

    def get_drive_amounts(self):
        """Gets the drive amount of a point by its uuid."""
        w_kr_components = self.container.W_Kr_Gsp_Komponente
        for w_kr_component in w_kr_components:
            w_kr_element_uuid = w_kr_component.ID_W_Kr_Gsp_Element.Wert
            w_kr_element = self.get_component_by_element_uuid(w_kr_element_uuid)
            w_kr_element_point = self.get_point_of_component(w_kr_element)
            w_kr_zungenpaar = w_kr_component.Zungenpaar
            if w_kr_zungenpaar is not None:
                w_kr_drive = w_kr_zungenpaar.Elektrischer_Antrieb_Anzahl.Wert
                w_kr_element_point.drive_amount = w_kr_drive


    def get_component_by_element_uuid(self, element_uuid: str):
        """Gets the point component (W_Kr_Gsp_Komponente) by the
        point element uuid

        :param element_uuid: The element uuid
        :return: The point component
        """
        for point_component in self.container.W_Kr_Gsp_Komponente:
            if point_component.ID_W_Kr_Gsp_Element.Wert == element_uuid:
                return point_component
        return None

    def get_point_of_component(self, component):
        """Gets the point, the TOP node, described by the component. Returns None,
        if some error occurs.

        :param component: The point component
        :return: The top node or None.
        """
        point = None
        for top_edge_xml in component.Punkt_Objekt_TOP_Kante:
            top_edge_uuid = top_edge_xml.ID_TOP_Kante.Wert
            if top_edge_uuid not in self.topology.edges:
                logging.error(
                    f"TOP_Kante with UUID {top_edge_uuid} not found during "
                    f"setting the point names"
                )
                return None
            top_edge = self.topology.edges[top_edge_uuid]
            distance = float(top_edge_xml.Abstand.Wert)
            point_on_top_edge = None
            if distance == 0.0:
                point_on_top_edge = top_edge.node_a
            elif top_edge.length == distance:
                point_on_top_edge = top_edge.node_b
            else:
                # This case can happen when there is a lock-object. Ignore these.
                return None

            if point is None:
                point = point_on_top_edge
            elif point.uuid != point.uuid:
                logging.error(
                    f"Point component {component.Identitaet.Wert} points to different "
                    f"TOP_Knoten."
                )
                return None
        return point
