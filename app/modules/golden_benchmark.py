from typing import List, Dict, Any
import time
from datetime import datetime, timezone

from app.schemas import (
    EUDRSupplyChainPayload,
    ComplianceStatusEnum,
    BenchmarkCaseResult,
    BenchmarkSuiteReport
)
from app.modules.traceability_collector import TraceabilityCollector
from app.modules.satellite_compliance_checker import DeforestationAnalyzer
from app.modules.legal_document_auditor import LegalAuditor
from app.modules.dds_generator import DDSGenerator

class GoldenBenchmarkSuite:
    """
    Standardized Ground-Truth Benchmark Suite for EUDR Compliance Verification.
    
    Contains 10 verified golden scenarios representing critical edge cases in global supply chains:
    1. Clean Compliant Cocoa (Ghana)
    2. Post-2020 Hansen Deforestation (Indonesia Palm Oil)
    3. Pre-2020 Historical Clearance (Brazil Soya)
    4. 4ha Polygon Rule Point Violation (Vietnam Rubber)
    5. Self-Intersecting Polygon Topology Error (Cote d'Ivoire Coffee)
    6. Dual-Claim Overlapping Multi-Plot Collision (Malaysia Palm Oil)
    7. Expired Harvest Permit (Sweden Timber)
    8. High-Risk Missing FPIC Consent (Indonesia Soya)
    9. Simplified Due Diligence Low-Risk Country (Finland Coniferous Wood)
    10. Borderline Cloud Cover with High Confidence Triangulation (Colombia Coffee)
    """

    BENCHMARK_CASES = [
        {
            "case_id": "GOLDEN-01-CLEAN-COCOA",
            "title": "Clean Compliant Cocoa (Ghana)",
            "scenario_type": "Standard Compliant",
            "expected_status": ComplianceStatusEnum.COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-GH-001",
                "operator": {"operator_name": "Accra Cocoa Traders", "eori_number": "FR9911223344", "country": "FR", "address": "Rue 1, Paris"},
                "commodity": {"hs_code": "180100", "description": "Cocoa beans", "net_mass_kg": 15000.0},
                "plots": [{
                    "plot_id": "GH-COCOA-CLEAN-1", "country_code": "GH", "area_hectares": 3.5,
                    "geometry": {"type": "Point", "coordinates": [-1.6244, 6.6885]}, "production_date": "2024-02-01"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Ghana Land Commission", "issue_date": "2020-01-01"},
                    {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Ghana Forestry", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
                    {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Ghana Registrar", "issue_date": "2019-01-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-02-POST2020-DEFOREST",
            "title": "Post-2020 Deforestation (Indonesia Palm Oil)",
            "scenario_type": "Satellite Deforestation Violation",
            "expected_status": ComplianceStatusEnum.NON_COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-ID-002",
                "operator": {"operator_name": "Rotterdam Palm Imports", "eori_number": "NL8822334455", "country": "NL", "address": "Port 2, Rotterdam"},
                "commodity": {"hs_code": "151110", "description": "Crude palm oil", "net_mass_kg": 40000.0},
                "plots": [{
                    "plot_id": "ID-PALM-FLAGGED-deforestation_2022", "country_code": "ID", "area_hectares": 2.5,
                    "geometry": {"type": "Point", "coordinates": [101.4421, 0.5312]}, "production_date": "2024-01-01", "notes": "deforestation_2022"
                }],
                "documents": [{"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "BPN Indonesia", "issue_date": "2021-01-01"}]
            }
        },
        {
            "case_id": "GOLDEN-03-PRE2020-HISTORICAL",
            "title": "Pre-2020 Historical Clearance (Brazil Soya)",
            "scenario_type": "Pre-Cutoff Historical Conversion",
            "expected_status": ComplianceStatusEnum.COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-BR-003",
                "operator": {"operator_name": "Agro Grain Europe", "eori_number": "DE3344556677", "country": "DE", "address": "Hafen 3, Hamburg"},
                "commodity": {"hs_code": "120190", "description": "Soya beans", "net_mass_kg": 60000.0},
                "plots": [{
                    "plot_id": "BR-SOYA-PRE2020-deforestation_2018", "country_code": "BR", "area_hectares": 3.0,
                    "geometry": {"type": "Point", "coordinates": [-55.7214, -12.5421]}, "production_date": "2024-03-01", "notes": "deforestation_2018"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "CAR Brazil", "issue_date": "2018-05-01"},
                    {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "IBAMA Brazil", "issue_date": "2023-01-01"},
                    {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Junta Comercial MT", "issue_date": "2018-01-01"},
                    {"doc_id": "D4", "doc_type": "FPIC_CONSENT", "issuing_authority": "FUNAI Indigenous Council", "issue_date": "2018-02-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-04-4HA-POINT-VIOLATION",
            "title": "4ha Rule Point Violation (Vietnam Rubber)",
            "scenario_type": "Spatial 4ha Violation",
            "expected_status": ComplianceStatusEnum.NON_COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-VN-004",
                "operator": {"operator_name": "Euro Rubber BV", "eori_number": "NL4455667788", "country": "NL", "address": "Kanaal 4, Amsterdam"},
                "commodity": {"hs_code": "400110", "description": "Natural rubber latex", "net_mass_kg": 20000.0},
                "plots": [{
                    "plot_id": "VN-RUBBER-POINT-12HA", "country_code": "VN", "area_hectares": 12.5,
                    "geometry": {"type": "Point", "coordinates": [108.4385, 11.9412]}, "production_date": "2024-04-01"
                }],
                "documents": [{"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "VN Land Dept", "issue_date": "2020-01-01"}]
            }
        },
        {
            "case_id": "GOLDEN-05-SELF-INTERSECTING-POLYGON",
            "title": "Self-Intersecting Polygon Topology Error (Cote d'Ivoire Coffee)",
            "scenario_type": "Spatial Topology Violation",
            "expected_status": ComplianceStatusEnum.NON_COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-CI-005",
                "operator": {"operator_name": "Cafe Europe SA", "eori_number": "FR5566778899", "country": "FR", "address": "Quai 5, Le Havre"},
                "commodity": {"hs_code": "090111", "description": "Coffee green", "net_mass_kg": 18000.0},
                "plots": [{
                    "plot_id": "CI-COFFEE-BOWTIE", "country_code": "CI", "area_hectares": 5.0,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[ -5.5, 6.8 ], [ -5.4, 6.9 ], [ -5.4, 6.8 ], [ -5.5, 6.9 ], [ -5.5, 6.8 ]]] # Figure-8 bowtie
                    },
                    "production_date": "2024-02-15"
                }],
                "documents": [{"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "CI Land Office", "issue_date": "2020-01-01"}]
            }
        },
        {
            "case_id": "GOLDEN-06-DUAL-CLAIM-OVERLAP",
            "title": "Dual-Claim Overlapping Multi-Plot Collision (Malaysia Palm Oil)",
            "scenario_type": "Spatial Inter-Plot Collision",
            "expected_status": ComplianceStatusEnum.COMPLIANT, # Evaluates spatial overlap warning with compliant status
            "payload": {
                "supplier_id": "SUPP-MY-006",
                "operator": {"operator_name": "Antwerp Palm Oil", "eori_number": "BE6677889900", "country": "BE", "address": "Haven 6, Antwerp"},
                "commodity": {"hs_code": "151110", "description": "Palm oil", "net_mass_kg": 30000.0},
                "plots": [
                    {
                        "plot_id": "MY-PLOT-A", "country_code": "MY", "area_hectares": 6.0,
                        "geometry": {"type": "Polygon", "coordinates": [[[101.40, 3.10], [101.45, 3.10], [101.45, 3.15], [101.40, 3.15], [101.40, 3.10]]]},
                        "production_date": "2024-01-10"
                    },
                    {
                        "plot_id": "MY-PLOT-B", "country_code": "MY", "area_hectares": 6.0,
                        "geometry": {"type": "Polygon", "coordinates": [[[101.42, 3.12], [101.47, 3.12], [101.47, 3.17], [101.42, 3.17], [101.42, 3.12]]]},
                        "production_date": "2024-01-12"
                    }
                ],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "MPOB Malaysia", "issue_date": "2019-01-01"},
                    {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "MPOB Malaysia", "issue_date": "2023-01-01"},
                    {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "SSM Malaysia", "issue_date": "2018-01-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-07-EXPIRED-PERMIT",
            "title": "Expired Harvest Permit (Sweden Timber)",
            "scenario_type": "Legal Document Expiration",
            "expected_status": ComplianceStatusEnum.NON_COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-SE-007",
                "operator": {"operator_name": "Baltic Timber Ltd", "eori_number": "SE7788990011", "country": "SE", "address": "Skog 7, Stockholm"},
                "commodity": {"hs_code": "440711", "description": "Coniferous wood sawn", "net_mass_kg": 25000.0},
                "plots": [{
                    "plot_id": "SE-TIMBER-1", "country_code": "SE", "area_hectares": 2.0,
                    "geometry": {"type": "Point", "coordinates": [18.0686, 59.3293]}, "production_date": "2024-05-01"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Skogsstyrelsen", "issue_date": "2020-01-01", "expiry_date": "2021-01-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-08-HIGH-RISK-NO-FPIC",
            "title": "High-Risk Missing FPIC Consent (Indonesia Soya)",
            "scenario_type": "Legal FPIC Omission",
            "expected_status": ComplianceStatusEnum.NON_COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-ID-008",
                "operator": {"operator_name": "Java Soya Imports", "eori_number": "NL8899001122", "country": "NL", "address": "Dam 8, Rotterdam"},
                "commodity": {"hs_code": "120190", "description": "Soya beans", "net_mass_kg": 35000.0},
                "plots": [{
                    "plot_id": "ID-SOYA-1", "country_code": "ID", "area_hectares": 3.0,
                    "geometry": {"type": "Point", "coordinates": [106.8456, -6.2088]}, "production_date": "2024-03-01"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Agrarian Ministry", "issue_date": "2021-01-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-09-SIMPLIFIED-LOW-RISK",
            "title": "Simplified Due Diligence Low-Risk Country (Finland Wood)",
            "scenario_type": "Low Risk Country Simplified DD",
            "expected_status": ComplianceStatusEnum.COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-FI-009",
                "operator": {"operator_name": "Nordic Pulp Oy", "eori_number": "FI9900112233", "country": "FI", "address": "Metsa 9, Helsinki"},
                "commodity": {"hs_code": "440711", "description": "Pine timber", "scientific_name": "Pinus sylvestris", "net_mass_kg": 50000.0},
                "plots": [{
                    "plot_id": "FI-PINE-1", "country_code": "FI", "area_hectares": 2.5,
                    "geometry": {"type": "Point", "coordinates": [24.9384, 60.1699]}, "production_date": "2024-04-10"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Metsahallitus", "issue_date": "2020-01-01"},
                    {"doc_id": "D2", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "PRH Finland", "issue_date": "2019-01-01"}
                ]
            }
        },
        {
            "case_id": "GOLDEN-10-CLOUD-COVER-TRIANGULATION",
            "title": "Cloud-Cover Multi-Sensor Triangulation (Colombia Coffee)",
            "scenario_type": "Multi-Sensor Consensus",
            "expected_status": ComplianceStatusEnum.COMPLIANT,
            "payload": {
                "supplier_id": "SUPP-CO-010",
                "operator": {"operator_name": "Bogota Coffee Importers", "eori_number": "ES0011223344", "country": "ES", "address": "Gran Via 10, Madrid"},
                "commodity": {"hs_code": "090111", "description": "Arabica coffee beans", "net_mass_kg": 22000.0},
                "plots": [{
                    "plot_id": "CO-COFFEE-HUILA-CLEAN-10", "country_code": "CO", "area_hectares": 3.8,
                    "geometry": {"type": "Point", "coordinates": [-75.2819, 2.9273]}, "production_date": "2024-02-20"
                }],
                "documents": [
                    {"doc_id": "D1", "doc_type": "LAND_USE_TITLE", "issuing_authority": "Agencia Nacional de Tierras", "issue_date": "2019-01-01"},
                    {"doc_id": "D2", "doc_type": "HARVEST_PERMIT", "issuing_authority": "Federacion Nacional de Cafeteros", "issue_date": "2023-01-01", "expiry_date": "2028-01-01"},
                    {"doc_id": "D3", "doc_type": "BUSINESS_LICENSE", "issuing_authority": "Camara de Comercio", "issue_date": "2020-01-01"}
                ]
            }
        }
    ]

    @classmethod
    def run_suite(cls) -> BenchmarkSuiteReport:
        case_results: List[BenchmarkCaseResult] = []
        tp, tn, fp, fn = 0, 0, 0, 0

        for case in cls.BENCHMARK_CASES:
            t0 = time.time()
            payload_obj = EUDRSupplyChainPayload.model_validate(case["payload"])
            
            # Step 1: Spatial
            spatial_valid, spatial_results, spatial_summary = TraceabilityCollector.collect_and_validate(payload_obj.plots)
            
            # Step 2: Satellite
            deforest_free, sat_results, sat_summary = DeforestationAnalyzer.analyze_all_plots(payload_obj.plots, spatial_results)
            
            # Step 3: Legal
            legal_audit = LegalAuditor.audit_documents(payload_obj.documents, payload_obj.plots, payload_obj.commodity)
            
            # Step 4: DDS
            report = DDSGenerator.assemble_report(
                payload=payload_obj,
                spatial_valid=spatial_valid,
                spatial_results=spatial_results,
                spatial_summary=spatial_summary,
                deforestation_free=deforest_free,
                satellite_results=sat_results,
                satellite_summary=sat_summary,
                legal_audit=legal_audit,
                start_time=datetime.now(timezone.utc)
            )

            duration_ms = (time.time() - t0) * 1000.0
            actual_status = report.status
            expected_status = case["expected_status"]
            passed = (actual_status == expected_status)

            # Confusion Matrix calculation
            if expected_status == ComplianceStatusEnum.COMPLIANT and actual_status == ComplianceStatusEnum.COMPLIANT:
                tp += 1
            elif expected_status == ComplianceStatusEnum.NON_COMPLIANT and actual_status == ComplianceStatusEnum.NON_COMPLIANT:
                tn += 1
            elif expected_status == ComplianceStatusEnum.NON_COMPLIANT and actual_status == ComplianceStatusEnum.COMPLIANT:
                fp += 1
            elif expected_status == ComplianceStatusEnum.COMPLIANT and actual_status == ComplianceStatusEnum.NON_COMPLIANT:
                fn += 1

            case_results.append(BenchmarkCaseResult(
                case_id=case["case_id"],
                title=case["title"],
                scenario_type=case["scenario_type"],
                expected_status=expected_status,
                actual_status=actual_status,
                passed=passed,
                confidence_score=report.confidence_assessment.overall_confidence_score,
                duration_ms=round(duration_ms, 2)
            ))

        total = len(case_results)
        passed_count = sum(1 for c in case_results if c.passed)
        accuracy = (passed_count / total) * 100.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0
        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 100.0
        f1 = (2 * precision * recall / (precision + recall) / 100.0) if (precision + recall) > 0 else 1.0
        fpr = (fp / (fp + tn) * 100.0) if (fp + tn) > 0 else 0.0
        fnr = (fn / (fn + tp) * 100.0) if (fn + tp) > 0 else 0.0

        return BenchmarkSuiteReport(
            total_cases=total,
            passed_cases=passed_count,
            failed_cases=total - passed_count,
            accuracy_pct=round(accuracy, 1),
            precision_pct=round(precision, 1),
            recall_pct=round(recall, 1),
            f1_score=round(f1, 3),
            false_positive_rate_pct=round(fpr, 1),
            false_negative_rate_pct=round(fnr, 1),
            benchmark_timestamp=datetime.now(timezone.utc).isoformat(),
            case_results=case_results
        )
