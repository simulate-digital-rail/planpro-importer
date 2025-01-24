import logging

from yaramo.model import Signal, SignalState, SignalFunction, SignalKind, SignalSystem
from typing import Set


class SignalReader:

    def __init__(self, topology, container):
        self.topology = topology
        self.container = container

    def get_signal_frames_by_signal_uuid(self, signal_uuid: str):
        frames = []
        for frame in self.container.Signal_Rahmen:
            if frame.ID_Signal.Wert == signal_uuid:
                frames.append(frame)
        return frames

    def get_signal_terms_by_signal_frame_uuid(self, signal_frame_uuid: str) -> Set[SignalState]:
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

    def get_supported_states_of_signal(self, signal_uuid: str) -> [SignalState]:
        supported_states: Set[SignalState] = set()
        frames = self.get_signal_frames_by_signal_uuid(signal_uuid)
        for frame in frames:
            frame_uuid = frame.Identitaet.Wert
            supported_states.update(self.get_signal_terms_by_signal_frame_uuid(frame_uuid))
        return supported_states

    def get_signal_identifier(self, signal):
        if signal.Bezeichnung is None:
            return None
        if signal.Bezeichnung.Bezeichnung_Aussenanlage is not None:
            return signal.Bezeichnung.Bezeichnung_Aussenanlage.Wert
        if signal.Bezeichnung.Bezeichnung_Tabelle is not None:
            return signal.Bezeichnung.Bezeichnung_Tabelle.Wert
        return None

    def get_signal_function(self, signal):
        if signal.Signal_Real is not None:
            if signal.Signal_Real.Signal_Funktion.Wert == "":
                return str(SignalFunction.Nicht_Definiert)
            return signal.Signal_Real.Signal_Funktion.Wert
        if len(signal.Signal_Fiktiv.Fiktives_Signal_Funktion) > 1:
            logging.warning(f"Multiple fictional functions of signals are not supported. Use first one. "
                            f"Signal: {self.get_signal_identifier(signal)} ({signal.Identitaet.Wert})")
        return signal.Signal_Fiktiv.Fiktives_Signal_Funktion[0].Wert

    def get_signal_kind(self, signal):
        if signal.Signal_Real is not None:
            if signal.Signal_Real.Signal_Real_Aktiv_Schirm is None:
                return SignalKind.andere
            return signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signal_Art.Wert
        return SignalKind.FiktivesSignal

    def get_side_distance(self, signal):
        if signal.Punkt_Objekt_TOP_Kante[0].Seitlicher_Abstand is None:
            return 0.0
        return signal.Punkt_Objekt_TOP_Kante[0].Seitlicher_Abstand.Wert

    def get_signal_system(self, signal):
        if signal.Signal_Real.Signal_Real_Aktiv_Schirm is not None:
            return signal.Signal_Real.Signal_Real_Aktiv_Schirm.Signalsystem.Wert
        return SignalSystem.andere

    def read_signals_from_container(self):
        for signal in self.container.Signal:
            signal_uuid = signal.Identitaet.Wert
            bezeichnung = self.get_signal_identifier(signal)
            if bezeichnung is None:
                logging.error(f"No identifier found for signal with uuid {signal_uuid}. Skip this signal.")
                continue
            function = self.get_signal_function(signal)
            if function not in [e.name for e in SignalFunction]:
                logging.error(f"Signal function {function} of signal {bezeichnung} ({signal_uuid}) not supported. "
                              f"Skip signal.")
                continue
            real_signal = signal.Signal_Real is not None
            if len(signal.Punkt_Objekt_TOP_Kante) != 1:  # If other than 1, no real signal with lights
                logging.warning(f"Signals with more than one related TOP_Kante will be associated to the first "
                                f"TOP_Kante. Affected Signal: {bezeichnung} ({signal_uuid})")
            top_kante_id = signal.Punkt_Objekt_TOP_Kante[0].ID_TOP_Kante.Wert
            if top_kante_id not in self.topology.edges:  # Corresponding TOP edge not found
                logging.error(f"Can not found TOP_Kante of a signal {bezeichnung} ({signal_uuid}). "
                              f"Skip this signal.")
                continue
            supported_states = self.get_supported_states_of_signal(signal_uuid)
            system = SignalSystem.andere
            if real_signal:
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
                real_signal=real_signal,
                system=system
            )
            self.topology.add_signal(signal_obj)
            signal_obj.edge.signals.append(signal_obj)

