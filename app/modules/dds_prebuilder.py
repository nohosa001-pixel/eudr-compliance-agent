from app.modules.dds_generator import DDSGenerator
from app.modules.traces_nt_schema_mapper import TracesNTSchemaMapper
from app.modules.evidence_bundle_generator import EvidenceBundleGenerator

class DDSPrebuilder(DDSGenerator):
    """
    TRACES-NT DDS Prebuilder Engine for EUDR Compliance.
    Embeds AS-IS legal disclaimer clauses, SHA-256 metadata, and self-healing audit bundles.
    """
    pass

__all__ = ["DDSPrebuilder", "DDSGenerator", "TracesNTSchemaMapper", "EvidenceBundleGenerator"]
