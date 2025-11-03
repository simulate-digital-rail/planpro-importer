from yaramo.model import Route


class RouteReader:

    @staticmethod
    def read_routes_from_container(container, topology):
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
            if start_signal_uuid in topology.signals:
                start_signal = topology.signals[start_signal_uuid]
            if end_signal_uuid in topology.signals:
                end_signal = topology.signals[end_signal_uuid]
            if start_signal is None or end_signal is None:
                continue  # Start or end signal not found

            # Edges
            edges = set()
            for teilbereich in fstr_fahrweg.Bereich_Objekt_Teilbereich:
                edge_uuid = teilbereich.ID_TOP_Kante.Wert
                if edge_uuid in topology.edges:
                    edges.add(topology.edges[edge_uuid])

            # Build route
            route = Route(
                start_signal=start_signal,
                maximum_speed=maximum_speed,
                uuid=fahrweg_uuid,
                name=f"{start_signal.name}-{end_signal.name}",
            )
            route.end_signal = end_signal
            route.edges = edges
            topology.add_route(route)