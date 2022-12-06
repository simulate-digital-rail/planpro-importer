from yaramo.model import Topology, Node, Signal, Edge
from planpro_importer import model


class PlanProReader(object):

    def __init__(self, plan_pro_file_name):
        if plan_pro_file_name.endswith(".ppxml"):
            self.plan_pro_file_name = plan_pro_file_name
        else:
            self.plan_pro_file_name = plan_pro_file_name + ".ppxml"
        self.topology = Topology()

    def read_topology_from_plan_pro_file(self):
        root_object = model.parse(self.plan_pro_file_name, silence=True)
        number_of_fachdaten = len(root_object.LST_Planung.Fachdaten.Ausgabe_Fachdaten)

        for id_of_fachdaten in range(0, number_of_fachdaten):
            container = root_object.LST_Planung.Fachdaten.Ausgabe_Fachdaten[id_of_fachdaten].LST_Zustand_Ziel.Container
            self.read_topology_from_container(container)

        for id_of_fachdaten in range(0, number_of_fachdaten):
            container = root_object.LST_Planung.Fachdaten.Ausgabe_Fachdaten[id_of_fachdaten].LST_Zustand_Ziel.Container
            self.read_signals_from_container(container)

        return self.topology

    def read_topology_from_container(self, container):
        for top_knoten in container.TOP_Knoten:
            top_knoten_uuid = top_knoten.Identitaet.Wert
            node_obj = Node(uuid=top_knoten_uuid)
            self.topology.add_node(node_obj)

        for top_kante in container.TOP_Kante:
            top_kante_uuid = top_kante.Identitaet.Wert
            node_a = self.topology.nodes[top_kante.ID_TOP_Knoten_A.Wert]
            node_b = self.topology.nodes[top_kante.ID_TOP_Knoten_B.Wert]

            # Anschluss A
            anschluss_a = top_kante.TOP_Kante_Allg.TOP_Anschluss_A.Wert
            if anschluss_a == "Links":
                node_a.set_connection_left(node_b)
            elif anschluss_a == "Rechts":
                node_a.set_connection_right(node_b)
            else:
                node_a.set_connection_head(node_b)

            # Anschluss B
            anschluss_b = top_kante.TOP_Kante_Allg.TOP_Anschluss_B.Wert
            if anschluss_b == "Links":
                node_b.set_connection_left(node_a)
            elif anschluss_b == "Rechts":
                node_b.set_connection_right(node_a)
            else:
                node_b.set_connection_head(node_a)

            length = top_kante.TOP_Kante_Allg.TOP_Laenge.Wert
            edge = Edge(node_a, node_b, length, uuid=top_kante_uuid)
            self.topology.add_edge(edge)

    def read_signals_from_container(self, container):
        for signal in container.Signal:
            signal_uuid = signal.Identitaet.Wert

            if signal.Signal_Real is not None and signal.Signal_Real.Signal_Real_Aktiv is not None:
                if len(signal.Punkt_Objekt_TOP_Kante) == 1:  # If greater, no real signal with lights
                    if signal.Bezeichnung is not None and signal.Bezeichnung.Bezeichnung_Aussenanlage is not None:
                        function = signal.Signal_Real.Signal_Real_Aktiv.Signal_Funktion.Wert
                        if function == "Einfahr_Signal" or function == "Ausfahr_Signal" or function == "Block_Signal":
                            top_kante_id = signal.Punkt_Objekt_TOP_Kante[0].ID_TOP_Kante.Wert
                            signal_obj = Signal(
                                uuid=signal_uuid,
                                function=function,
                                kind=signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signal_Art.Wert,
                                name=signal.Bezeichnung.Bezeichnung_Aussenanlage.Wert,
                                edge=self.topology.edges[top_kante_id],
                                direction=signal.Punkt_Objekt_TOP_Kante[0].Wirkrichtung.Wert,
                                side_distance=signal.Punkt_Objekt_TOP_Kante[0].Seitlicher_Abstand.Wert,
                                distance_previous_node=signal.Punkt_Objekt_TOP_Kante[0].Abstand.Wert
                            )
                            self.topology.add_signal(signal_obj)
                            signal_obj.edge.signals.append(signal_obj)
