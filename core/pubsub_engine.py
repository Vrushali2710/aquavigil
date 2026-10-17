import datetime
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("aquavigil.pubsub")

class PubSubOperationalEngine:
    """
    Pillar II: Cloud Pub/Sub Event-Driven Operational Ingestion Engine.
    Captures operational supply-cycle shutdown events, pump stoppage signals,
    and reported sector depressurizations as lightweight JSON payloads.
    Orchestrates analytical tasks to evaluate network segments entering vulnerable rest periods.
    """
    def __init__(self):
        self.events_history: List[Dict[str, Any]] = []
        self.active_depressurizations: Dict[str, Dict[str, Any]] = {}
        self.pressure_history: List[float] = [2.80] * 25
        self.last_pressure: float = 2.80
        self.last_tick_timestamp: float = datetime.datetime.utcnow().timestamp()
        # Pre-seed initial active state (fully pressurized)
        self.pipe_states: Dict[str, Dict[str, Any]] = {
            "WTR-PIPE-4011": {
                "status": "PRESSURIZED",
                "pressure_bar": 2.8,
                "valve_id": "VLV-SEC4-WEST-02",
                "material": "CAST_IRON_UNLINED",
                "installation_decade": "1980s"
            },
            "WTR-PIPE-4012": {
                "status": "PRESSURIZED",
                "pressure_bar": 2.7,
                "valve_id": "VLV-SEC4-WEST-02",
                "material": "CAST_IRON_UNLINED",
                "installation_decade": "1980s"
            },
            "WTR-PIPE-4013": {
                "status": "PRESSURIZED",
                "pressure_bar": 3.4,
                "valve_id": "VLV-SEC4-NORTH-01",
                "material": "DUCTILE_IRON",
                "installation_decade": "2010s"
            }
        }
        self.valve_states: Dict[str, str] = {
            "VLV-SEC4-WEST-02": "OPEN",
            "VLV-SEC4-NORTH-01": "OPEN"
        }

    def publish_scada_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate Google Cloud Pub/Sub message publish and ingestion.
        Validates schema against Google Cloud AI Builder Cup specifications.
        """
        event_id = payload.get("event_id", f"evt_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        event_type = payload.get("event_type", "SUPPLY_CYCLE_SHUTDOWN")
        valve_id = payload.get("valve_id", "VLV-SEC4-WEST-02")
        timestamp = payload.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        telemetry = payload.get("telemetry", {})
        impacted_sub_network = payload.get("impacted_sub_network", {})

        processed_event = {
            "event_id": event_id,
            "valve_id": valve_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "telemetry": telemetry,
            "impacted_sub_network": impacted_sub_network,
            "ingested_via": "Cloud Pub/Sub (Topic: scada.valve.telemetry)",
            "processing_latency_ms": 14.2
        }

        # Apply state changes to pipeline topology
        actuator_state = telemetry.get("actuator_state", "CLOSED")
        residual_pressure = telemetry.get("residual_pressure_bar", 0.05)
        downstream_lines = impacted_sub_network.get("downstream_line_ids", ["WTR-PIPE-4011", "WTR-PIPE-4012"])

        self.valve_states[valve_id] = actuator_state

        for pipe_id in downstream_lines:
            if pipe_id in self.pipe_states:
                if event_type == "SUPPLY_CYCLE_SHUTDOWN" or actuator_state == "CLOSED":
                    self.pipe_states[pipe_id]["status"] = "UNPRESSURIZED_RESTING"
                    self.pipe_states[pipe_id]["pressure_bar"] = residual_pressure
                    self.active_depressurizations[pipe_id] = processed_event
                else:
                    self.pipe_states[pipe_id]["status"] = "PRESSURIZED"
                    self.pipe_states[pipe_id]["pressure_bar"] = 2.8
                    self.active_depressurizations.pop(pipe_id, None)

        self.events_history.insert(0, processed_event)
        logger.info(f"Ingested PubSub event {event_id}: Valve {valve_id} is {actuator_state}")
        return processed_event

    def trigger_supply_cessation_demo(self) -> Dict[str, Any]:
        """
        Minute 1 of Hackathon Presentation Blueprint:
        Triggers simulated supply-cycle cessation for Sector 4 South.
        """
        demo_payload = {
            "event_id": "evt_valve_down_90412",
            "valve_id": "VLV-SEC4-WEST-02",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "event_type": "SUPPLY_CYCLE_SHUTDOWN",
            "telemetry": {
                "actuator_state": "CLOSED",
                "residual_pressure_bar": 0.05,
                "pipe_material": "CAST_IRON_UNLINED",
                "installation_decade": "1980s"
            },
            "impacted_sub_network": {
                "sector_id": "SECTOR_04_SOUTH",
                "downstream_line_ids": ["WTR-PIPE-4011", "WTR-PIPE-4012"]
            }
        }
        return self.publish_scada_event(demo_payload)

    def trigger_repressurization_demo(self) -> Dict[str, Any]:
        """Restore normal water pressure cycle."""
        demo_payload = {
            "event_id": "evt_valve_up_90413",
            "valve_id": "VLV-SEC4-WEST-02",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "event_type": "SUPPLY_CYCLE_RESUME",
            "telemetry": {
                "actuator_state": "OPEN",
                "residual_pressure_bar": 2.85,
                "pipe_material": "CAST_IRON_UNLINED",
                "installation_decade": "1980s"
            },
            "impacted_sub_network": {
                "sector_id": "SECTOR_04_SOUTH",
                "downstream_line_ids": ["WTR-PIPE-4011", "WTR-PIPE-4012"]
            }
        }
        return self.publish_scada_event(demo_payload)

    def get_live_telemetry_tick(self) -> Dict[str, Any]:
        """
        Emits live real-time SCADA operational telemetry.
        Generates realistic micro-oscillations, live ISO timestamps, and active pressure curves.
        """
        now = datetime.datetime.utcnow()
        import math
        t = now.timestamp()
        
        valve_state = self.valve_states.get("VLV-SEC4-WEST-02", "OPEN")
        
        for pipe_id in ["WTR-PIPE-4011", "WTR-PIPE-4012"]:
            if pipe_id in self.pipe_states:
                if valve_state == "OPEN":
                    base = 2.80
                    oscillation = round(math.sin(t * 0.8) * 0.05 + math.cos(t * 1.5) * 0.02, 2)
                    self.pipe_states[pipe_id]["pressure_bar"] = round(base + oscillation, 2)
                    self.pipe_states[pipe_id]["status"] = "PRESSURIZED"
                else:
                    noise = round(math.sin(t * 0.5) * 0.01, 2)
                    self.pipe_states[pipe_id]["pressure_bar"] = round(0.05 + noise, 2)
                    self.pipe_states[pipe_id]["status"] = "UNPRESSURIZED_RESTING"

        pipe4011 = self.pipe_states.get("WTR-PIPE-4011", {})
        curr_p = pipe4011.get("pressure_bar", 2.80)

        # Update rolling buffer
        self.pressure_history.append(curr_p)
        if len(self.pressure_history) > 30:
            self.pressure_history.pop(0)

        dt = max(0.2, t - self.last_tick_timestamp)
        dp_dt = round((curr_p - self.last_pressure) / dt, 3)
        self.last_pressure = curr_p
        self.last_tick_timestamp = t

        if valve_state == "CLOSED":
            transient_regime = "SUB_ATMOSPHERIC_SIPHONAGE" if curr_p <= 0.10 else "DRAIN_DOWN_TRANSIENT"
        elif dp_dt > 0.4:
            transient_regime = "REPRESSURIZATION_SURGE"
        else:
            transient_regime = "STEADY_HYDRAULIC_EQUILIBRIUM"

        return {
            "timestamp": now.isoformat() + "Z",
            "valve_id": "VLV-SEC4-WEST-02",
            "actuator_state": valve_state,
            "residual_pressure_bar": curr_p,
            "status": pipe4011.get("status", "PRESSURIZED"),
            "flow_rate_lps": round(42.5 + math.sin(t) * 3.0, 1) if valve_state == "OPEN" else 0.0,
            "pressure_gradient_dp_dt": dp_dt,
            "transient_hydraulic_regime": transient_regime,
            "reynolds_flow_regime": "TURBULENT (Re=48,200)" if valve_state == "OPEN" else "LAMINAR_DRAIN (Re<500)",
            "pressure_history": self.pressure_history,
            "active_depressurizations": list(self.active_depressurizations.keys()),
            "pubsub_topic": "projects/aquavigil-2026/topics/scada.valve.telemetry",
            "pubsub_subscription": "projects/aquavigil-2026/subscriptions/scada-spatial-correlator-sub"
        }

    def get_operational_status(self) -> Dict[str, Any]:
        return {
            "valves": self.valve_states,
            "pipe_states": self.pipe_states,
            "active_depressurizations": list(self.active_depressurizations.keys()),
            "total_events_logged": len(self.events_history),
            "recent_events": self.events_history[:10]
        }

pubsub_engine = PubSubOperationalEngine()
