# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false

"""Tests for the Compliance Report Service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.compliance.compliance_report_service import (
    ComplianceFramework,
    ComplianceReport,
    SectionScore,
    generate_report,
    generate_all_reports,
)


class TestComplianceFramework:
    """Tests for the ComplianceFramework enum."""

    def test_all_frameworks_defined(self):
        """All five frameworks are defined."""
        frameworks = list(ComplianceFramework)
        assert ComplianceFramework.GDPR in frameworks
        assert ComplianceFramework.HIPAA in frameworks
        assert ComplianceFramework.CCPA in frameworks
        assert ComplianceFramework.DORA in frameworks
        assert ComplianceFramework.FERPA in frameworks

    def test_framework_values(self):
        """Framework values are lowercase strings."""
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.CCPA.value == "ccpa"
        assert ComplianceFramework.DORA.value == "dora"
        assert ComplianceFramework.FERPA.value == "ferpa"


class TestSectionScore:
    """Tests for the SectionScore dataclass."""

    def test_section_score_creation(self):
        """SectionScore stores section name, score, evidence count, and details."""
        score = SectionScore(
            section="data_consent",
            score=75.0,
            evidence_count=8,
            details="8 audit event(s) in last 90 days",
        )
        assert score.section == "data_consent"
        assert score.score == 75.0
        assert score.evidence_count == 8
        assert "8 audit event" in score.details

    def test_section_score_zero_evidence(self):
        """SectionScore with zero evidence has score 0."""
        score = SectionScore(
            section="breach_notification",
            score=0.0,
            evidence_count=0,
            details="0 audit event(s) in last 90 days",
        )
        assert score.score == 0.0
        assert score.evidence_count == 0


class TestComplianceReport:
    """Tests for the ComplianceReport dataclass."""

    def test_readiness_level_ready(self):
        """Overall score >= 80 is 'ready'."""
        report = ComplianceReport(
            framework=ComplianceFramework.GDPR,
            overall_score=85.0,
        )
        assert report.readiness_level == "ready"

    def test_readiness_level_partial(self):
        """Overall score >= 50 and < 80 is 'partial'."""
        report = ComplianceReport(
            framework=ComplianceFramework.HIPAA,
            overall_score=65.0,
        )
        assert report.readiness_level == "partial"

    def test_readiness_level_insufficient(self):
        """Overall score < 50 is 'insufficient'."""
        report = ComplianceReport(
            framework=ComplianceFramework.CCPA,
            overall_score=30.0,
        )
        assert report.readiness_level == "insufficient"

    def test_readiness_level_boundary_80(self):
        """Score of exactly 80 is 'ready'."""
        report = ComplianceReport(
            framework=ComplianceFramework.DORA,
            overall_score=80.0,
        )
        assert report.readiness_level == "ready"

    def test_readiness_level_boundary_50(self):
        """Score of exactly 50 is 'partial'."""
        report = ComplianceReport(
            framework=ComplianceFramework.FERPA,
            overall_score=50.0,
        )
        assert report.readiness_level == "partial"

    def test_report_with_sections(self):
        """Report stores sections list."""
        sections = [
            SectionScore(section="s1", score=100.0, evidence_count=10),
            SectionScore(section="s2", score=50.0, evidence_count=5),
        ]
        report = ComplianceReport(
            framework=ComplianceFramework.GDPR,
            overall_score=75.0,
            sections=sections,
        )
        assert len(report.sections) == 2
        assert report.sections[0].section == "s1"


class TestGenerateReport:
    """Tests for the generate_report function."""

    @pytest.mark.asyncio
    async def test_generate_gdpr_report_with_evidence(self):
        """GDPR report is generated with section scores from audit evidence."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.GDPR)

        assert isinstance(report, ComplianceReport)
        assert report.framework == ComplianceFramework.GDPR
        assert len(report.sections) == 5  # GDPR has 5 sections
        # Each section has 5 evidence * 10 = 50 score
        for section in report.sections:
            assert section.score == 50.0
            assert section.evidence_count == 5

    @pytest.mark.asyncio
    async def test_generate_hipaa_report(self):
        """HIPAA report is generated with correct sections."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.HIPAA)

        assert report.framework == ComplianceFramework.HIPAA
        assert len(report.sections) == 5  # HIPAA has 5 sections
        section_names = [s.section for s in report.sections]
        assert "access_control" in section_names
        assert "audit_logging" in section_names
        assert "encryption" in section_names
        assert "data_retention" in section_names
        assert "breach_response" in section_names

    @pytest.mark.asyncio
    async def test_generate_ccpa_report(self):
        """CCPA report is generated with correct sections."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.CCPA)

        assert report.framework == ComplianceFramework.CCPA
        assert len(report.sections) == 4  # CCPA has 4 sections

    @pytest.mark.asyncio
    async def test_generate_dora_report(self):
        """DORA report is generated with correct sections."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.DORA)

        assert report.framework == ComplianceFramework.DORA
        assert len(report.sections) == 4  # DORA has 4 sections

    @pytest.mark.asyncio
    async def test_generate_ferpa_report(self):
        """FERPA report is generated with correct sections."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 4
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.FERPA)

        assert report.framework == ComplianceFramework.FERPA
        assert len(report.sections) == 4  # FERPA has 4 sections

    @pytest.mark.asyncio
    async def test_score_capped_at_100(self):
        """Evidence score is capped at 100 even with many events."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 20  # 20 * 10 = 200, capped at 100
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.GDPR)

        for section in report.sections:
            assert section.score <= 100.0

    @pytest.mark.asyncio
    async def test_zero_evidence_gives_zero_score(self):
        """Zero evidence results in zero score for all sections."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.GDPR)

        for section in report.sections:
            assert section.score == 0.0
            assert section.evidence_count == 0

    @pytest.mark.asyncio
    async def test_overall_score_is_weighted_average(self):
        """Overall score is a weighted average of section scores."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10  # 10 * 10 = 100 score per section
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.GDPR)

        # All sections have score 100, so overall should be 100
        assert report.overall_score == 100.0

    @pytest.mark.asyncio
    async def test_custom_days_parameter(self):
        """The days parameter controls the look-back window."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3
        session.execute = AsyncMock(return_value=mock_count_result)

        report = await generate_report(session, ComplianceFramework.GDPR, days=30)

        assert report is not None
        # Verify the query was called (we can't easily check the days param
        # since it's embedded in the cutoff calculation, but the report
        # should still be generated)
        assert len(report.sections) == 5


class TestGenerateAllReports:
    """Tests for the generate_all_reports function."""

    @pytest.mark.asyncio
    async def test_generate_all_reports_returns_all_frameworks(self):
        """generate_all_reports returns reports for all 5 frameworks."""
        session = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        session.execute = AsyncMock(return_value=mock_count_result)

        reports = await generate_all_reports(session)

        assert len(reports) == 5
        assert "gdpr" in reports
        assert "hipaa" in reports
        assert "ccpa" in reports
        assert "dora" in reports
        assert "ferpa" in reports
        for report in reports.values():
            assert isinstance(report, ComplianceReport)
