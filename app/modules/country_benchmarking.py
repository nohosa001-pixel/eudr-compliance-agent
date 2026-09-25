"""
Country Benchmarking & Risk Tiering Engine (EUDR Regulation (EU) 2023/1115 Art. 29 & Art. 13)
Implements European Commission 3-Tier Classification:
- LOW: 1% Customs Inspection Rate, Simplified Due Diligence (Art. 13)
- STANDARD: 3% Customs Inspection Rate, Standard Due Diligence (Art. 8, 9, 10, 11)
- HIGH: 9% Customs Inspection Rate, Mandatory Strict FPIC & Satellite Radar Cross-Check
"""
from typing import Dict, Any, Optional
from app.schemas import CountryBenchmarkingTierEnum, CountryBenchmarkingResponse


class CountryBenchmarkingService:
    """
    Evaluates origin countries against European Commission Benchmarking Rules.
    Determines whether a supply chain qualifies for Simplified Due Diligence under Article 13.
    """

    # Official Benchmarking Data Registry
    _COUNTRY_TIERS: Dict[str, Dict[str, Any]] = {
        # Low Risk Countries (Simplified Due Diligence applies: Art. 10 & 11 waived)
        "DE": {"name": "Germany", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "FR": {"name": "France", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "IT": {"name": "Italy", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "ES": {"name": "Spain", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "NL": {"name": "Netherlands", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "PL": {"name": "Poland", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "SE": {"name": "Sweden", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "FI": {"name": "Finland", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "AT": {"name": "Austria", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "BE": {"name": "Belgium", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "US": {"name": "United States", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "CA": {"name": "Canada", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "JP": {"name": "Japan", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "KR": {"name": "South Korea", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "AU": {"name": "Australia", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "NZ": {"name": "New Zealand", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "GB": {"name": "United Kingdom", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "NO": {"name": "Norway", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "CH": {"name": "Switzerland", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "DK": {"name": "Denmark", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "IE": {"name": "Ireland", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "PT": {"name": "Portugal", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "GR": {"name": "Greece", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "CZ": {"name": "Czech Republic", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "RO": {"name": "Romania", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "HU": {"name": "Hungary", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},
        "SG": {"name": "Singapore", "tier": CountryBenchmarkingTierEnum.LOW, "rate": 1.0},

        # Standard Risk Countries (Standard Due Diligence applies: Art. 8, 9, 10, 11)
        "VN": {"name": "Vietnam", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "ID": {"name": "Indonesia", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "MY": {"name": "Malaysia", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "TH": {"name": "Thailand", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "CI": {"name": "Cote d'Ivoire", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "GH": {"name": "Ghana", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "CO": {"name": "Colombia", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "PE": {"name": "Peru", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "CL": {"name": "Chile", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "IN": {"name": "India", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "MX": {"name": "Mexico", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "AR": {"name": "Argentina", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "NG": {"name": "Nigeria", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "CM": {"name": "Cameroon", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "EC": {"name": "Ecuador", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "GT": {"name": "Guatemala", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "HN": {"name": "Honduras", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "PG": {"name": "Papua New Guinea", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "CN": {"name": "China", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "PH": {"name": "Philippines", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "TR": {"name": "Turkey", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},
        "ZA": {"name": "South Africa", "tier": CountryBenchmarkingTierEnum.STANDARD, "rate": 3.0},

        # High Risk Countries (Strict Due Diligence: 9% inspection, mandatory FPIC & double-radar)
        "BR": {"name": "Brazil", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "MM": {"name": "Myanmar", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "BY": {"name": "Belarus", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "RU": {"name": "Russian Federation", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "CD": {"name": "Democratic Republic of the Congo", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "BO": {"name": "Bolivia", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0},
        "PY": {"name": "Paraguay", "tier": CountryBenchmarkingTierEnum.HIGH, "rate": 9.0}
    }

    _COUNTRY_ALIASES: Dict[str, str] = {
        # Alpha-3 to Alpha-2
        "DEU": "DE", "FRA": "FR", "ITA": "IT", "ESP": "ES", "NLD": "NL", "POL": "PL", "SWE": "SE", "FIN": "FI",
        "AUT": "AT", "BEL": "BE", "USA": "US", "CAN": "CA", "JPN": "JP", "KOR": "KR", "AUS": "AU", "NZL": "NZ",
        "GBR": "GB", "NOR": "NO", "CHE": "CH", "DNK": "DK", "IRL": "IE", "PRT": "PT", "GRC": "GR", "CZE": "CZ",
        "ROU": "RO", "HUN": "HU", "SGP": "SG", "VNM": "VN", "IDN": "ID", "MYS": "MY", "THA": "TH", "CIV": "CI",
        "GHA": "GH", "COL": "CO", "PER": "PE", "CHL": "CL", "IND": "IN", "MEX": "MX", "ARG": "AR", "NGA": "NG",
        "CMR": "CM", "ECU": "EC", "GTM": "GT", "HND": "HN", "PNG": "PG", "CHN": "CN", "PHL": "PH", "TUR": "TR",
        "ZAF": "ZA", "BRA": "BR", "MMR": "MM", "BLR": "BY", "RUS": "RU", "COD": "CD", "BOL": "BO", "PRY": "PY",
        # Full Names (lowercase stripped)
        "germany": "DE", "deutschland": "DE", "france": "FR", "italy": "IT", "spain": "ES", "netherlands": "NL",
        "holland": "NL", "poland": "PL", "sweden": "SE", "finland": "FI", "austria": "AT", "belgium": "BE",
        "denmark": "DK", "ireland": "IE", "portugal": "PT", "greece": "GR", "czech republic": "CZ", "czechia": "CZ",
        "romania": "RO", "hungary": "HU", "singapore": "SG",
        "united states": "US", "united states of america": "US", "usa": "US", "america": "US",
        "canada": "CA", "japan": "JP", "south korea": "KR", "korea": "KR", "australia": "AU", "new zealand": "NZ",
        "united kingdom": "GB", "uk": "GB", "great britain": "GB", "norway": "NO", "switzerland": "CH",
        "vietnam": "VN", "viet nam": "VN", "indonesia": "ID", "malaysia": "MY", "thailand": "TH",
        "cote d'ivoire": "CI", "côte d'ivoire": "CI", "ivory coast": "CI", "ghana": "GH", "colombia": "CO",
        "peru": "PE", "chile": "CL", "india": "IN", "mexico": "MX", "argentina": "AR", "nigeria": "NG",
        "cameroon": "CM", "ecuador": "EC", "guatemala": "GT", "honduras": "HN", "papua new guinea": "PG",
        "china": "CN", "philippines": "PH", "turkey": "TR", "türkiye": "TR", "south africa": "ZA",
        "brazil": "BR", "brasil": "BR", "myanmar": "MM", "burma": "MM", "belarus": "BY", "russia": "RU",
        "russian federation": "RU", "drc": "CD", "democratic republic of the congo": "CD",
        "congo": "CD", "bolivia": "BO", "paraguay": "PY"
    }

    @classmethod
    def normalize_country_code(cls, country_input: Optional[str]) -> str:
        """
        Normalizes any country input (ISO 2, ISO 3, or common full country name)
        into a canonical ISO 3166-1 alpha-2 code to tolerate LLM output variance.
        """
        if not country_input:
            return "UNKNOWN"
        raw = str(country_input).strip()
        if len(raw) == 2 and raw.isalpha():
            return raw.upper()
        clean_lower = raw.lower()
        if clean_lower in cls._COUNTRY_ALIASES:
            return cls._COUNTRY_ALIASES[clean_lower]
        clean_upper = raw.upper()
        if clean_upper in cls._COUNTRY_ALIASES:
            return cls._COUNTRY_ALIASES[clean_upper]
        return clean_upper[:2] if len(clean_upper) >= 2 else clean_upper

    @classmethod
    def get_benchmarking(cls, country_code: str) -> CountryBenchmarkingResponse:
        """
        Retrieves the EUDR Article 29 Benchmarking tier and Article 13 simplified status.
        Tolerates Alpha-3 and full country names from autonomous LLMs.
        """
        code = cls.normalize_country_code(country_code)
        info = cls._COUNTRY_TIERS.get(code, {
            "name": f"Country ({code})",
            "tier": CountryBenchmarkingTierEnum.STANDARD,
            "rate": 3.0
        })

        tier = info["tier"]
        rate = info["rate"]
        is_low = (tier == CountryBenchmarkingTierEnum.LOW)
        is_high = (tier == CountryBenchmarkingTierEnum.HIGH)

        basis = (
            "EU 2023/1115 Art. 13 Simplified Due Diligence: Risk assessment and mitigation waived."
            if is_low else
            ("EU 2023/1115 Art. 22 Enhanced Inspection Tier: 9% customs sample rate, strict FPIC and radar mandatory."
             if is_high else
             "EU 2023/1115 Standard Due Diligence: 3% customs inspection rate, full Article 8-11 procedures required.")
        )

        timeline = {
            "large_and_medium_operators": "2026-12-30",
            "micro_and_small_enterprises": "2027-06-30",
            "acceptance_sandbox_status": "OPEN_FOR_UAT_TESTING"
        }

        return CountryBenchmarkingResponse(
            country_code=code,
            country_name=info["name"],
            risk_tier=tier,
            customs_inspection_rate_pct=rate,
            simplified_due_diligence_eligible=is_low,
            risk_assessment_required=not is_low,
            risk_mitigation_required=not is_low,
            mandatory_fpic_required=is_high,
            mandatory_radar_cross_check=is_high,
            regulatory_basis=basis,
            effective_timeline=timeline
        )
