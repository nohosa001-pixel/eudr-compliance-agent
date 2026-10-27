# -*- coding: utf-8 -*-
"""Autonomous Daily EUDR Regulatory Intelligence Generator
===========================================================
Uses Google Gemini 3.8 Flash with Google Search Grounding to automatically research,
synthesize, and generate comprehensive daily EU Deforestation Regulation (EUDR, Reg (EU) 2023/1115)
intelligence briefing reports, archiving them in `docs/reports/` and alerting stakeholders.
"""

from __future__ import annotations

import os
import sys
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv

# Reconfigure console output for UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("[ERROR] 'google-genai' package is required. Install via pip install google-genai", file=sys.stderr)
    sys.exit(1)


SYSTEM_INSTRUCTION = """당신은 'EUDR Compliance Intelligence Desk'의 수석 EU 규제 정책 및 글로벌 공급망 실사(DDS) 전문 분석가입니다.
실시간 Google Search 검색 결과를 바탕으로 EU 집행위원회(European Commission), 관세청(EU CSW-CERTEX), TRACES NT 시스템, 회원국 관할당국(Competent Authorities), 유예/적용 규정((EU) 2026/2102 등), 글로벌 7대 대상 품목(목재/종이, 팜유, 대두, 고무, 커피, 코코아, 소고기/가죽)의 최신 팩트와 집행 가이드라인을 정밀하게 취합하여 최고 수준의 종합 분석 보고서를 한국어로 작성합니다.
반드시 각 조항(Article), TARIC 코드, 국가 벤치마킹(Benchmarking), 세관 통관 전산화 현황, 출처 링크(마크다운 하이퍼링크)를 포함하여 구체적이고 실무 적용 가능한 형태로 작성해야 합니다."""


PROMPT_TEMPLATE = """오늘은 {target_date_str}입니다.
오늘({target_date_str}) 기준 최신 'EU 산림벌채방지규정(EUDR - Regulation (EU) 2023/1115)' 일일 규제 동향 및 공급망 실사 브리핑 보고서를 아래 구조에 맞추어 전문적이고 심층적으로 작성해주세요.

[반드시 포함해야 할 섹션 구조]:
# EU 산림벌채방지규정(EUDR) 일일 규제 동향 및 실사 인텔리전스 보고서 ({target_date_iso})

- **보고 일시**: {target_date_str} 기준
- **분석 주관**: EUDR Compliance Intelligence Desk

---

## 1. EUDR 7대 핵심 품목별 세관 통관 및 공급망 리스크 총괄표
(목재/종이·펄프, 팜유/유도체, 대두, 천연고무/타이어, 커피, 코코아, 소/가죽)
- 마크다운 테이블 형식: | 대상 품목 | 주요 HS/TARIC 코드 | 글로벌 주요 공급국 | 리스크 등급(고/표준/저) | 세관(CSW-CERTEX) 통관 핵심 점검 항목 | 최근 규제 이슈 및 공급망 변동 |
- 각 품목별 최신 EU 및 무역 통계 출처 링크를 포함할 것.

---

## 2. EU 세관 전자시스템(CSW-CERTEX) & TRACES NT 실시간 연동 심층 분석
- 세관 CSW-CERTEX와 TRACES NT 시스템 간 실시간 자동 교차 검증 메커니즘
- DDS(공급망 실사 신고서) 참조번호 및 검증키 불일치 시 세관 자동 반출 차단(Automatic Cargo Release Hold) 및 과징금(최대 연간 매출 4%) 리스크
- 수입신고서(UCC DE 12 03 000 000 및 TARIC 코드 C081, C082) 전자 매핑 사전 검증의 중요성

---

## 3. 국가별 벤치마킹(Country Benchmarking) 및 의무 감사 비율 동향
- 위험군별 검사 비율: 고위험국(9%), 표준위험국(3%), 저위험국(1%)
- 1% 무작위 샘플링 검사 적발 시 24시간 내 소명 데이터 제출 의무 (WGS84 농장 폴리곤 + Sentinel-1/2 위성 증빙)
- 한국 등 저위험국(Low-risk) 수출 기업의 실질적 실사 의무 및 보관 의무(5년) 유의점

---

## 4. 최신 EUDR 법제화, 위임규정 및 가이드라인 동향
- 위임규정 (EU) 2026/2102 등 최신 개정 및 해석 지침 영향 (면제 품목 코드 Y120, 가죽/고무/올레오케미컬 예외 규정 등)
- 2026년 대기업 적용 및 2027년 중소기업(SME) 적용 타임라인 D-Day 현황

---

## 5. 국내 수출 제조기업(타이어, 제지/포장재, 식품/화장품, 가구 등) 핵심 실행 가이드
- 공급망 업스트림(동남아, 남미 등) WGS84 GPS 다각형(Polygon) 좌표 수집 체계 구축
- 산림 황폐화(Forest Degradation) 및 2020년 12월 31일 기준선 위성 검증 방안
- TRACES NT 적합 XML 전자 데이터 번들 자동화 전략

---

## 6. X (Twitter) 포스팅용 브리핑 초안
- [국문 버전] 핵심 요약 불렛포인트, 해시태그
- [영문 버전] Executive summary, policy action bullets, hashtags
"""


def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment. Please check .env file.")
    return genai.Client(api_key=api_key)


def generate_eudr_briefing(target_date: Optional[datetime.date] = None) -> tuple[Path, str]:
    """Generates the EUDR daily briefing using Gemini 3.8 Flash with Google Search Grounding."""
    if target_date is None:
        target_date = datetime.date.today()

    target_date_iso = target_date.strftime("%Y-%m-%d")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][target_date.weekday()]
    target_date_str = f"{target_date.year}년 {target_date.month}월 {target_date.day}일({weekday_kr})"

    print(f"[EUDR Intelligence] Generating EUDR regulatory report for {target_date_str}...")

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    prompt = PROMPT_TEMPLATE.format(
        target_date_str=target_date_str,
        target_date_iso=target_date_iso,
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
    )

    print(f"[EUDR Intelligence] Querying {model_name} with Google Search Grounding...")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )

    content = response.text or ""
    if not content.strip():
        raise RuntimeError("Received empty response from Gemini API.")

    # Target directory: docs/reports
    reports_dir = PROJECT_ROOT / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"{target_date_iso}_eudr_briefing.md"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[EUDR Intelligence] Successfully saved report to {report_file} ({len(content)} chars)")
    return report_file, content


def main():
    parser = argparse.ArgumentParser(description="Autonomous Daily EUDR Briefing Generator")
    parser.add_argument("--date", type=str, help="Target date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Print brief excerpt without overwriting file")
    args = parser.parse_args()

    target_date = None
    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"[ERROR] Invalid date format: {args.date}. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    try:
        report_file, content = generate_eudr_briefing(target_date)
        if args.dry_run:
            print("\n" + "=" * 80)
            print(content[:500] + "\n...\n[TRUNCATED]")
            print("=" * 80)
    except Exception as exc:
        print(f"[ERROR] Failed to generate EUDR briefing: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
