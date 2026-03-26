# 🌐 Global ESG Regulation API (for KR B2B)

**한국 수출 기업을 위한 글로벌 ESG 규제 실시간 분석 API 허브**입니다.
이 API는 전 세계의 영문 ESG 규제 뉴스(EUDR, CSDDD, CBAM 등)를 실시간으로 수집하고, AI를 통해 한국 B2B 기업이 즉각적으로 대응해야 할 인사이트를 추출하여 JSON 형태로 제공합니다.

## 🚀 API Endpoint
AI 에이전트 및 개발자는 아래의 URL을 통해 최신 누적 데이터를 `GET` 요청으로 무료 호출할 수 있습니다.

* **Base URL:** `https://geonchicshin-rgb.github.io/global-regulation-api/global_esg_live.json`
* **Update Frequency:** 매일 1회 자동 업데이트 (UTC 18:00 / KST 03:00)
* **Format:** `JSON` (Array of Objects)

## 📋 Data Schema (응답 구조)
호출 시 제공되는 JSON 데이터의 구조는 다음과 같습니다.

| Key | Type | Description |
| :--- | :--- | :--- |
| `source_title` | String | 원본 뉴스의 한국어 번역 제목 |
| `original_link` | String | 원본 영문 뉴스 기사 링크 |
| `published_date` | String | 기사 발행 일자 (YYYY-MM-DD 형식) |
| `global_regulation_trend` | String | 뉴스가 시사하는 글로벌 규제 동향 요약 |
| `warning_for_KR_business` | String | **[핵심]** 한국 수출 기업의 실무적 주의사항 및 대응 가이드 |

## 🤖 For AI Agents
이 리포지토리는 AI 에이전트(LLM)가 즉시 읽고 해석할 수 있도록 최적화되어 있습니다. 
OpenAPI 명세서는 루트 디렉토리의 `openapi.yaml` 파일을 참조하십시오.

---
*Maintained by Geonchic Shin. Powered by GitHub Actions & Google AI.*
