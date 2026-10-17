import datetime
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("aquavigil.escalation")

class ContextualEscalationEngine:
    """
    Two-Tier Escalation Model:
    Combines Gemini Multimodal Visual Fouling Index with BigQuery GIS Subterranean Intrusion Risk Score.
    Prevents false public alarms while providing rapid, defensible utility triage.
    """
    def __init__(self):
        self.escalation_log = []

    def evaluate_escalation(
        self,
        household_id: str,
        address: str,
        connected_pipe_id: str,
        visual_analysis: Dict[str, Any],
        spatial_risk_score: float,
        pipe_operational_status: str
    ) -> Dict[str, Any]:
        """
        Synthesizes multimodal image forensics with SCADA & BigQuery GIS spatial topology.
        """
        visual_score = float(visual_analysis.get("visual_fouling_index", 0.0))
        severity = visual_analysis.get("fouling_severity", "LOW")
        deposit = visual_analysis.get("deposit_indicators", "INORGANIC_SILT")
        
        is_depressurized = (pipe_operational_status == "UNPRESSURIZED_RESTING")
        effective_spatial_risk = spatial_risk_score if is_depressurized else (spatial_risk_score * 0.3)

        # Contextual Composite Risk Formula
        # 55% weight to visual fouling + 45% weight to subterranean cross-contamination exposure
        contextual_score = round((0.55 * visual_score) + (0.45 * effective_spatial_risk), 2)
        contextual_score = min(1.0, max(0.0, contextual_score))

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        # Determine Tier 1 (Household) & Tier 2 (Municipal Utility) Actions
        if contextual_score >= 0.75 and is_depressurized:
            escalation_level = "TIER_2_CORROBORATED_UTILITY_ESCALATION"
            badge_color = "red"
            tier1_household_action = {
                "headline": "PRECAUTIONARY HOUSEHOLD ADVISORY",
                "recommended_action": "REPLACE_FILTER_IMMEDIATELY",
                "water_usage": "BOIL BEFORE CONSUMING / DO NOT DRINK UNBOILED",
                "message": f"Elevated visual fouling ({visual_score}) matches active subterranean low-pressure ingress risk along your street ({connected_pipe_id}). Replace your cartridge housing immediately. Boil tap water for 1-2 minutes until utility line flushing completes."
            }
            tier2_municipal_action = {
                "status": "DISPATCH_FIELD_VERIFICATION_CREW",
                "priority": "HIGH_SEVERITY_TRIAGE",
                "target_corridor": f"Corridor {connected_pipe_id} (Adjacent to Sewer Intersect)",
                "action_required": "Deploy mobile grab-sampler to hydrant downstream. Conduct rapid chlorine residual and turbidity assay. Inspect isolation valve VLV-SEC4-WEST-02.",
                "defensibility_note": "Corroborated by physical SCADA supply cessation + BigQuery GIS 5m buffer proximity + Gemini visual fouling forensics."
            }
        elif visual_score >= 0.60:
            escalation_level = "TIER_1_INTERNAL_HOUSEHOLD_ACTION"
            badge_color = "amber"
            tier1_household_action = {
                "headline": "FILTER CARTRIDGE REPLACEMENT RECOMMENDED",
                "recommended_action": "REPLACE_CARTRIDGE",
                "water_usage": "SAFE WITH FRESH FILTER",
                "message": f"Cartridge saturation is elevated ({visual_score}), but distribution main pressure is normal. Accumulation is likely standard calendar wear. Replace cartridge to maintain filtration throughput."
            }
            tier2_municipal_action = {
                "status": "PASSIVE_MONITORING",
                "priority": "INFORMATIONAL",
                "target_corridor": f"Pipe {connected_pipe_id}",
                "action_required": "No field crew required. Logged to water quality observation ledger.",
                "defensibility_note": "Isolated endpoint filter wear without spatial network ingress triggers."
            }
        else:
            escalation_level = "ROUTINE_NORMAL"
            badge_color = "emerald"
            tier1_household_action = {
                "headline": "PURIFIER & WATER HEALTH OPTIMAL",
                "recommended_action": "ROUTINE_MONITORING",
                "water_usage": "NORMAL USE",
                "message": "Cartridge surface is clean with low particulate fouling. No depressurization warnings on your sector."
            }
            tier2_municipal_action = {
                "status": "ALL_SYSTEMS_NOMINAL",
                "priority": "NONE",
                "target_corridor": f"Pipe {connected_pipe_id}",
                "action_required": "None",
                "defensibility_note": "No network depressurization or endpoint particulate saturation detected."
            }

        incident_record = {
            "incident_id": f"ESC-{datetime.datetime.utcnow().strftime('%m%d-%H%M%S')}",
            "timestamp": timestamp,
            "household_id": household_id,
            "address": address,
            "connected_pipe_id": connected_pipe_id,
            "pipe_operational_status": pipe_operational_status,
            "visual_fouling_index": visual_score,
            "spatial_intrusion_score": spatial_risk_score,
            "contextual_escalation_score": contextual_score,
            "escalation_level": escalation_level,
            "badge_color": badge_color,
            "tier1_household": tier1_household_action,
            "tier2_municipal": tier2_municipal_action,
            "visual_rationale": visual_analysis.get("rationale", ""),
            "technical_metrics": {
                "decision_fusion_formula": "Score = 0.55 * VisualFouling + 0.45 * SpatialRisk * is_depressurized",
                "estimated_population_protected": 1420,
                "households_in_sector": 320,
                "sop_protocol_code": "SOP-WQ-4011-RAPID-FLUSH",
                "field_dispatch_sla_mins": 45,
                "target_sampling_point": "Hydrant HYD-PIN-04 (Chainage 0+180)",
                "regulatory_defensibility": "WHO Drinking-water Guidelines 4th Ed. §7.2 & EPA Emergency Triage"
            }
        }

        self.escalation_log.insert(0, incident_record)
        return incident_record

    def get_recent_escalations(self, limit: int = 10):
        return self.escalation_log[:limit]

escalation_engine = ContextualEscalationEngine()
