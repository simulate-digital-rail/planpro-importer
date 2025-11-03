from yaramo.model import DbrefGeoNode

class Utils:

    @staticmethod
    def get_coordinates_of_geo_node(container, uuid: str):
        """Gets the coordinates of a geo node.

        :param container: The container
        :param uuid: The uuid of the geo node
        :return: The coordinates (x, y)
        """
        geo_point = Utils.get_geo_point_by_geo_node_uuid(container, uuid)
        if geo_point is None:
            return None, None, None, None
        x = float(geo_point.GEO_Punkt_Allg.GK_X.Wert)
        y = float(geo_point.GEO_Punkt_Allg.GK_Y.Wert)
        source = str(geo_point.GEO_Punkt_Allg.Plan_Quelle.Wert)

        try:
            coordinate_system = geo_point.GEO_Punkt_Allg.GEO_Koordinatensystem.Wert
        except AttributeError:
            coordinate_system = geo_point.GEO_Punkt_Allg.GEO_KoordinatenSystem_LSys.Wert

        return x, y, source, coordinate_system

    @staticmethod
    def get_geo_point_by_geo_node_uuid(container, uuid: str):
        """Gets the geo point of a geo node.

        :param container: The container
        :param uuid: The uuid of the geo node
        :return: The geo point
        """
        geo_points = container.GEO_Punkt
        for geo_point in geo_points:
            if geo_point.ID_GEO_Knoten is None:
                continue
            if geo_point.ID_GEO_Knoten.Wert == uuid:
                return geo_point
        return None

    @staticmethod
    def get_all_geo_edges_by_top_edge_uuid(container, top_edge_uuid):
        geo_edges = container.GEO_Kante
        result = []
        for geo_edge in geo_edges:
            if geo_edge.ID_GEO_Art.Wert == top_edge_uuid:
                result.append(geo_edge)
        return result

    @staticmethod
    def get_container(root_object):
        container = []

        if root_object.LST_Planung is not None:
            container.extend(
                fd.LST_Zustand_Ziel.Container
                for fd in root_object.LST_Planung.Fachdaten.Ausgabe_Fachdaten
            )
        if root_object.LST_Zustand is not None:
            container.append(root_object.LST_Zustand.Container)

        if not container:
            raise ImportError("No PlanPro-data found")

        return container

    @staticmethod
    def set_connection(anschluss, cur_node, edge):
        if anschluss == "Links":
            cur_node.set_connection_left_edge(edge)
        elif anschluss == "Rechts":
            cur_node.set_connection_right_edge(edge)
        else:
            cur_node.set_connection_head_edge(edge)

    @staticmethod
    def get_intermediate_geo_nodes_of_geo_edge(container, edge, last_node_uuid, geo_converter):
        if geo_converter is not None:
            geo_point_a = Utils.get_geo_point_by_geo_node_uuid(container, edge.ID_GEO_Knoten_A.Wert)
            geo_point_b = Utils.get_geo_point_by_geo_node_uuid(container, edge.ID_GEO_Knoten_B.Wert)
            inter_geo_nodes = geo_converter.get_intermediate_geo_nodes_of_geo_edge(edge, geo_point_a, geo_point_b)
            x, y, source, coordinate_system = Utils.get_coordinates_of_geo_node(container, last_node_uuid)
            last_geo_node = DbrefGeoNode(x, y, data_source=source, dbref_crs=coordinate_system)

            if len(inter_geo_nodes) <= 1:
                return inter_geo_nodes

            if (last_geo_node.get_distance_to_other_geo_node(inter_geo_nodes[0]) <
                    last_geo_node.get_distance_to_other_geo_node(inter_geo_nodes[-1])):
                return inter_geo_nodes
            elif (last_geo_node.get_distance_to_other_geo_node(inter_geo_nodes[0]) >
                  last_geo_node.get_distance_to_other_geo_node(inter_geo_nodes[-1])):
                return reversed(inter_geo_nodes)
            else:
                raise ValueError(f"Inter geo nodes have same distance from last node.")
        return []
