import logging

from yaramo.model import (
    Topology,
    Signal,
    SignalState,
    SignalFunction,
    SignalKind,
    SignalSystem,
)
from .model110 import CContainer
from typing import Set


class SignalReader:

    def __init__(self, topology: Topology, container: CContainer):
        """Reads all signals of a container and adds them to the topology

        :param topology: The yaramo topology
        :param container: The XML-container of the PlanPro file
        """
        self.topology: Topology = topology
        self.container: CContainer = container

    def get_signal_frames_by_signal_uuid(self, signal_uuid: str):
        """Gets all frames of a signal identified by its UUID

        :param signal_uuid: The UUID of the signal
        :return: all frames of the signal
        """
        frames = []
        for frame in self.container.Signal_Rahmen:
            if frame.ID_Signal.Wert == signal_uuid:
                frames.append(frame)
        return frames

    def get_signal_states_by_signal_frame_uuid(
        self, signal_frame_uuid: str
    ) -> Set[SignalState]:
        """Gets all signal states of a signal frame

        :param signal_frame_uuid: The UUID of the signal frame
        :return: A set of all signal states
        """
        terms: Set[SignalState] = set()
        for term in self.container.Signal_Signalbegriff:
            if term.ID_Signal_Rahmen.Wert == signal_frame_uuid:
                signal_term_string = term.Signalbegriff_ID.Kurzbezeichnung_DS
                if signal_term_string is None:
                    signal_term_string = term.Signalbegriff_ID.Beschreibung
                state: SignalState = SignalState.get_state_by_string(signal_term_string)
                if state is not None:
                    terms.add(state)
        return terms

    def get_supported_states_of_signal(self, signal_uuid: str) -> Set[SignalState]:
        """Gets all signal states of a signal.

        :param signal_uuid: The UUID of the signal
        :return: A set of all possible Signal States
        """
        supported_states: Set[SignalState] = set()
        frames = self.get_signal_frames_by_signal_uuid(signal_uuid)
        for frame in frames:
            frame_uuid = frame.Identitaet.Wert
            supported_states.update(
                self.get_signal_states_by_signal_frame_uuid(frame_uuid)
            )
        return supported_states

    def get_signal_function(self, signal):
        """Gets the signal function of a signal. Returns SignalFunction.Nicht_Definiert if the
        function is not defined.

        :param signal: The signal XML
        :return: The signal function
        """
        if signal.Signal_Real is not None:
            if signal.Signal_Real.Signal_Funktion.Wert == "":
                return str(SignalFunction.Nicht_Definiert)
            return signal.Signal_Real.Signal_Funktion.Wert
        if len(signal.Signal_Fiktiv.Fiktives_Signal_Funktion) > 1:
            logging.warning(
                f"Multiple fictional functions of signals are not supported. Use first one. "
                f"Signal: {self.get_signal_identifier(signal)} ({signal.Identitaet.Wert})"
            )
        return signal.Signal_Fiktiv.Fiktives_Signal_Funktion[0].Wert

    @staticmethod
    def get_signal_kind(signal):
        """Gets the signal kind of the signal. Returns SignalKind.andere if the kind is not defined.

        :param signal: The signal XML
        :return: The signal kind
        """
        if signal.Signal_Real is not None:
            if signal.Signal_Real.Signal_Real_Aktiv_Schirm is None:
                return SignalKind.andere
            return signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signal_Art.Wert
        return SignalKind.FiktivesSignal

    @staticmethod
    def get_signal_identifier(signal):
        """Gets the signal identifier. Returns None if no identifier is defined.

        :param signal: The signal XML
        :return: The signal identifier or None
        """
        if signal.Bezeichnung is None:
            return None
        if signal.Bezeichnung.Bezeichnung_Aussenanlage is not None:
            return signal.Bezeichnung.Bezeichnung_Aussenanlage.Wert
        if signal.Bezeichnung.Bezeichnung_Tabelle is not None:
            return signal.Bezeichnung.Bezeichnung_Tabelle.Wert
        return None

    @staticmethod
    def get_side_distance(signal):
        """Gets the side distance of the signal. Returns 0.0 if the side distance is not defined.

        :param signal: The signal XML
        :return: The side distance
        """
        if signal.Punkt_Objekt_TOP_Kante[0].Seitlicher_Abstand is None:
            return 0.0
        return signal.Punkt_Objekt_TOP_Kante[0].Seitlicher_Abstand.Wert

    @staticmethod
    def get_signal_system(signal):
        """Get ths signal system. Return SignalSystem.andere if the system is not defined.

        :param signal: The signal XML
        :return: The signal system
        """
        if signal.Signal_Real.Signal_Real_Aktiv_Schirm is not None:
            return signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signalsystem.Wert
        return SignalSystem.andere

    def read_signals_from_container(self):
        """Reads the signals for the container"""

        for signal in self.container.Signal:
            signal_uuid = signal.Identitaet.Wert
            bezeichnung = self.get_signal_identifier(signal)
            if bezeichnung is None:
                logging.error(
                    f"No identifier found for signal with uuid {signal_uuid}. Skip this signal."
                )
                continue
            function = self.get_signal_function(signal)
            if function not in SignalFunction.__members__:
                logging.error(
                    f"Signal function {function} of signal {bezeichnung} ({signal_uuid}) not supported. "
                    f"Skip signal."
                )
                continue
            if len(signal.Punkt_Objekt_TOP_Kante) != 1:
                # If other than 1, no real signal with lights
                logging.warning(
                    f"Signals with more than one related TOP_Kante will be associated to the first "
                    f"TOP_Kante. Affected Signal: {bezeichnung} ({signal_uuid})"
                )
            top_kante_id = signal.Punkt_Objekt_TOP_Kante[0].ID_TOP_Kante.Wert
            if top_kante_id not in self.topology.edges:
                # Corresponding TOP edge not found
                logging.error(
                    f"Can not found TOP_Kante of a signal {bezeichnung} ({signal_uuid}). "
                    f"Skip this signal."
                )
                continue
            supported_states = self.get_supported_states_of_signal(signal_uuid)
            system = SignalSystem.andere
            if signal.Signal_Real is not None:
                system = self.get_signal_system(signal)
            signal_obj = Signal(
                uuid=signal_uuid,
                function=function,
                kind=self.get_signal_kind(signal),
                name=bezeichnung,
                edge=self.topology.edges[top_kante_id],
                direction=signal.Punkt_Objekt_TOP_Kante[0].Wirkrichtung.Wert,
                side_distance=self.get_side_distance(signal),
                distance_edge=signal.Punkt_Objekt_TOP_Kante[0].Abstand.Wert,
                supported_states=supported_states,
                system=system,
            )
            self.topology.add_signal(signal_obj)
            signal_obj.edge.signals.append(signal_obj)
